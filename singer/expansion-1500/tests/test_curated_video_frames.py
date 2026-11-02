"""Regression guards for opt-in video frame research; no network or image approval."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "curated_video_frames.py"
spec = importlib.util.spec_from_file_location("curated_video_frames", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CuratedVideoFrameResearchTests(unittest.TestCase):
    def test_only_exact_curated_unpublished_lead(self):
        lead = module.select_lead("t1500_0094")
        self.assertEqual(lead["name"], "寇世勳")
        self.assertFalse(lead["picturedIdentityConfirmed"])
        with self.assertRaises(ValueError):
            module.select_lead("t1500_9999")

    def test_cdn_allowlist(self):
        self.assertTrue(module.allowed_video_url(
            "https://upload.wikimedia.org/wikipedia/commons/5/53/example.webm"))
        for url in (
            "http://upload.wikimedia.org/wikipedia/commons/5/53/a.webm",
            "https://upload.wikimedia.org.evil.com/wikipedia/commons/a.webm",
            "https://commons.wikimedia.org/wiki/File:example.webm",
            "https://upload.wikimedia.org/wikipedia/commons/a.jpg",
            "https://upload.wikimedia.org@evil.example/wikipedia/commons/a.webm",
            "https://upload.wikimedia.org/wikipedia/en/a.webm",
        ):
            with self.subTest(url=url):
                self.assertFalse(module.allowed_video_url(url))

    def test_exact_file_metadata_only(self):
        lead = module.select_lead("t1500_0094")
        title = "File:大囍臨門賀歲 豬哥亮首映圍爐.webm"
        good = "https://upload.wikimedia.org/wikipedia/commons/5/53/example.webm"
        class Response:
            def __init__(self, page):
                self.page = page
            def raise_for_status(self):
                pass
            def json(self):
                return {"query": {"pages": {"12": self.page}}}
        with patch.object(module.requests, "get", return_value=Response({
            "title": title, "videoinfo": [{"url": good, "size": 1024}]})):
            self.assertEqual(module.commons_video_url(lead), good)
        for page in (
            {"title": "File:Wrong.webm", "videoinfo": [{"url": good, "size": 1024}]},
            {"title": title, "videoinfo": [{"url": good, "size": module.MAX_BYTES + 1}]},
            {"title": title, "videoinfo": [{"url": "https://evil.example/a.webm", "size": 1024}]},
        ):
            with self.subTest(page=page):
                with patch.object(module.requests, "get", return_value=Response(page)):
                    with self.assertRaises(ValueError):
                        module.commons_video_url(lead)

    def test_research_only_manifest_without_game_photo(self):
        # Mock ffprobe/ffmpeg while creating valid tiny JPEG frames.
        from PIL import Image
        lead = module.select_lead("t1500_0094")
        class Completed:
            stdout = json.dumps({"format": {"duration": "75.0"},
                                 "streams": [{"width": 1920, "height": 1080}]})
        def fake_run(cmd, **kwargs):
            if cmd[0] == "ffmpeg":
                Image.new("RGB", (640, 360), "white").save(cmd[-1])
            return Completed()
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            video = base / "source.webm"
            video.write_bytes(b"test-bytes-not-a-real-video")
            with patch.object(module.subprocess, "run", side_effect=fake_run):
                manifest = module.extract_frames(video, base, lead, "LOCAL_TEST_ONLY")
            self.assertEqual(len(manifest["frames"]), 4)
            self.assertEqual(manifest["releaseGate"], "RESEARCH_ONLY_NOT_APPROVED_NOT_PLAYABLE")
            self.assertFalse(manifest["picturedIdentityConfirmed"])
            self.assertFalse(manifest["eligibleForLive"])
            self.assertFalse(manifest["fiveStagesReviewed"])
            self.assertNotIn("gameSha256", manifest)
            self.assertTrue((base / "contact-sheet.jpg").is_file())


if __name__ == "__main__":
    unittest.main()
