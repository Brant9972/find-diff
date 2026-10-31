"""Exact Commons source leads must remain draft until full review."""
import json
import unittest
from pathlib import Path


class LinYuzhongSourceLeadTest(unittest.TestCase):
    def test_exact_lead_is_not_an_approval(self):
        root = Path(__file__).resolve().parents[1]
        plan = json.loads((root / 'release-plan-20261028.json').read_text(encoding='utf-8'))
        row = next(p for p in plan['selectedNew'] if p['plannedQuestionId'] == 't1500_0388')
        self.assertEqual(row['name'], '林宇中')
        self.assertIn('林宇中.JPG', row['reviewExactCommonsFiles'])
        self.assertEqual(row['photoStatus'], 'not_prepared')
        self.assertFalse(row['imageVerification']['rightsDocumented'])
        self.assertFalse(row['imageVerification']['finalCropReviewed'])
        self.assertEqual(row['qaStatus'], 'not_releasable')


if __name__ == '__main__':
    unittest.main()
