"""Keep new identity leads distinct from approved game portraits."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ThreeQidSourceLeadsTest(unittest.TestCase):
    def test_exact_identities_are_search_leads_only(self):
        plan = json.loads((ROOT / 'release-plan-20261028.json').read_text(encoding='utf-8'))
        people = {p['plannedQuestionId']: p for p in plan['selectedNew']}
        expected = {
            't1500_0093': ('郭品超', 'Q710553', 'Dylan Kuo'),
            't1500_0092': ('江祖平', 'Q8975739', 'Amigo Chiang'),
            't1500_0094': ('寇世勳', 'Q8980013', 'Johnny Kou'),
        }
        for pid, (name, qid, alias) in expected.items():
            with self.subTest(person=pid):
                p = people[pid]
                self.assertEqual(p['name'], name)
                self.assertEqual(p['wikidataId'], qid)
                self.assertIn(alias, p['aliases'])
                self.assertIn(alias, p['acceptedAnswers'])
                self.assertNotEqual(p['photoStatus'], 'published')
                self.assertFalse(p['imageVerification']['finalCropReviewed'])
                self.assertFalse(p['imageVerification']['rightsDocumented'])
                self.assertFalse(p.get('reviewVerifiedOriginalSources'))

    def test_previous_zhao_is_released_and_not_requeued(self):
        plan = json.loads((ROOT / 'release-plan-20261028.json').read_text(encoding='utf-8'))
        request = json.loads((ROOT / 'pipeline/batch-request.json').read_text(encoding='utf-8'))
        zhao = next(p for p in plan['selectedNew'] if p['plannedQuestionId'] == 't1500_0102')
        self.assertEqual(zhao['photoStatus'], 'published')
        # Release counts must advance as new people are actually deployed;
        # never freeze a historical milestone in a source-lead regression.
        self.assertGreaterEqual(plan['arithmetic']['currentlyLiveUnique'], 1077)
        self.assertGreaterEqual(plan['releaseProgress']['published'], 90)
        self.assertNotIn('t1500_0102', request['plannedPersonIds'])


if __name__ == '__main__':
    unittest.main()
