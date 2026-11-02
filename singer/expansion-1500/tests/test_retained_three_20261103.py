"""SHA-bound retained source review: only exact rejected photographs are blocked.

The selected people remain eligible for future properly licensed, clear portraits.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from media_pipeline.sources import source_key, excluded_commons_keys

REVIEW = ROOT / "pipeline/chatgpt-review/20261103-retained-three-and-jade2019-source-screen.json"
LEAD = ROOT / "pipeline/curated-jade-kwan-highres-lead-20261102.json"
PLAN = ROOT / "release-plan-20261028.json"
PHOTO = ROOT.parent / "photo-review.json"


class RetainedThree20261103Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = json.loads(REVIEW.read_text(encoding="utf-8"))
        cls.people = {p["plannedQuestionId"]: p for p in json.loads(PLAN.read_text(encoding="utf-8"))["selectedNew"]}
        cls.photo = json.loads(PHOTO.read_text(encoding="utf-8"))

    def test_no_unreviewed_person_is_released(self):
        self.assertEqual(self.audit["releaseGate"], "SOURCE_SCREENING_ONLY_NOT_PLAYABLE")
        self.assertEqual(self.audit["summary"], {
            "peopleScreened": 3,
            "exactSourcesRejected": 3,
            "exactSourcesHeld": 1,
            "approvedForGame": 0,
        })
        self.assertEqual(len(self.audit["decisions"]), 4)
        for d in self.audit["decisions"]:
            with self.subTest(d=d["source"]):
                self.assertFalse(d["eligibleForLive"])
                self.assertEqual(self.people[d["personId"]]["photoStatus"], "not_prepared")
                self.assertFalse(self.people[d["personId"]]["imageVerification"]["finalCropReviewed"])

    def test_rejected_sources_are_exact_person_scoped(self):
        for d in self.audit["decisions"]:
            person = self.people[d["personId"]]
            key = source_key(d["source"])
            excluded = excluded_commons_keys(person)
            if d["decision"] == "reject_exact_source":
                self.assertIn(key, excluded)
                self.assertTrue(any(
                    r.get("id") == d["personId"] and source_key(r.get("source", "")) == key
                    for r in self.photo["rejected"]
                ))
            else:
                self.assertNotIn(key, excluded)
            self.assertNotIn(
                source_key("https://commons.wikimedia.org/wiki/File:Future_Clear_Original_" + d["personId"] + ".jpg"),
                excluded,
            )

    def test_sha_bound_retained_pixels_and_original_only_lead(self):
        expected = {
            "t1500_0308": "4e036011d507786ecb1556b46121a93c15b8fe4d8d660a63b892f10c06c2b287",
            "t1500_0474": "1975aa1650bd71a00aa2f4d71bf2cbaa0a1d0048b7294de87e02eefb664211e2",
        }
        for d in self.audit["decisions"]:
            if d["personId"] in expected:
                self.assertEqual(d["gameSha256"], expected[d["personId"]])
                self.assertEqual(d["fiveStagesReviewed"], ["eyes", "nose", "mouth", "chin", "full"])
        jade = [d for d in self.audit["decisions"] if d["personId"] == "t1500_0481"]
        self.assertEqual(len(jade), 2)
        old = next(d for d in jade if d["gameSha256"])
        self.assertEqual(old["gameSha256"], "e99faeaff15cd59e4453d7a84f7b841b36fca57e11bc109ef4580a18d5a0faae")
        high = next(d for d in jade if not d["gameSha256"])
        self.assertFalse(high["gameCrop600x720Reviewed"])
        self.assertEqual(high["fiveStagesReviewed"], [])
        lead = json.loads(LEAD.read_text(encoding="utf-8"))
        self.assertEqual(lead["releaseGate"], "REJECTED_EXACT_SOURCE_NOT_PLAYABLE")
        self.assertEqual(lead["sourceOriginalVisualFinding"], "eyes_closed")
        self.assertFalse(lead["gameCrop600x720Reviewed"])
        self.assertFalse(lead["fiveStageReviewed"])



    def test_new_guangzhou_original_is_only_a_highres_lead(self):
        lead = json.loads((ROOT / "pipeline/curated-jade-kwan-guangzhou-2019-lead-20261103.json").read_text(encoding="utf-8"))
        self.assertEqual(lead["personId"], "t1500_0481")
        self.assertEqual(lead["releaseGate"], "HIGH_RES_ORIGINAL_VISUAL_LEAD_NOT_CROPPED_NOT_APPROVED")
        self.assertEqual(lead["imageDimensions"], [4160, 6240])
        self.assertEqual(lead["originalSha1"], "deedf1eae08b911b404149cad9c63d07cc32cf9b")
        self.assertTrue(lead["visualFindings"]["eyesOpen"])
        self.assertTrue(lead["visualFindings"]["mouthVisible"])
        self.assertFalse(lead["originalPixelsDownloadedToPipeline"])
        self.assertFalse(lead["gameCrop600x720Reviewed"])
        self.assertFalse(lead["fiveStageReviewed"])
        self.assertFalse(lead["approvedForGame"])
        self.assertNotIn(source_key(lead["source"]), excluded_commons_keys(self.people["t1500_0481"]))

if __name__ == "__main__":
    unittest.main()
