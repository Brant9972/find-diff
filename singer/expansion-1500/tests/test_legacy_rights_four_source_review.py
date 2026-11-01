"""Regression guard for 2026-11-01 source-only legacy portrait screening.

This deliberately does NOT certify a portrait or authorize a live release.
"""
import json
import unittest
from pathlib import Path


REVIEW = (Path(__file__).resolve().parents[1] / "pipeline" / "chatgpt-review" /
          "20261101-legacy-rights-four-commons-visual.json")


class LegacyRightsFourSourceReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = json.loads(REVIEW.read_text(encoding="utf-8"))

    def test_source_evidence_cannot_be_construed_as_game_approval(self):
        record = self.record
        self.assertEqual(record["releaseGate"], "EVIDENCE_ONLY_NO_PRODUCTION_APPROVAL")
        self.assertEqual(record["scope"]["newGameCropsApproved"], 0)
        self.assertEqual(record["scope"]["productionChanges"], 0)
        self.assertEqual(len(record["decisions"]), 4)
        self.assertEqual(record["scope"]["affectedBankEntries"], 8)
        for entry in record["decisions"]:
            self.assertIs(entry["eligibleForLive"], False)
            self.assertIs(entry["actualImageViewed"], True)
            self.assertEqual(len(entry["existingIds"]), 2)
            self.assertTrue(entry["commonsPage"].startswith("https://commons.wikimedia.org/wiki/File:"))
            self.assertTrue(entry["licenseUrl"].startswith("https://creativecommons.org/licenses/"))
            self.assertTrue(entry["nextAction"])

    def test_precise_pending_and_rejection_decisions(self):
        by_name = {item["name"]: item for item in self.record["decisions"]}
        self.assertEqual(len(by_name), 4)
        self.assertEqual(by_name["吳建豪"]["decision"], "priority_manual_crop_and_five_stage_review")
        for name in ("劉若英", "張衛健", "李麗珍"):
            self.assertTrue(by_name[name]["decision"].startswith("reject_exact_source"))
        self.assertIn("License review needed", by_name["李麗珍"]["licenseReview"])
        self.assertIn("YouTubeReviewBot", by_name["張衛健"]["licenseReview"])
        self.assertEqual(by_name["吳建豪"]["sourceDimensions"], [2304, 3072])


if __name__ == "__main__":
    unittest.main()
