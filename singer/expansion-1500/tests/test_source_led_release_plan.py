"""Keep exact-source diagnostics separate from human approval and release."""
import json
import unittest
from pathlib import Path


class SourceLedReleasePlanTest(unittest.TestCase):
    def test_eric_kot_exact_sources_are_pinned_but_not_released(self):
        root = Path(__file__).resolve().parents[1]
        plan = json.loads((root / 'release-plan-20261028.json').read_text(
            encoding='utf-8'))
        people = [row for row in plan['selectedNew']
                  if row['plannedQuestionId'] == 't1500_0564']
        self.assertEqual(len(people), 1)
        person = people[0]
        self.assertEqual(person['name'], '葛民輝')
        self.assertEqual(person['wikidataId'], 'Q590914')
        self.assertIn('Eric Kot', person['aliases'])
        self.assertEqual(person['cachedMetadataRecheckToken'],
                         '20261030-eric-kot-verified-alias')
        self.assertIn('Eric Kot', person['acceptedAnswers'])
        self.assertEqual(person['reviewExactCommonsFiles'], [
            'Eric Kot 20231029.jpg', 'Eric Kot 200812.JPG'])
        self.assertEqual(len(person['reviewVerifiedOriginalSources']), 2)
        self.assertEqual(person['qaStatus'], 'not_releasable')
        self.assertFalse(person['imageVerification']['finalCropReviewed'])
        self.assertFalse(person['imageVerification']['rightsDocumented'])


    def test_english_alias_matches_verified_commons_filename_not_substring(self):
        import sys
        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root))
        from media_pipeline.sources import identity
        person = json.loads((root / 'release-plan-20261028.json')
                            .read_text(encoding='utf-8'))['selectedNew']
        person = next(row for row in person
                      if row['plannedQuestionId'] == 't1500_0564')
        self.assertIn('Eric Kot', identity(person, 'Eric Kot 20231029.jpg'))
        self.assertIn('Eric Kot', identity(person, 'Eric Kot 200812.JPG'))
        self.assertEqual(identity(person, 'Eric Kotch in 2023'), [])


    def test_batch_is_targeted_and_never_claims_approval(self):
        root = Path(__file__).resolve().parents[1]
        request = json.loads((root / 'pipeline' / 'batch-request.json')
                             .read_text(encoding='utf-8'))
        # Do not freeze a historical source batch's provider selection:
        # entity-led QID diagnostics and curated Commons recovery are both
        # allowed, while arbitrary/unsafe providers remain forbidden.
        self.assertIn(request['providers'], (
            ['curated', 'commons'], ['entity', 'commons'],
            ['commons'], ['curated'],
        ))
        if request.get('requestId') == '20261031-sodagreen-alternative-photo-search-2':
            self.assertEqual(request['plannedPersonIds'], ['t1500_0112', 't1500_0114'])
        if request['retryFailed']:
            # Only bounded, explicitly named, curated-source diagnostics may
            # bypass cooldown. Never pin this test to a past request ID.
            self.assertEqual(request['mode'], 'search')
            self.assertTrue(request['plannedPersonIds'])
            self.assertLessEqual(len(request['plannedPersonIds']), 10)
            if 'curated' not in request['providers']:
                if request['providers'] == ['entity', 'commons']:
                    # Only a small explicit cohort may retry with the new
                    # exact-Q5 Wikidata Commons category-sitelink discovery.
                    # Runtime Q5/name/QID checks and prior photo exclusions
                    # remain mandatory; this never authorizes publication.
                    self.assertLessEqual(len(request['plannedPersonIds']), 6)
                    self.assertIn('exact q5', request['purpose'].casefold())
                    self.assertIn('commonswiki', request['purpose'].casefold())
                    self.assertLessEqual(request['maxMinutes'], 20)
                    self.assertLessEqual(request['personSeconds'], 120)
                else:
                    # Commons-only retries require an explicit exact file,
                    # not an open-ended name sweep.
                    self.assertEqual(request['providers'], ['commons'])
                    plan = json.loads((root / 'release-plan-20261028.json').read_text(encoding='utf-8'))
                    selected = {p['plannedQuestionId']: p for p in plan['selectedNew']}
                    self.assertTrue(all(selected[pid].get('reviewExactCommonsFiles')
                                        for pid in request['plannedPersonIds']))
            self.assertNotIn('openverse', request['providers'])
            self.assertIn('exact', request['purpose'].casefold())
        self.assertIn(request['mode'], ('render_only', 'search', 'manual_recrop', 'import_review_rejections'))
        ids = request['plannedPersonIds']
        if request['mode'] in {'render_only', 'import_review_rejections'}:
            self.assertEqual(ids, [])
            self.assertEqual(request['targetPeople'], 0)
            if request['mode'] == 'import_review_rejections':
                import sys
                sys.path.insert(0, str(root))
                from media_pipeline.review import validate_rejection_only_document
                review_path = Path(request['reviewDecisionPath'])
                self.assertEqual(review_path.parent, Path('singer/expansion-1500/pipeline/chatgpt-review'))
                self.assertTrue(review_path.name.endswith('-rejections-only.json'))
                review = json.loads((root.parent.parent / review_path).read_text(encoding='utf-8'))
                self.assertGreater(len(validate_rejection_only_document(review)), 0)
        else:
            # A controlled diagnostic may replace a finished render-only
            # request. Do not freeze the old request values into the test.
            self.assertTrue(1 <= request['targetPeople'] <= 10)
            self.assertEqual(len(ids), request['targetPeople'])
            self.assertEqual(len(ids), len(set(ids)))
            plan = json.loads((root / 'release-plan-20261028.json')
                              .read_text(encoding='utf-8'))
            eligible = {
                row['plannedQuestionId']
                for row in plan['selectedNew']
                if row.get('photoStatus') != 'published'
                and row.get('name') != '羅璧玲'
            }
            self.assertTrue(set(ids) <= eligible,
                            'Only unpublished selectedNew IDs may be searched')
            self.assertTrue(all(pid.startswith('t1500_') for pid in ids))
            purpose = request['purpose'].casefold().replace('-', ' ')
            self.assertIn('draft only', purpose)
            self.assertIn('no main', purpose)
            if request['mode'] == 'manual_recrop':
                spec_name = Path(request['manualCropRequestPath']).name
                self.assertTrue(spec_name.startswith('manual-crop-request-'))
                self.assertTrue(spec_name.endswith('.json'))
                spec = json.loads((root / 'pipeline' / spec_name).read_text(encoding='utf-8'))
                self.assertEqual(spec['releaseGate'], 'MANUAL_CROP_STAGING_ONLY_NO_LIVE')
                self.assertEqual([item['personId'] for item in spec['items']], ids)
                self.assertEqual(len(spec['sourceCommit']), 40)
                for item in spec['items']:
                    self.assertEqual(len(item['sourceSha256']), 64)
                    x0, y0, x1, y1 = item['box']
                    self.assertEqual((x1-x0)*6, (y1-y0)*5)



    def test_chen_mingchang_verified_qid_alias_replays_exact_metadata_only(self):
        import sys
        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root))
        from media_pipeline.sources import identity
        plan = json.loads((root / 'release-plan-20261028.json').read_text(
            encoding='utf-8'))
        person = next(row for row in plan['selectedNew']
                      if row['plannedQuestionId'] == 't1500_0107')
        self.assertEqual(person['wikidataId'], 'Q9474720')
        self.assertIn('Chen Ming-chang', person['aliases'])
        self.assertIn('Chen Ming-chang', person['acceptedAnswers'])
        self.assertIn('2022-03-06 Chen Ming-chang 02.jpg',
                      person['reviewExactCommonsFiles'])
        self.assertTrue(person['cachedMetadataRecheckToken'].startswith(
            '20261031-chen-mingchang-q9474720'))
        self.assertIn('Chen Ming-chang', identity(
            person, '2022-03-06 Chen Ming-chang 02.jpg'))
        self.assertEqual(identity(person, 'Chen Ming-changson unrelated'), [])
        self.assertFalse(person['imageVerification']['finalCropReviewed'])
        self.assertNotEqual(person['photoStatus'], 'published')


    def test_exact_qid_p18_source_may_be_retained_for_manual_crop_only(self):
        import sys
        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root))
        from media_pipeline.core import verified_curated_p18_manual_source
        plan = json.loads((root / 'release-plan-20261028.json').read_text(
            encoding='utf-8'))
        person = next(row for row in plan['selectedNew']
                      if row['plannedQuestionId'] == 't1500_0107')
        self.assertEqual(person['reviewVerifiedP18File'],
                         '2022-03-06 Chen Ming-chang 02.jpg')
        source = 'https://commons.wikimedia.org/wiki/File:2022-03-06_Chen_Ming-chang_02.jpg'
        item = {'filename': person['reviewVerifiedP18File'],
                'source': source}
        evidence = {'curatedExactFileHint': True}
        self.assertTrue(verified_curated_p18_manual_source(
            person, item, evidence))
        self.assertFalse(verified_curated_p18_manual_source(
            person, {**item, 'filename': '2022-03-06 Chen Ming-chang 01.jpg'}, evidence))
        self.assertFalse(verified_curated_p18_manual_source(
            person, {**item, 'source': 'https://example.org/' + item['filename']}, evidence))
        self.assertFalse(verified_curated_p18_manual_source(
            person, item, {'curatedExactFileHint': False}))
        self.assertFalse(verified_curated_p18_manual_source(
            {**person, 'wikidataId': None}, item, evidence))
        self.assertFalse(person['imageVerification']['finalCropReviewed'])
        self.assertIn('https://commons.wikimedia.org/wiki/File:2022-03-06_Chen_Ming-chang_01.jpg',
                      person['excludedPhotoSources'])
        self.assertIn('https://commons.wikimedia.org/wiki/File:2022-03-06_Chen_Ming-chang_02.jpg',
                      person['excludedPhotoSources'])
        self.assertNotIn('https://commons.wikimedia.org/wiki/File:2023_TTXC高雄電影節-陳明章.jpg',
                         person['excludedPhotoSources'])


    def test_dayuan_and_huanghongxuan_exact_leads_stay_draft_only(self):
        root = Path(__file__).resolve().parents[1]
        plan = json.loads((root / 'release-plan-20261028.json').read_text(
            encoding='utf-8'))
        people = {row['plannedQuestionId']: row for row in plan['selectedNew']}
        for person_id, filename, rejected in (
            ('t1500_0475', 'LinDaYuan.jpg',
             'https://commons.wikimedia.org/wiki/File:Lin_DaYuan_from_Popu_Lady.jpg'),
            ('t1500_0534', '台灣演員黃宏軒的形象照，攝於2024年.jpg',
             'https://commons.wikimedia.org/wiki/File:S_37822478.jpg'),
        ):
            row = people[person_id]
            self.assertIn(filename, row['reviewExactCommonsFiles'])
            self.assertIn(rejected, row['excludedPhotoSources'])
            if row.get('photoStatus') == 'published':
                # A previously staged exact-source lead may now be genuinely
                # live after its independent five-stage and Pages QA.
                self.assertTrue(row['imageVerification']['finalCropReviewed'])
                self.assertTrue(row['imageVerification']['rightsDocumented'])
                self.assertEqual(row['qaStatus'], 'pages_live_verified')
            else:
                self.assertEqual(row['qaStatus'], 'not_releasable')
                self.assertFalse(row['imageVerification']['finalCropReviewed'])
                self.assertFalse(row['imageVerification']['rightsDocumented'])

    def test_source_screening_records_no_approved_game_crop(self):
        root = Path(__file__).resolve().parents[1]
        report = json.loads((root / 'pipeline' / 'chatgpt-review' /
                             '20261030-source-led-visual-and-rights-screening.json')
                            .read_text(encoding='utf-8'))
        self.assertEqual(report['approvalGate'], 'no candidates approved for live')
        self.assertEqual(len(report['records']), 8)
        self.assertTrue(all(row['decision'] != 'approved_for_live'
                            for row in report['records']))


if __name__ == '__main__':
    unittest.main()
