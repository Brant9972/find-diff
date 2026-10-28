import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.core import Cropper, apply_rejections, atomic, initialise, live_people, lock, process, rejection_keys, valid_reveal
from media_pipeline.review import import_decisions, report
from media_pipeline.sources import SourceError, rights, source_key, public_https

REVEAL = {k: [.08, .2, .92, y] for k, y in [('eyes', .4), ('nose', .55), ('mouth', .7), ('chin', .9)]}
REVEAL['full'] = [0, 0, 1, 1]


def candidate(n='one', license='CC BY 4.0'):
    return {'url': 'https://images.example.org/' + n + '.jpg', 'source': 'https://example.org/' + n,
            'license': license, 'licenseUrl': 'https://creativecommons.org/licenses/by/4.0/', 'artist': 'Photographer',
            'filename': n + '.jpg', 'caption': '測試人物 official portrait'}


class Provider:
    name = 'fixture'
    def __init__(self, results, error=False):
        self.results, self.error, self.calls = results, error, 0
    def search(self, person, http, round_number=0):
        self.calls += 1
        if self.error:
            raise SourceError('network_error', 'fixture outage')
        yield from self.results


class FakeHTTP:
    def get(self, url):
        return ('original ' + url).encode()


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'singer'
        self.directory = self.root / 'expansion-1500/pipeline'
        self.person = {'plannedQuestionId': 't1', 'candidateId': 'c1', 'name': '測試人物', 'aliases': []}
        atomic(self.root / 'expansion-1500/release-plan-20261028.json', {'selectedNew': [self.person]})
        self.state = initialise(self.root, self.directory)
        self.row = self.state['people']['t1']

    def tearDown(self):
        self.temp.cleanup()

    def crop(self, blob):
        return b'game image ' + blob, REVEAL, {'decoded': True, 'size': [600, 720]}

    def run_person(self, providers, crop=None):
        process(self.person, self.row, self.root, self.directory, providers, FakeHTTP(), crop or self.crop, set(), checkpoint=lambda: atomic(self.directory / 'state.json', self.state))
        atomic(self.directory / 'state.json', self.state)

    def test_failure_is_retryable_and_other_source_runs(self):
        self.run_person([Provider([], error=True), Provider([candidate()])])
        self.assertEqual(self.row['status'], 'pending_review')
        self.assertEqual(len(self.row['candidates']), 1)
        self.assertEqual(self.row['lastErrors'][0]['code'], 'network_error')

    def test_no_result_can_retry_after_restart(self):
        self.run_person([Provider([])])
        self.assertEqual(self.row['status'], 'no_suitable_source')
        self.assertTrue(self.row['nextRetryAt'])
        self.state = initialise(self.root, self.directory)
        self.row = self.state['people']['t1']
        self.run_person([Provider([candidate()])])
        self.assertEqual(self.row['status'], 'pending_review')
        self.assertEqual(self.row['attempts'], 2)

    def test_multiple_candidates_cap_and_no_duplicate_on_rerun(self):
        self.run_person([Provider([candidate(str(i)) for i in range(5)])])
        self.assertEqual(len(self.row['candidates']), 3)
        snapshot = copy.deepcopy(self.row['candidates'])
        self.run_person([Provider([candidate(str(i)) for i in range(5)])])
        self.assertEqual(self.row['candidates'], snapshot)

    def test_unknown_license_is_metadata_only_never_downloaded(self):
        def fail_download(*args):
            raise AssertionError('Must not download')
        http = FakeHTTP()
        http.get = fail_download
        process(self.person, self.row, self.root, self.directory, [Provider([candidate(license='Copyright retained')])], http, self.crop, set())
        self.assertEqual(self.row['candidates'][0]['status'], 'metadata_only')
        self.assertFalse(self.row['candidates'][0]['eligibleForLive'])
        self.assertEqual(self.row['lastErrors'][0]['code'], 'license_unclear')

    def test_rejected_source_blocked_after_review(self):
        self.run_person([Provider([candidate()])])
        c = self.row['candidates'][0]
        doc = {'schemaVersion': 1, 'reviewer': 'External reviewer', 'reviewedAt': '2026-10-28T12:00:00Z',
               'decisions': [{'personId': 't1', 'candidateId': c['id'], 'gameSha256': c['gameSha256'], 'decision': 'rejected', 'reason': 'wrong person'}]}
        import_decisions(self.root, self.directory, self.state, doc)
        self.run_person([Provider([candidate(), candidate('alternative')])])
        self.assertEqual(len(self.row['candidates']), 2)
        self.assertEqual(self.row['candidates'][0]['status'], 'rejected')

    def test_review_hash_and_approved_protection(self):
        self.run_person([Provider([candidate()])])
        c = self.row['candidates'][0]
        entry = {'personId': 't1', 'candidateId': c['id'], 'gameSha256': 'wrong', 'decision': 'approved', 'reason': 'Identity, licence and crop checked'}
        doc = {'schemaVersion': 1, 'reviewer': 'External reviewer', 'reviewedAt': '2026-10-28T12:00:00Z', 'decisions': [entry]}
        with self.assertRaises(ValueError):
            import_decisions(self.root, self.directory, self.state, doc)
        self.assertEqual(c['status'], 'pending_review')
        entry['gameSha256'] = c['gameSha256']
        import_decisions(self.root, self.directory, self.state, doc)
        self.assertEqual(self.row['status'], 'approved')
        self.assertFalse(c['eligibleForLive'])
        with self.assertRaises(ValueError):
            import_decisions(self.root, self.directory, self.state, doc)

    def test_all_review_entries_validated_before_mutation(self):
        self.run_person([Provider([candidate(), candidate('two')])])
        one, two = self.row['candidates']
        doc = {'schemaVersion': 1, 'reviewer': 'Reviewer', 'reviewedAt': '2026-10-28', 'decisions': [
            {'personId': 't1', 'candidateId': one['id'], 'gameSha256': one['gameSha256'], 'decision': 'approved', 'reason': 'Checked'},
            {'personId': 't1', 'candidateId': two['id'], 'gameSha256': 'stale', 'decision': 'rejected', 'reason': 'No'}]}
        with self.assertRaises(ValueError):
            import_decisions(self.root, self.directory, self.state, doc)
        self.assertEqual(one['status'], 'pending_review')

    def test_checkpoint_survives_later_provider_crash(self):
        self.run_person([Provider([candidate()]), Provider([], error=True)])
        stored = json.loads((self.directory / 'state.json').read_text())
        self.assertEqual(len(stored['people']['t1']['candidates']), 1)

    def test_legacy_rejections_and_missing_files_are_retryable(self):
        atomic(self.root / 'expansion-1500/draft-media-index.json', {'items': [{'candidateId': 'c1', 'reviewStatus': 'rejected_eyes_not_visible', 'source': candidate()['source'], 'draftPhoto': 'expansion-1500/missing.jpg'}]})
        state = initialise(self.root, self.directory)
        self.assertEqual(state['people']['t1']['status'], 'rejected')
        self.assertIn(source_key(candidate()['source']), rejection_keys(self.root))

    def test_existing_live_person_skipped_and_legacy_untouched(self):
        atomic(self.root / 'questions.json', {'questions': [{'id': 't1', 'name': '測試人物'}]})
        state = initialise(self.root, self.directory)
        self.assertEqual(state['people']['t1']['status'], 'published')

    def test_report_escapes_untrusted_caption_and_stable_ids(self):
        self.row['name'] = '</script><img src=x onerror=alert(1)>'
        summary = report(self.root, self.directory, self.state, 'fixture', [])
        page = (self.directory / 'runs/fixture/review.html').read_text()
        self.assertNotIn('</script><img src=x', page)
        data = json.loads((self.directory / 'runs/fixture/review-index.json').read_text())
        self.assertEqual(data['people'][0]['personId'], 't1')
        self.assertFalse(summary['modifiedProduction'])

    def test_reveal_and_licence_gate(self):
        self.assertTrue(valid_reveal(REVEAL))
        bad = copy.deepcopy(REVEAL)
        bad['nose'][3] = .1
        self.assertFalse(valid_reveal(bad))
        self.assertEqual(rights(candidate()), 'open_license_metadata')
        self.assertEqual(rights(candidate(license='CC BY-NC 4.0')), 'needs_review')
        c = candidate()
        c['licenseUrl'] = 'https://evil.example/licenses/by/4.0/'
        self.assertEqual(rights(c), 'needs_review')

    def test_real_interruption_keeps_candidate_and_searching_checkpoint(self):
        class Interrupted(Provider):
            def search(self, *args):
                raise KeyboardInterrupt('Simulated process interruption')
                yield
        with self.assertRaises(KeyboardInterrupt):
            self.run_person([Provider([candidate()]), Interrupted([])])
        recovered = initialise(self.root, self.directory)['people']['t1']
        self.assertEqual(recovered['status'], 'searching')
        self.assertEqual(len(recovered['candidates']), 1)

    def test_corrupt_images_fail_before_model_or_network(self):
        with self.assertRaises(OSError):
            Cropper(self.root)(b'not an image')
        from PIL import Image
        import io
        buf = io.BytesIO()
        Image.new('RGB', (20, 20)).save(buf, 'PNG')
        with self.assertRaisesRegex(ValueError, 'resolution'):
            Cropper(self.root)(buf.getvalue())

    def test_redirects_do_not_downgrade_tls_or_use_private_ips(self):
        for url in ['http://example.org/a', 'https://127.0.0.1/a', 'https://localhost/a', 'https://user:password@example.org/a']:
            with self.assertRaises(SourceError):
                public_https(url)
        self.assertEqual(public_https('https://commons.wikimedia.org/wiki/File:A.jpg'), 'commons.wikimedia.org')

    def test_metadata_only_can_be_researched_after_licence_is_supplied(self):
        self.run_person([Provider([candidate(license='Copyright retained')])])
        self.assertEqual(self.row['candidates'][0]['status'], 'metadata_only')
        self.run_person([Provider([candidate()])])
        self.assertEqual(len(self.row['candidates']), 1)
        self.assertEqual(self.row['candidates'][0]['status'], 'pending_review')

    def test_search_result_without_identity_evidence_is_not_downloaded(self):
        record = candidate()
        record['caption'] = 'Someone'
        self.run_person([Provider([record])])
        self.assertEqual(self.row['candidates'][0]['status'], 'metadata_only')
        self.assertEqual(self.row['lastErrors'][0]['code'], 'identity_unconfirmed')

    def test_identical_images_from_different_sources_are_not_multiple_options(self):
        http = FakeHTTP()
        http.get = lambda url: b'same image from mirrors'
        process(self.person, self.row, self.root, self.directory, [Provider([candidate(), candidate('mirror')])], http, self.crop, set())
        self.assertEqual(len(self.row['candidates']), 1)
        self.assertEqual(len(self.row['candidates'][0]['alternateSources']), 1)
        self.assertEqual(self.row['lastErrors'][0]['code'], 'duplicate_image')

    def test_same_image_cannot_be_assigned_to_a_second_person(self):
        blob = FakeHTTP().get(candidate()['url'])
        image_hash = hashlib.sha256(self.crop(blob)[0]).hexdigest()
        self.state['people']['other'] = {'personId': 'other', 'status': 'approved', 'candidates': [{'gameSha256': image_hash}]}
        atomic(self.directory / 'state.json', self.state)
        self.run_person([Provider([candidate()])])
        self.assertFalse(self.row['candidates'])
        self.assertEqual(self.row['lastErrors'][0]['code'], 'image_used_for_other_person')
        self.assertEqual(self.state['people']['other']['status'], 'approved')

    def test_new_legacy_rejection_updates_pending_but_never_overwrites_approval(self):
        self.run_person([Provider([candidate()])])
        apply_rejections(self.state, {source_key(candidate()['source'])})
        self.assertEqual(self.row['status'], 'rejected')
        self.assertEqual(self.row['candidates'][0]['status'], 'rejected')
        self.row['status'] = 'approved'
        self.row['candidates'][0]['status'] = 'approved'
        apply_rejections(self.state, {source_key(candidate()['source'])})
        self.assertEqual(self.row['candidates'][0]['status'], 'approved')

    def test_live_git_ref_reads_published_banks_without_checkout(self):
        import subprocess
        repo = self.root.parent
        def git(*args):
            return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.DEVNULL, text=True).strip()
        git('init')
        for filename in ['questions.json', 'actors.json', 'variety.json']:
            atomic(self.root / filename, {'questions': [{'id': 't1', 'name': 'Published'}] if filename == 'questions.json' else []})
        git('add', 'singer')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.org', 'commit', '-m', 'Fixture published banks')
        ref = git('rev-parse', 'HEAD')
        atomic(self.root / 'questions.json', {'questions': []})
        self.assertIn('t1', live_people(self.root, ref))
        self.assertFalse(live_people(self.root))
        self.assertEqual(git('rev-parse', 'HEAD'), ref)

    def test_lock_excludes_other_writer(self):
        with lock(self.directory):
            with self.assertRaises(RuntimeError):
                with lock(self.directory):
                    pass


if __name__ == '__main__':
    unittest.main()
