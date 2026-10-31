"""Only independently reviewed Commons CC-licensed YouTube stills can be curated."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from media_pipeline.sources import CuratedCommons, rights
from media_pipeline.core import process


class ReviewedCommonsYoutubeTest(unittest.TestCase):
    def setUp(self):
        plan = json.loads((ROOT / "release-plan-20261028.json").read_text(encoding="utf-8"))
        self.person = next(row for row in plan["selectedNew"]
                           if row["plannedQuestionId"] == "t1500_0562")
        self.item = self.person["reviewVerifiedOriginalSources"][0]
        self.source = "https://commons.wikimedia.org/wiki/File:張達明.jpg"
        self.original = "https://upload.wikimedia.org/wikipedia/commons/5/59/張達明.jpg"

    def test_exact_reviewed_source_metadata_is_draft_only(self):
        rows = list(CuratedCommons().search(self.person, None))
        self.assertEqual(len(rows), 1)
        item = rows[0]
        self.assertEqual(item["source"], self.source)
        self.assertEqual(item["url"], self.original)
        self.assertEqual(item["artist"], "am730")
        self.assertEqual(item["licenseReviewStatus"], "reviewed")
        self.assertEqual(rights(item), "open_license_metadata")
        self.assertEqual(item["identityEvidence"]["commonsYouTubeLicenseReview"]["reviewer"], "GRuban")
        self.assertFalse(item["identityEvidence"]["visualIdentityVerified"])
        self.assertFalse(self.person["imageVerification"]["finalCropReviewed"])
        self.assertNotEqual(self.person["photoStatus"], "published")

    def test_no_unreviewed_or_misaddressed_youtube_source(self):
        for change in (
            {"sourceType": "unknown"},
            {"sourceType": "uploader_own_work", "verificationUrl": "https://example.org"},
            {"licenseReviewer": ""},
            {"licenseReviewedAt": ""},
            {"licenseReviewedAt": "2020-07-xx"},
            {"license": "CC BY 4.0"},
            {"licenseUrl": "https://creativecommons.org/licenses/by/4.0/"},
            {"originalSourceUrl": "https://youtube.com/watch?v=bad"},
            {"originalSourceUrl": "https://evil.example/watch?v=lUMttVkRH-Y"},
            {"originalSourceUrl": "https://www.youtube.com/watch?v=lUMttVkRH-Y&list=other"},
            {"url": "https://upload.wikimedia.org/wikipedia/commons/5/58/張達明.jpg"},
            {"source": "https://commons.wikimedia.org/wiki/File:Different.jpg"},
            {"caption": "An unrelated celebrity"},
        ):
            with self.subTest(change=change):
                person = dict(self.person)
                person["reviewVerifiedOriginalSources"] = [{**self.item, **change}]
                self.assertEqual(list(CuratedCommons().search(person, None)), [])

    def test_even_a_successful_crop_is_only_pending_review(self):
        row = {"personId": "t1500_0562", "status": "no_suitable_source",
               "attempts": 0, "candidates": [], "history": []}

        class FakeHTTP:
            budget = None
            def get(self, url):
                self.last_url = url
                return b"fixture original bytes"

        def fake_crop(blob):
            return b"fixture 600x720 jpeg", {
                "eyes": [0, 0, 1, .2], "nose": [0, 0, 1, .4],
                "mouth": [0, 0, 1, .6], "chin": [0, 0, 1, .8],
                "full": [0, 0, 1, 1]}, {"size": [600, 720]}

        http = FakeHTTP()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            process(self.person, row, root,
                    root / "singer" / "expansion-1500" / "pipeline",
                    [CuratedCommons()], http, fake_crop, set(),
                    max_candidates=1, max_attempts=2, active={},
                    rejected_pixels=[])
        self.assertEqual(http.last_url, self.original)
        self.assertEqual(len(row["candidates"]), 1)
        self.assertEqual(row["candidates"][0]["status"], "pending_review")
        self.assertFalse(row["candidates"][0]["eligibleForLive"])


if __name__ == "__main__":
    unittest.main()
