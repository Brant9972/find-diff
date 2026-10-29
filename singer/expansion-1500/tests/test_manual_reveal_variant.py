"""Manual recrop must not silently skip changed five-stage masks for identical JPEG pixels."""
import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.manual_recrop_from_commit import stage_manual_recrops


class ManualRevealVariantTest(unittest.TestCase):
    def test_same_photo_new_reveal_creates_new_draft_and_preserves_old_previews(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "singer"
            directory = root / "expansion-1500" / "pipeline"
            image = Image.new("RGB", (120, 144), "#9f8871")
            out = io.BytesIO()
            image.save(out, "JPEG")
            raw = out.getvalue()
            digest = hashlib.sha256(raw).hexdigest()
            source = {
                "id": "source1", "status": "manual_crop_required",
                "rightsStatus": "open_license_metadata",
                "originalSha256": digest,
                "originalPath": "expansion-1500/pipeline/assets/t1/source1/original.bin",
                "eligibleForLive": False,
            }
            source_state = {"people": {"t1": {"name": "Test Person", "candidates": [source]}}}
            state = {"people": {"t1": {"name": "Test Person", "personId": "t1",
                                      "status": "manual_crop_required", "candidates": []}}}
            reveal_a = {k: [.08, .2, .92, y] for k, y in
                        [("eyes", .34), ("nose", .50), ("mouth", .62), ("chin", .76)]}
            reveal_a["full"] = [0, 0, 1, 1]
            reveal_b = copy.deepcopy(reveal_a)
            reveal_b["nose"][3] = .43
            request = {"schemaVersion": 1, "releaseGate": "MANUAL_CROP_STAGING_ONLY_NO_LIVE",
                       "sourceCommit": "a" * 40, "items": [{
                           "personId": "t1", "sourceCandidateId": "source1",
                           "sourceSha256": digest, "box": [0, 0, 120, 144],
                           "reveal": reveal_a}]}

            def git_file(commit, path):
                if path.endswith("state.json"):
                    return json.dumps(source_state).encode()
                return raw

            with patch("tools.manual_recrop_from_commit._git_file", side_effect=git_file):
                self.assertEqual(stage_manual_recrops(root, directory, state, request, "run1", set()), ["t1"])
                old = next(c for c in state["people"]["t1"]["candidates"]
                           if c["status"] == "pending_review")
                old_id = old["id"]
                old_nose = Path(root / old["stagePreviews"]["nose"])
                old_bytes = old_nose.read_bytes()
                request["items"][0]["reveal"] = reveal_b
                self.assertEqual(stage_manual_recrops(root, directory, state, request, "run2", set()), ["t1"])
                new = next(c for c in state["people"]["t1"]["candidates"]
                           if c["status"] == "pending_review")
                self.assertNotEqual(old_id, new["id"])
                self.assertEqual(old["status"], "superseded")
                self.assertEqual(old["supersededBy"], new["id"])
                self.assertEqual(old["gameSha256"], new["gameSha256"])
                self.assertNotEqual(old["stagePreviews"]["nose"], new["stagePreviews"]["nose"])
                self.assertEqual(old_nose.read_bytes(), old_bytes)
                self.assertNotEqual(old_bytes, (root / new["stagePreviews"]["nose"]).read_bytes())
                self.assertEqual(stage_manual_recrops(root, directory, state, request, "run3", set()), [])
                self.assertFalse(new["eligibleForLive"])


if __name__ == "__main__":
    unittest.main()
