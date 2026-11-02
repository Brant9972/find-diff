"""Offline tests for bounded curated Commons original download and provisional previews."""
import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "tools"))
import curated_still_original as diag

URL = "https://upload.wikimedia.org/wikipedia/commons/9/99/Jade_Kwan_2019.jpg"


class FakeResponse:
    def __init__(self, url=URL, status=200, data=b"test"):
        self.url = url
        self.status_code = status
        self.data = data
        self.closed = False

    def iter_content(self, chunk_size=65536):
        yield self.data

    def close(self):
        self.closed = True


class CuratedStillOriginalTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
