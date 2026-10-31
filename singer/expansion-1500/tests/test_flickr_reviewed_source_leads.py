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

    def test_historical_flickr_leads_do_not_pin_future_batch_requests(self):
        # These two Flickr sources remain subject to their independent
        # source-specific review, but the ACTIVE batch may legitimately move
        # to a different set of selectedNew people.
        req = json.loads((ROOT / "pipeline/batch-request.json").read_text(encoding="utf-8"))
        self.assertIn(req["mode"], {"search", "render_only", "manual_recrop"})
        if req["mode"] == "search":
            ids = req["plannedPersonIds"]
            self.assertEqual(len(ids), req["targetPeople"])
            self.assertEqual(len(ids), len(set(ids)))
            self.assertTrue(all(pid.startswith("t1500_") for pid in ids))
            self.assertTrue(set(req["providers"]) <= {"curated", "commons", "entity"})
        self.assertIn("draft only", req["purpose"].casefold())
        self.assertIn("no main", req["purpose"].casefold())


    def test_visual_rejections_are_source_specific_and_not_releasable(self):
        report = json.loads((ROOT / "pipeline/chatgpt-review/20261031-flickr-source-visual-screening-41190446979.json").read_text(encoding="utf-8"))
        self.assertEqual(report["releaseGate"], "DRAFT_ONLY_NOT_PLAYABLE")
        self.assertEqual(report["summary"]["approvedForGame"], 0)
        self.assertEqual(report["summary"]["rejectedExactSources"], 2)
        for row in report["decisions"]:
            self.assertFalse(row["eligibleForLive"])
            self.assertFalse(row["fiveStageReviewed"])
            if row["decision"] == "reject_source_as_game_portrait":
                self.assertIn(row["sourcePage"], self.people[row["personId"]]["excludedPhotoSources"])
            else:
                self.assertEqual(row["candidateId"], "d5e1b75b4539fc4f5eb3")
                self.assertEqual(row["decision"], "defer_manual_face_isolation_not_approved")

if __name__ == "__main__":
    unittest.main()
