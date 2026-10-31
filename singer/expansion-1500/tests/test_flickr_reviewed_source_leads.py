"""Two Flickr-reviewed Commons source leads remain draft-only until actual pixel review."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FlickrSourceLeadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = json.loads((ROOT / "release-plan-20261028.json").read_text(encoding="utf-8"))
        cls.people = {p["plannedQuestionId"]: p for p in cls.plan["selectedNew"]}

    def test_published_cheung_is_not_searched_again(self):
        row = self.people["t1500_0562"]
        self.assertEqual(row["name"], "張達明")
        self.assertEqual(row["photoStatus"], "published")
        self.assertEqual(row["publishedQuestionId"], "t1500_0562")
        self.assertEqual(row["portraitSource"], "https://commons.wikimedia.org/wiki/File:張達明.jpg")
        self.assertEqual(self.plan["arithmetic"]["currentlyLiveUnique"], 1080)

    def test_precise_licensed_flickr_sources_are_only_discovery_hints(self):
        expected = {
            "t1500_0123": (
                "林慶台",
                '2013 臺灣泰雅族原住民林慶台與萊萊在自由廣場《看見台灣》露天首映會 Premiere of "Beyond Beauty - TAIWAN FROM ABOVE" in the Liberty Square, Taipei, TAIWAN.jpg',
                "https://creativecommons.org/licenses/by/2.0/",
            ),
            "t1500_0154": (
                "李炳輝", "Lee Ping-Huei & Wu Bai 20101127.jpg",
                "https://creativecommons.org/licenses/by-sa/2.0/",
            ),
        }
        for pid, (name, filename, licence) in expected.items():
            with self.subTest(pid=pid):
                row = self.people[pid]
                self.assertEqual(row["name"], name)
                self.assertEqual(row["reviewExactCommonsFiles"], [filename])
                self.assertEqual(row["reviewLicenseUrl"], licence)
                self.assertNotEqual(row["photoStatus"], "published")
                self.assertFalse(row["imageVerification"]["finalCropReviewed"])
                self.assertFalse(row["imageVerification"]["rightsDocumented"])
                self.assertNotEqual(row["qaStatus"], "Pages_live_verified")

    def test_targeted_request_never_changes_production(self):
        req = json.loads((ROOT / "pipeline/batch-request.json").read_text(encoding="utf-8"))
        self.assertEqual(req["plannedPersonIds"], ["t1500_0123", "t1500_0154"])
        self.assertEqual(req["targetPeople"], 2)
        self.assertEqual(req["providers"], ["commons"])
        self.assertIn("Draft only", req["purpose"])
        self.assertIn("do not auto-approve", req["purpose"])


if __name__ == "__main__":
    unittest.main()
