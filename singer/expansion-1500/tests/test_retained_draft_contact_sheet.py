"""Offline safety tests for retained-draft contact sheet export."""
import json
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from retained_draft_contact_sheet import build, stage_tile


class RetainedDraftContactSheetTests(unittest.TestCase):
    def test_masks_outside_reveal_rectangle(self):
        tile = stage_tile(Image.new("RGB", (600, 720), (240, 100, 20)),
                          [0.1, 0.3, 0.9, 0.5])
        self.assertEqual(tile.getpixel((0, 0)), (22, 22, 22))
        self.assertEqual(tile.getpixel((75, 72)), (240, 100, 20))
        with self.assertRaises(ValueError):
            stage_tile(Image.new("RGB", (600, 720)), [0.5, 0.5, 0.2, 0.8])

    def test_draft_only_skips_live_and_excluded_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root/"expansion-1500"
            (folder/"review_photos").mkdir(parents=True)
            plan = {"selectedNew": [
                {"plannedQuestionId": "t1500_0001", "excludedPhotoSources": []},
                {"plannedQuestionId": "t1500_0002", "excludedPhotoSources": ["https://commons.wikimedia.org/wiki/File:bad.jpg"]},
                {"plannedQuestionId": "t1500_0003", "excludedPhotoSources": []},
            ]}
            (folder/"release-plan-20261028.json").write_text(json.dumps(plan), encoding="utf-8")
            reveal = {s: ([0, 0, 1, 1] if s == "full" else [0.08, 0.3, 0.92, 0.45])
                      for s in ("eyes", "nose", "mouth", "chin", "full")}
            items = []
            for n, source in ((1, "good.jpg"), (2, "bad.jpg"), (3, "live.jpg")):
                pid = f"t1500_{n:04d}"
                Image.new("RGB", (600, 720), (n*50, 80, 120)).save(folder/"review_photos"/(pid+".jpg"))
                items.append({"questionId": pid, "name": pid, "reviewStatus": "draft_not_verified",
                              "source": "https://commons.wikimedia.org/wiki/File:"+source,
                              "draftPhoto": "expansion-1500/review_photos/"+pid+".jpg",
                              "revealDraft": reveal})
            (folder/"draft-media-index.json").write_text(json.dumps({"items": items}), encoding="utf-8")
            for bank in ("questions.json", "actors.json", "variety.json"):
                (root/bank).write_text(json.dumps({"questions": [{"id": "t1500_0003"}] if bank == "actors.json" else []}), encoding="utf-8")
            result = build(root, root/"expansion-1500/pipeline/review-assets/retained")
            self.assertEqual([x["personId"] for x in result["people"]], ["t1500_0001"])
            self.assertEqual({x["reason"] for x in result["skipped"]},
                             {"source_previously_excluded", "not_selected_or_already_live"})
            self.assertTrue((root/"expansion-1500/pipeline/review-assets/retained/contact-sheet.png").is_file())
            self.assertEqual(result["people"][0]["reviewStatus"], "VISUAL_SCREENING_REQUIRED_NOT_APPROVED")
            # A pipeline branch can lag behind main: fetched main, not local banks,
            # must decide whether a portrait is already published.
            def git_read(cmd, text=True):
                if cmd[-2:] == ["rev-parse", "origin/main"]:
                    return "a"*40+"\n"
                if cmd[-1] == "origin/main:singer/questions.json":
                    return json.dumps({"questions": [{"id": "t1500_0001"}, {"id": "t1500_0003"}]})
                return json.dumps({"questions": []})
            with mock.patch("retained_draft_contact_sheet.subprocess.check_output", side_effect=git_read):
                current = build(root, root/"expansion-1500/pipeline/review-assets/live-ref", live_ref="origin/main")
            self.assertEqual(current["summary"]["screeningRows"], 0)
            self.assertEqual(current["baselineLiveSha"], "a"*40)
            self.assertIn("not_selected_or_already_live", {x["reason"] for x in current["skipped"]})


if __name__ == "__main__":
    unittest.main()
