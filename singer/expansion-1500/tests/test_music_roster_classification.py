"""Regression guard for music artists misassigned to the actor question bank.

This checks staging metadata only; it does not approve photos or publish questions.
"""
import json
import unittest
from pathlib import Path


PLAN = Path(__file__).resolve().parents[1] / "release-plan-20261028.json"
MUSIC_IDS = {
    "t1500_0276": "HOW",
    "t1500_0277": "完美小姐",
    "t1500_0278": "無與倫比的美麗",
    "t1500_0279": "壞米仔",
    "t1500_0280": "美感 Harateng no Pangcah",
    "t1500_0281": "無與倫比的美麗",
    "t1500_0282": "VAIVAIK尋走",
}


class MusicRosterClassificationTests(unittest.TestCase):
    def test_music_artists_have_singer_category_and_bank(self):
        data = json.loads(PLAN.read_text(encoding="utf-8"))
        selected = {row["plannedQuestionId"]: row for row in data["selectedNew"]}
        for person_id, expected_work in MUSIC_IDS.items():
            with self.subTest(person_id=person_id):
                row = selected[person_id]
                self.assertEqual(row["categories"], ["歌手"])
                self.assertEqual(row["proposedPrimaryBank"], "questions.json")
                self.assertIn(expected_work, row["representativeWorks"])
                self.assertTrue(row["acceptedAnswers"])
                self.assertEqual(row["plannedQuestionId"], person_id)


if __name__ == "__main__":
    unittest.main()
