"""Protect the corrected 鄭弘儀 manual reveal from the forehead-only regression."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "pipeline/manual-crop-request-20261030-zhenghongyi-v2.json"


class ZhengHongyiRevealV2Test(unittest.TestCase):
    def test_corrected_stages_and_draft_gate(self):
        data = json.loads(SPEC.read_text(encoding="utf-8"))
        self.assertEqual(data["releaseGate"], "MANUAL_CROP_STAGING_ONLY_NO_LIVE")
        self.assertEqual(len(data["items"]), 1)
        item = data["items"][0]
        self.assertEqual(item["personId"], "t1500_0491")
        self.assertEqual(item["box"], [230, 60, 930, 900])
        stages = item["reveal"]
        self.assertEqual(stages["full"], [0, 0, 1, 1])
        self.assertGreaterEqual(stages["eyes"][3], 0.54)
        self.assertGreaterEqual(stages["nose"][3], 0.68)
        self.assertGreaterEqual(stages["mouth"][3], 0.82)
        self.assertGreaterEqual(stages["chin"][3], 0.95)
        for a, b in zip(("eyes", "nose", "mouth"), ("nose", "mouth", "chin")):
            self.assertLess(stages[a][3], stages[b][3])
            self.assertEqual(stages[a][:3], stages[b][:3])


if __name__ == "__main__":
    unittest.main()
