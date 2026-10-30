"""Backup searches are draft-only and limited to the existing 2026-10-28 roster."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from prepare_media import load_preselected_backup_search_people


class PreselectedBackupSearchTest(unittest.TestCase):
    def test_real_lead_is_from_existing_backup_and_not_published(self):
        people = load_preselected_backup_search_people(ROOT.parent)
        self.assertEqual(list(people), ['t1500_0604'])
        person = people['t1500_0604']
        self.assertEqual(person['candidateId'], 'c1500-0604')
        self.assertEqual(person['name'], '潘親御')
        self.assertEqual(person['purpose'], 'backup')
        self.assertEqual(person['proposedPrimaryBank'], 'actors.json')
        self.assertEqual(person['reviewExactCommonsFiles'],
                         ['潘親御演員.jpg', '潘親御演員照.jpg'])
        self.assertTrue(person['backupSearchOnly'])
        self.assertEqual(person['qaStatus'], 'not_releasable')
        self.assertEqual(person['photoStatus'], 'not_prepared')
        plan = json.loads((ROOT / 'release-plan-20261028.json').read_text())
        self.assertEqual(len(plan['selectedNew']), 511)
        self.assertNotIn('t1500_0604', {p['plannedQuestionId'] for p in plan['selectedNew']})

    def test_unlisted_or_renamed_person_and_unsafe_filename_fail_closed(self):
        original = {'candidates': [{'candidateId': 'c1500-0604', 'name': '潘親御',
                                    'purpose': 'backup', 'photoStatus': 'not_prepared'}]}
        reviewed = {'candidates': [{'candidateId': 'c1500-0604', 'name': '潘親御',
                                    'proposedBank': 'actors.json'}]}
        lead = {'candidateId': 'c1500-0604', 'plannedQuestionId': 't1500_0604',
                'name': '潘親御', 'proposedPrimaryBank': 'actors.json',
                'reviewExactCommonsFiles': ['潘親御演員.jpg']}
        def check(row):
            def fake_read(path, default=None):
                name = Path(path).name
                if name == 'backup-photo-leads-20261030.json':
                    return {'releaseGate': 'BACKUP_PHOTO_SEARCH_ONLY_NOT_PLAYABLE',
                            'people': [row]}
                if name == 'taiwan-first-candidates-20261028.json':
                    return original
                if name == 'backup-eligibility-review-20261029.json':
                    return reviewed
                raise AssertionError(name)
            with patch('prepare_media.read', side_effect=fake_read):
                return load_preselected_backup_search_people(ROOT.parent)
        self.assertIn('t1500_0604', check(lead))
        for changed in ({**lead, 'name': '同名錯誤人物'},
                        {**lead, 'candidateId': 'c1500-0999'},
                        {**lead, 'reviewExactCommonsFiles': ['../private.jpg']},
                        {**lead, 'reviewExactCommonsFiles': ['bad\\\\path.jpg']}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                check(changed)


if __name__ == '__main__':
    unittest.main()
