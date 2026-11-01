"""A previously human-rejected source is not a fresh exact Commons lead."""
import json
import unittest
from pathlib import Path
from urllib.parse import quote


class LinYuzhongSourceLeadTest(unittest.TestCase):
    def test_rejected_exact_lead_is_excluded_not_retried(self):
        root = Path(__file__).resolve().parents[1]
        plan = json.loads((root / 'release-plan-20261028.json').read_text(encoding='utf-8'))
        row = next(p for p in plan['selectedNew'] if p['plannedQuestionId'] == 't1500_0388')
        self.assertEqual(row['name'], '林宇中')
        self.assertNotIn('林宇中.JPG', row.get('reviewExactCommonsFiles', []))
        self.assertIn('https://commons.wikimedia.org/wiki/File:' + quote('林宇中.JPG'),
                      row['excludedPhotoSources'])
        self.assertIn('photo-review.json', row['reviewSourceResearchNote'])
        self.assertEqual(row['photoStatus'], 'not_prepared')
        self.assertFalse(row['imageVerification']['rightsDocumented'])
        self.assertFalse(row['imageVerification']['finalCropReviewed'])
        self.assertEqual(row['qaStatus'], 'not_releasable')


if __name__ == '__main__':
    unittest.main()
