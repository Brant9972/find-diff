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
        self.assertIn('Eric Kot', person['acceptedAnswers'])
        self.assertEqual(person['reviewExactCommonsFiles'], [
            'Eric Kot 20231029.jpg', 'Eric Kot 200812.JPG'])
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
        self.assertEqual(request['plannedPersonIds'], ['t1500_0564'])
        self.assertEqual(request['targetPeople'], 1)
        self.assertEqual(request['mode'], 'search')
        self.assertEqual(request['providers'], ['entity', 'commons'])
        self.assertIn('five reveal stages', request['purpose'])
        self.assertIn('No old cohort rerun', request['purpose'])


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
