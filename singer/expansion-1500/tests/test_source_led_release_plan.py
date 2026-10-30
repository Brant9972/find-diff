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
        self.assertEqual(person['reviewExactCommonsFiles'], [
            'Eric Kot 20231029.jpg', 'Eric Kot 200812.JPG'])
        self.assertEqual(person['qaStatus'], 'not_releasable')
        self.assertFalse(person['imageVerification']['finalCropReviewed'])
        self.assertFalse(person['imageVerification']['rightsDocumented'])

    def test_batch_is_targeted_and_never_claims_approval(self):
        root = Path(__file__).resolve().parents[1]
        request = json.loads((root / 'pipeline' / 'batch-request.json')
                             .read_text(encoding='utf-8'))
        self.assertEqual(request['plannedPersonIds'], ['t1500_0564'])
        self.assertEqual(request['targetPeople'], 1)
        self.assertEqual(request['mode'], 'search')
        self.assertEqual(request['providers'], ['entity', 'commons'])
        self.assertIn('five-stage', request['purpose'])
        self.assertIn('not a blind', request['purpose'])


if __name__ == '__main__':
    unittest.main()
