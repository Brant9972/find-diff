import copy
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.core import Cropper, apply_rejections, atomic, initialise, live_people, lock, process, rejection_keys, valid_reveal
from media_pipeline.review import import_decisions, report
from recover_pipeline import recover
from validate_pipeline import validate
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

    def test_excluded_old_manual_crop_allows_new_source_original(self):
        old = 'https://example.org/old'
        self.row['candidates'].append({
            'id': 'old-manual', 'personId': 't1',
            'source': old, 'status': 'manual_crop_required',
            'originalPath': 'expansion-1500/pipeline/assets/old/original.bin',
        })
        self.person['excludedPhotoSources'] = [old]
        new = candidate('new')
        def failed_auto_crop(blob):
            raise ValueError('Face is too tilted')
        self.run_person([Provider([new])], crop=failed_auto_crop)
        retained = [c for c in self.row['candidates']
                    if c.get('status') == 'manual_crop_required']
        self.assertEqual(len(retained), 2)
        self.assertEqual(retained[-1]['source'], new['source'])
        self.assertTrue(retained[-1]['originalPath'])
        self.assertFalse(retained[-1]['eligibleForLive'])
        self.assertIsNone(retained[-1]['gamePath'])

    def test_unexcluded_manual_crop_still_caps_source_only_originals(self):
        self.row['candidates'].append({
            'id': 'old-manual', 'personId': 't1',
            'source': 'https://example.org/old',
            'status': 'manual_crop_required',
        })
        def failed_auto_crop(blob):
            raise ValueError('Blurred crop: sharpness below 65')
        self.run_person([Provider([candidate('new')])], crop=failed_auto_crop)
        self.assertEqual(
            len([c for c in self.row['candidates']
                 if c.get('status') == 'manual_crop_required']), 1)

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

    def test_vogue_taiwan_rights_conflict_blocks_download_despite_cc_metadata(self):
        photo = candidate('vogue')
        photo.update({'artist': 'VOGUE Taiwan', 'caption': '測試人物 interview portrait'})
        self.assertEqual(rights(photo), 'rights_disputed')
        # Other independent VOGUE publishers must not be falsely blacklisted.
        self.assertEqual(rights({**photo, 'artist': 'VOGUE Hong Kong'}), 'open_license_metadata')
        http = FakeHTTP()
        def fail_download(url):
            raise AssertionError('Disputed VOGUE Taiwan media must not be downloaded')
        http.get = fail_download
        process(self.person, self.row, self.root, self.directory,
                [Provider([photo])], http, self.crop, set())
        self.assertEqual(self.row['candidates'][0]['status'], 'metadata_only')
        self.assertEqual(self.row['candidates'][0]['rightsStatus'], 'rights_disputed')
        self.assertEqual(self.row['lastErrors'][0]['code'], 'license_disputed')
        self.assertFalse(self.row['candidates'][0]['eligibleForLive'])

    def test_vogue_taiwan_in_file_source_is_also_disputed(self):
        photo = candidate('other')
        photo.update({'source': 'https://commons.wikimedia.org/wiki/File:VOGUE_Taiwan_interview.jpg'})
        self.assertEqual(rights(photo), 'rights_disputed')
        self.assertEqual(rights({**photo, 'source': 'https://commons.wikimedia.org/wiki/File:Vogue_Hong_Kong.jpg'}),
                         'open_license_metadata')

    def test_commons_thumbnail_403_falls_back_to_original_without_approving(self):
        photo = candidate('wikimedia')
        photo.update({
            'provider': 'commons',
            'url': 'https://thumb.wikimedia.org/thumb/a.jpg',
            'originalUrl': 'https://upload.wikimedia.org/original/a.jpg',
        })
        calls = []
        class ThumbBlocked:
            def get(self, url):
                calls.append(url)
                if url.startswith('https://thumb.wikimedia.org/'):
                    raise SourceError('http_403', 'thumbnail CDN refused request')
                return b'valid Wikimedia original bytes'
        process(self.person, self.row, self.root, self.directory,
                [Provider([photo])], ThumbBlocked(), self.crop, set())
        self.assertEqual(calls, [photo['url'], photo['originalUrl']])
        self.assertEqual(self.row['status'], 'pending_review')
        result = self.row['candidates'][0]
        self.assertEqual(result['downloadVariant'], 'wikimedia_original_fallback')
        self.assertFalse(result['eligibleForLive'])
        self.assertIsNone(result['humanReview'])
        self.assertEqual(result['originalSha256'],
                         hashlib.sha256(b'valid Wikimedia original bytes').hexdigest())

    def test_non_commons_sources_cannot_use_wikimedia_original_fallback(self):
        photo = candidate('untrusted')
        photo.update({
            'provider': 'openverse',
            'url': 'https://photos.example.org/a.jpg',
            'originalUrl': 'https://upload.wikimedia.org/unrelated.jpg',
        })
        calls = []
        class Refused:
            def get(self, url):
                calls.append(url)
                raise SourceError('http_403', 'source refused')
        process(self.person, self.row, self.root, self.directory,
                [Provider([photo])], Refused(), self.crop, set())
        self.assertEqual(calls, [photo['url']])
        self.assertEqual(self.row['status'], 'download_failed')
        self.assertFalse(any(c.get('status') == 'pending_review' for c in self.row['candidates']))

    def test_crop_failure_preserves_one_source_only_for_manual_recrop(self):
        photo = candidate('needs-recrop')
        photo['provider'] = 'commons'
        image = Image.new('RGB', (500, 600), 'white')
        out = io.BytesIO()
        image.save(out, format='JPEG')
        source = out.getvalue()
        class SourceHTTP:
            def get(self, url):
                return source
        def bad_crop(blob):
            raise ValueError('No reliable frontal face')
        process(self.person, self.row, self.root, self.directory,
                [Provider([photo])], SourceHTTP(), bad_crop, set())
        self.assertEqual(self.row['status'], 'no_suitable_source')
        manual = [c for c in self.row['candidates'] if c.get('status') == 'manual_crop_required']
        self.assertEqual(len(manual), 1)
        self.assertEqual(manual[0]['originalSha256'], hashlib.sha256(source).hexdigest())
        self.assertFalse(manual[0]['eligibleForLive'])
        self.assertFalse(manual[0].get('gamePath'))
        self.assertIsNone(manual[0]['humanReview'])
        atomic(self.directory / 'state.json', self.state)
        validate(self.root)

    def test_english_filename_without_named_caption_cannot_save_manual_crop(self):
        photo = candidate('unverified-homonym')
        photo.update({'provider': 'commons', 'filename': 'Common English Name.jpg',
                      'caption': 'Profile picture'})
        class SourceHTTP:
            def get(self, url):
                return b'raw image'
        def bad_crop(blob):
            raise ValueError('No reliable frontal face')
        process(self.person, self.row, self.root, self.directory,
                [Provider([photo])], SourceHTTP(), bad_crop, set())
        self.assertFalse(any(c.get('status') == 'manual_crop_required'
                             for c in self.row['candidates']))

    def test_person_specific_false_identity_source_is_not_downloaded(self):
        bad = candidate('english-homonym')
        self.person['excludedPhotoSources'] = [bad['source']]
        class NoDownload:
            def get(self, url):
                raise AssertionError('Rejected identity source must not be downloaded')
        process(self.person, self.row, self.root, self.directory,
                [Provider([bad])], NoDownload(), self.crop, set())
        self.assertFalse(self.row['candidates'])
        self.assertEqual(self.row['status'], 'no_suitable_source')

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

    def recovery_fixture(self):
        atomic(self.directory / 'state.json', self.state)
        digest = hashlib.sha256((self.directory / 'state.json').read_bytes()).hexdigest()
        atomic(self.directory / 'recovery-request.json', {'runId': '123', 'baseStateSha256': digest, 'completed': False})
        artifact = self.root.parent / 'artifact'
        incoming = copy.deepcopy(self.state)
        incoming['people']['t1']['attempts'] = 3
        atomic(artifact / 'singer/expansion-1500/pipeline/state.json', incoming)
        return artifact, incoming

    def test_artifact_recovery_resumes_without_overwriting_review(self):
        artifact, incoming = self.recovery_fixture()
        recover(self.root, artifact)
        stored = json.loads((self.directory / 'state.json').read_text())
        self.assertEqual(stored, incoming)
        recover(self.root, artifact)  # completed request is idempotent

    def test_artifact_recovery_refuses_diverged_state_or_new_approval(self):
        artifact, incoming = self.recovery_fixture()
        self.state['people']['t1']['attempts'] = 9
        atomic(self.directory / 'state.json', self.state)
        with self.assertRaises(ValueError):
            recover(self.root, artifact)
        self.state['people']['t1']['attempts'] = 0
        atomic(self.directory / 'state.json', self.state)
        incoming['people']['t1']['status'] = 'approved'
        atomic(artifact / 'singer/expansion-1500/pipeline/state.json', incoming)
        with self.assertRaises(ValueError):
            recover(self.root, artifact)
        self.assertEqual(json.loads((self.directory / 'state.json').read_text())['people']['t1']['status'], 'not_started')

    def test_lock_excludes_other_writer(self):
        with lock(self.directory):
            with self.assertRaises(RuntimeError):
                with lock(self.directory):
                    pass


if __name__ == '__main__':
    unittest.main()
