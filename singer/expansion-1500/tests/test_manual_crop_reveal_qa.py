"""Regression for visually reviewed HK manual crop stages (not identity/rights approval)."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUEST = ROOT / "pipeline" / "manual-crop-request-20261030-hk.json"


class HKManualRevealTest(unittest.TestCase):
    def test_huang_haoran_nose_does_not_pre_reveal_mouth(self):
        data = json.loads(REQUEST.read_text(encoding="utf-8"))
        person = next(item for item in data["items"] if item["personId"] == "t1500_0579")
        reveal = person["reveal"]
        self.assertEqual(reveal["full"], [0, 0, 1, 1])
        self.assertLessEqual(reveal["eyes"][3], 0.36)
        self.assertLessEqual(reveal["nose"][3], 0.44)
        self.assertGreaterEqual(reveal["mouth"][3], 0.50)
        self.assertGreaterEqual(reveal["chin"][3], 0.60)
        for earlier, later in zip(("eyes", "nose", "mouth"), ("nose", "mouth", "chin")):
            self.assertLess(reveal[earlier][3], reveal[later][3])
            self.assertEqual(reveal[earlier][:3], reveal[later][:3])
        self.assertEqual(data["releaseGate"], "MANUAL_CROP_STAGING_ONLY_NO_LIVE")


if __name__ == "__main__":
    unittest.main()
