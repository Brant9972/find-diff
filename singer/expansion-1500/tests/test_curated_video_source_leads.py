"""Keep source-only Commons video leads out of the playable photo pipeline.

Video stills are an opt-in research route, not a substitute for an approved
600x720 JPEG, verified source/identity, or five-stage human inspection.
"""
import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
LEADS = ROOT / "pipeline" / "curated-video-source-leads-20261102.json"


class CuratedVideoSourceLeadsTest(unittest.TestCase):
    def test_video_source_leads_are_research_only(self):
        data = json.loads(LEADS.read_text(encoding="utf-8"))
        self.assertEqual(data["releaseGate"], "SOURCE_RESEARCH_ONLY_NO_DOWNLOAD_NO_CROP_NO_LIVE")
        self.assertTrue(data["people"])
        for lead in data["people"]:
            with self.subTest(person=lead["personId"]):
                self.assertTrue(lead["personId"].startswith("t1500_"))
                self.assertEqual(urlsplit(lead["commonsSourcePage"]).hostname, "commons.wikimedia.org")
                self.assertTrue(lead["commonsSourcePage"].endswith(".webm"))
                self.assertEqual(lead["mediaProperties"]["type"], "video/webm")
                self.assertTrue(lead["status"].startswith("HOLD_"))
                self.assertFalse(lead["alreadyLive"])
                self.assertFalse(lead["sourceFrameDownloaded"])
                self.assertFalse(lead["picturedIdentityConfirmed"])
                self.assertFalse(lead["frameAuthorAndLicenseIndependentlyApproved"])
                self.assertFalse(lead["gameCrop600x720"])
                self.assertFalse(lead["fiveStagesReviewed"])
                self.assertIsNone(lead["gameSha256"])
                self.assertIsNone(lead["frameTimecode"])
                self.assertNotIn("photo", lead)
                self.assertNotIn("reveal", lead)
                self.assertNotIn("approvedForLive", lead)


if __name__ == "__main__":
    unittest.main()
