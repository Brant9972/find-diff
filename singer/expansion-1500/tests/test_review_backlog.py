import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.review_backlog import BANKS, build_queue

SHA = 'a' * 40


def item(id, name, license='CC BY-SA 4.0', reviewed=False, source='https://commons.wikimedia.org/wiki/File:A.jpg'):
    return {'id': id, 'name': name, 'photo': f'photos/{id}.jpg',
            'humanReviewed': reviewed, 'visualReviewedByAI': True,
            'attribution': {'license': license, 'source': source, 'artist': 'A'}}


class ReviewBacklogTest(unittest.TestCase):
    def test_rights_blocker_first_and_no_automatic_approval(self):
        banks = {b: [] for b in BANKS}
        banks['questions.json'] = [item('t1500_0001', '已核准', reviewed=True),
                                   item('t1500_0002', '待補人審')]
        banks['actors.json'] = [item('t1500_0003', '無授權', license='Copyright retained by original rights holders', source='https://example.com/image.jpg')]
        banks['variety.json'] = [item('x1000_01', '舊題')]
        report = build_queue(banks, SHA)
        self.assertEqual(report['summary']['expansionEntries'], 3)
        self.assertEqual(report['summary']['needsEvidenceOrRightsReconciliation'], 2)
        self.assertEqual(report['summary']['rightsBlockers'], 1)
        self.assertEqual(report['summary']['missingHumanReviewFlag'], 2)
        self.assertEqual([x['id'] for x in report['people']], ['t1500_0003', 't1500_0002'])
        self.assertIn('non_commons_source_verify_rights', report['people'][0]['issues'])
        self.assertFalse(report['people'][0]['approvedForRelease'])
        self.assertEqual(report['people'][1]['fiveStageNames'], ['eyes', 'nose', 'mouth', 'chin', 'full'])
        self.assertEqual(report['releaseGate'], 'AUDIT_ONLY_NO_APPROVAL')

    def test_flagged_reviewed_but_no_open_license_is_still_blocked(self):
        banks = {b: [] for b in BANKS}
        banks['actors.json'] = [item('t1500_0095', '金超群', 'Copyright retained', True)]
        report = build_queue(banks, SHA)
        self.assertEqual(report['summary']['rightsBlockers'], 1)
        self.assertEqual(report['summary'].get('missingHumanReviewFlag', 0), 0)

    def test_duplicate_ids_rejected_even_across_banks(self):
        banks = {b: [] for b in BANKS}
        banks['questions.json'] = [item('t1500_0010', '甲')]
        banks['actors.json'] = [item('t1500_0010', '乙')]
        with self.assertRaisesRegex(ValueError, 'duplicate expansion ID'):
            build_queue(banks, SHA)

    def test_invalid_sha_and_missing_name_rejected(self):
        banks = {b: [] for b in BANKS}
        with self.assertRaises(ValueError):
            build_queue(banks, 'main')
        banks['questions.json'] = [item('t1500_0001', '')]
        with self.assertRaisesRegex(ValueError, 'missing name'):
            build_queue(banks, SHA)


if __name__ == '__main__':
    unittest.main()
