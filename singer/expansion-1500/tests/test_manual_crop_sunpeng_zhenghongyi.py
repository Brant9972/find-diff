"""Draft-only geometry and staged reveal regression for two manually cropped source-only images.

These assertions do NOT certify visual identity, photo license, or human approval.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "pipeline" / "manual-crop-request-20261030-sunpeng-zhenghongyi.json"
BATCH = ROOT / "pipeline" / "batch-request.json"


class ManualCropGeometryTest(unittest.TestCase):
    def test_pinned_sources_and_non_live_gate(self):
        spec = json.loads(SPEC.read_text(encoding="utf-8"))
        batch = json.loads(BATCH.read_text(encoding="utf-8"))
        self.assertEqual(spec["releaseGate"], "MANUAL_CROP_STAGING_ONLY_NO_LIVE")
        self.assertEqual(spec["sourceCommit"], "0bef170ec4f28ccf0d47fffc30548e17a3b45ffc")
        self.assertEqual(batch["mode"], "manual_recrop")
        self.assertEqual(batch["targetPeople"], 2)
        self.assertEqual(batch["manualCropRequestPath"], str(SPEC.relative_to(ROOT.parent.parent)).replace("\\", "/"))
        self.assertEqual(
            {item["personId"] for item in spec["items"]},
            {"t1500_0470", "t1500_0491"},
        )
        for item in spec["items"]:
            self.assertEqual(len(item["sourceSha256"]), 64)
            self.assertEqual(len(item["sourceCandidateId"]), 20)

    def test_exact_five_six_crop_and_progressive_masks(self):
        spec = json.loads(SPEC.read_text(encoding="utf-8"))
        dims = {"t1500_0470": (1920, 1440), "t1500_0491": (1170, 1632)}
        for item in spec["items"]:
            with self.subTest(person=item["personId"]):
                x0, y0, x1, y1 = item["box"]
                width, height = dims[item["personId"]]
                self.assertTrue(0 <= x0 < x1 <= width)
                self.assertTrue(0 <= y0 < y1 <= height)
                self.assertEqual((x1 - x0) * 6, (y1 - y0) * 5)
                reveal = item["reveal"]
                self.assertEqual(reveal["full"], [0, 0, 1, 1])
                prev = 0
                for name in ("eyes", "nose", "mouth", "chin"):
                    left, top, right, bottom = reveal[name]
                    self.assertTrue(0 <= left < right <= 1)
                    self.assertTrue(0 <= top < bottom <= 1)
                    self.assertGreater(bottom, prev)
                    prev = bottom


if __name__ == "__main__":
    unittest.main()
