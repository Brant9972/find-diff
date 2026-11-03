"""Offline tests for bounded curated Commons original download and provisional previews."""
import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "tools"))
import curated_still_original as diag

URL = "https://upload.wikimedia.org/wikipedia/commons/9/99/Jade_Kwan_2019.jpg"


class FakeResponse:
    def __init__(self, url=URL, status=200, data=b"test", headers=None):
        self.url = url
        self.status_code = status
        self.data = data
        self.headers = headers or {}
        self.closed = False

    def iter_content(self, chunk_size=65536):
        yield self.data

    def close(self):
        self.closed = True


class CuratedStillOriginalTest(unittest.TestCase):
    def test_curated_source_is_manual_only(self):
        """Metadata-only commits and PR QA must never trigger a remote original fetch."""
        workflow = (ROOT.parent.parent / ".github/workflows/curated-still-original-diagnostic.yml").read_text(encoding="utf-8")
        self.assertNotIn("\\n  push:\\n", workflow)
        self.assertIn("  workflow_dispatch:", workflow)
        self.assertIn("  pull_request:", workflow)
        self.assertIn("if: github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/automation/celebrity-photo-pipeline'", workflow)

    def test_only_pinned_wikimedia_original_host_and_path(self):
        self.assertTrue(diag.allowed_original_url(URL))
        for bad in [
            "http://upload.wikimedia.org/wikipedia/commons/9/99/a.jpg",
            "https://example.com/wikipedia/commons/9/99/a.jpg",
            "https://upload.wikimedia.org.evil.example/wikipedia/commons/a.jpg",
            "https://upload.wikimedia.org/wikipedia/en/a.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/a.jpg?redirect=https://evil.test",
            "https://upload.wikimedia.org/wikipedia/commons/a.png",
        ]:
            with self.subTest(bad=bad):
                self.assertFalse(diag.allowed_original_url(bad))

    def test_sha_size_and_redirect_integrity(self):
        data = b"original source bytes"
        session = Mock()
        response = FakeResponse(data=data)
        session.get.return_value = response
        got = diag.fetch_exact(URL, len(data), hashlib.sha1(data).hexdigest(), session=session)
        self.assertEqual(got, data)
        self.assertTrue(response.closed)
        with self.assertRaisesRegex(ValueError, "SHA-1 mismatch"):
            diag.fetch_exact(URL, len(data), "0" * 40, session=session)
        with self.assertRaisesRegex(ValueError, "size mismatch"):
            diag.fetch_exact(URL, len(data) + 1, hashlib.sha1(data).hexdigest(), session=session)
        session.get.return_value = FakeResponse(url="https://example.com/photo.jpg", data=data)
        with self.assertRaisesRegex(ValueError, "Untrusted download redirect"):
            diag.fetch_exact(URL, len(data), hashlib.sha1(data).hexdigest(), session=session)

    def test_403_stops_without_retries(self):
        session = Mock()
        session.get.return_value = FakeResponse(status=403)
        with self.assertRaisesRegex(RuntimeError, "source_http_403"):
            diag.fetch_exact(URL, 4, "0" * 40, session=session)
        self.assertEqual(session.get.call_count, 1)

    def test_rate_limit_does_not_immediately_retry_and_retains_server_cooldown(self):
        for code, cooldown in [(429, "7200"), (503, "Wed, 04 Nov 2026 00:00:00 GMT")]:
            with self.subTest(code=code):
                session = Mock()
                response = FakeResponse(status=code, headers={"Retry-After": cooldown})
                session.get.return_value = response
                with self.assertRaises(diag.SourceHTTPError) as caught:
                    diag.fetch_exact(URL, 4, "0" * 40, session=session)
                self.assertEqual(str(caught.exception), f"source_http_{code}")
                self.assertEqual(caught.exception.retry_after, cooldown)
                self.assertEqual(session.get.call_count, 1)
                self.assertTrue(response.closed)

    def test_rate_limit_manifest_is_not_approval_and_records_retry_after(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(diag, "fetch_exact", side_effect=diag.SourceHTTPError(429, "3600")):
                result = diag.run(Path(tmp))
            self.assertEqual(result["status"], "source_blocked")
            self.assertEqual(result["error"], "source_http_429")
            self.assertEqual(result["retryAfterHeader"], "3600")
            self.assertEqual(result["retryPolicy"], "no_immediate_retry_wait_for_source_cooldown")
            self.assertFalse(result["humanReviewed"])
            self.assertFalse(result["liveUpdated"])
            self.assertFalse(result["rightsAndIdentityFinalApproval"])
            self.assertEqual(result, __import__("json").loads((Path(tmp) / "manifest.json").read_text(encoding="utf-8")))

    def test_preview_is_not_an_approval(self):
        original = Image.new("RGB", (100, 120), (130, 120, 100))
        buf = io.BytesIO()
        original.save(buf, format="JPEG")
        lead = {"imageDimensions": [100, 120], "provisionalOriginalPixelCropBox": [10, 10, 60, 70]}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            result = diag.build_previews(buf.getvalue(), lead, out)
            self.assertTrue(result["stageMasksProvisional"])
            self.assertEqual(result["fiveStages"], ["eyes", "nose", "mouth", "chin", "full"])
            with Image.open(out / "draft-600x720.jpg") as crop:
                self.assertEqual(crop.size, (600, 720))
            with Image.open(out / "contact-sheet.jpg") as sheet:
                self.assertEqual(sheet.size, (1200, 330))

    def test_yang_lihua_pinned_source_is_review_only(self):
        """The right-side subject can be isolated without including left-side pixels."""
        original = Image.new("RGB", (1280, 1920), (32, 35, 38))
        from PIL import ImageDraw
        ImageDraw.Draw(original).rectangle((0, 0, 629, 1919), fill=(240, 20, 20))
        buf = io.BytesIO()
        original.save(buf, format="JPEG", quality=95)
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(diag, "fetch_exact", return_value=buf.getvalue()) as fetch:
                result = diag.run(Path(tmp), lead_path=diag.YANG_LEAD)
            self.assertEqual(result["status"], "download_verified_provisional_crop_created")
            self.assertEqual(result["personId"], "t1500_0273")
            self.assertFalse(result["humanReviewed"])
            self.assertFalse(result["rightsAndIdentityFinalApproval"])
            self.assertFalse(result["liveUpdated"])
            self.assertEqual(result["cropBox"], [690, 330, 1090, 810])
            self.assertTrue(result["customStageMasks"])
            self.assertEqual(result["stageRects"]["nose"], [0.08, 0.38, 0.92, 0.55])
            self.assertEqual(fetch.call_args.args[1], 324913)
            self.assertEqual(fetch.call_args.args[2], "176c36fcd5a039936b7f2b31bbdc6da10fd5b7a3")
            with Image.open(Path(tmp) / "draft-600x720.jpg") as photo:
                self.assertEqual(photo.size, (600, 720))
                self.assertLess(photo.getpixel((0, 360))[0], 100)

    def test_arbitrary_source_lead_cannot_be_injected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "not allowlisted"):
                diag.run(Path(tmp), lead_path=Path(tmp) / "external.json")

    def test_default_reveal_rectangles_match_actual_singer_game(self):
        """A review montage must not show more of the face than the live game."""
        import ast
        import re
        game = (ROOT.parent / "game.js").read_text(encoding="utf-8")
        match = re.search(r"\|\|(\[\[.*?\]\])\[state\.stage\]", game)
        self.assertIsNotNone(match, "Singer game reveal fallback missing")
        self.assertEqual(
            [list(rect) for rect in diag.STAGES.values()],
            ast.literal_eval(match.group(1)),
        )

    def test_reject_nonmonotonic_custom_stage_rectangles(self):
        img = Image.new("RGB", (100, 120), (20, 20, 20))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        masks = {name: list(rect) for name, rect in diag.STAGES.items()}
        masks["nose"] = [0.08, 0.275, 0.92, 0.4]
        lead = {
            "imageDimensions": [100, 120],
            "provisionalOriginalPixelCropBox": [10, 10, 60, 70],
            "provisionalReveal": masks,
        }
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "monotonically expanding"):
                diag.build_previews(buf.getvalue(), lead, Path(tmp))

    def test_verified_original_bytes_can_be_reused_without_network(self):
        data = b"sha-bound source original"
        digest = hashlib.sha1(data).hexdigest()
        self.assertEqual(diag.verify_exact_bytes(data, len(data), digest), data)
        with self.assertRaisesRegex(ValueError, "SHA-1 mismatch"):
            diag.verify_exact_bytes(data, len(data), "0" * 40)
        with self.assertRaisesRegex(ValueError, "size mismatch"):
            diag.verify_exact_bytes(data, len(data) + 1, digest)
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / "source.jpg"
            original.write_bytes(data)
            out = Path(tmp) / "review"
            with patch.object(diag, "fetch_exact") as fetch, \
                 patch.object(diag, "verify_exact_bytes", return_value=data) as verify, \
                 patch.object(diag, "build_previews", return_value={"cropSha256": "test"}):
                result = diag.run(out, lead_path=diag.YANG_LEAD, source_file=original)
            fetch.assert_not_called()
            verify.assert_called_once()
            self.assertEqual((out / "original-sha1-verified.jpg").read_bytes(), data)
            self.assertEqual(result["sourceRetrieval"], "sha_verified_local_reuse")
            self.assertFalse(result["humanReviewed"])
            self.assertFalse(result["liveUpdated"])


if __name__ == "__main__":
    unittest.main()
