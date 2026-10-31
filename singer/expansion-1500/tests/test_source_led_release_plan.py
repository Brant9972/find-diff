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
            # The one explicit post-fix replay is permitted only for two
            # known sources after the retained-original cap bug was fixed.
            self.assertEqual(
                request['requestId'],
                '20261031-excluded-old-original-retention-fix-two')
            self.assertEqual(
                request['plannedPersonIds'], ['t1500_0475', 't1500_0534'])
            self.assertEqual(request['providers'], ['commons'])
            self.assertIn('retention fix', request['purpose'].casefold())
        else:
            self.assertFalse(request['retryFailed'])
        self.assertIn(request['mode'], ('render_only', 'search', 'manual_recrop'))
        ids = request['plannedPersonIds']
        if request['mode'] == 'render_only':
            self.assertEqual(ids, [])
            self.assertEqual(request['targetPeople'], 0)
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
