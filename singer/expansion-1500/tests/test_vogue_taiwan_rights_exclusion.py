"""Regression: known Vogue Taiwan rights-disputed screenshots cannot enter expansion search."""
import json
import unittest
from pathlib import Path


class VogueTaiwanRightsExclusionTest(unittest.TestCase):
    def test_lu_yiching_vogue_screenshot_excluded_without_excluding_person(self):
        root = Path(__file__).resolve().parents[1]
        plan = json.loads((root / "release-plan-20261028.json").read_text(encoding="utf-8"))
        person = next(p for p in plan["selectedNew"] if p["plannedQuestionId"] == "t1500_0172")
        self.assertEqual(person["name"], "陸弈靜")
        self.assertNotEqual(person["photoStatus"], "published")
        self.assertIn("https://commons.wikimedia.org/wiki/File:陸弈靜.png", person["excludedPhotoSources"])
        self.assertIn("Vogue Taiwan", person["reviewSourceResearchNote"])
        self.assertFalse(person["imageVerification"]["rightsDocumented"])


if __name__ == "__main__":
    unittest.main()
