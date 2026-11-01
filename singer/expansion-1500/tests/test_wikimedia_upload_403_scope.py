"""A denied Commons thumbnail must not poison other files on the upload host."""
import unittest
import urllib.error
from unittest.mock import patch
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.sources import HTTP, SourceError


class Response:
    headers = {'Content-Length': '4'}

    def __init__(self):
        self.sent = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _size):
        if self.sent:
            return b''
        self.sent = True
        return b'JPEG'


class FakeOpener:
    def __init__(self, denied, status=403):
        self.denied = denied
        self.status = status
        self.calls = []

    def open(self, request, timeout=None):
        url = request.full_url
        self.calls.append(url)
        if url == self.denied:
            raise urllib.error.HTTPError(url, self.status, 'denied', {}, None)
        return Response()


class WikimediaUploadRefusalTest(unittest.TestCase):
    def test_one_thumbnail_403_does_not_block_other_images_or_original(self):
        bad = 'https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/photo.jpg/1400px-photo.jpg'
        good = 'https://upload.wikimedia.org/wikipedia/commons/thumb/b/bc/other.jpg/1400px-other.jpg'
        original = 'https://upload.wikimedia.org/wikipedia/commons/a/ab/photo.jpg'
        opener = FakeOpener(bad)
        client = HTTP(attempts=1, interval=0, timeout=5)
        with patch('media_pipeline.sources.urllib.request.build_opener', return_value=opener):
            with self.assertRaises(SourceError) as first:
                client.get(bad)
            self.assertEqual(first.exception.code, 'http_403')
            self.assertEqual(client.get(good), b'JPEG')
            self.assertEqual(client.get(original, allow_wikimedia_original_retry=True), b'JPEG')
            with self.assertRaises(SourceError) as repeated:
                client.get(bad)
            self.assertEqual(repeated.exception.code, 'http_403')
        self.assertEqual(opener.calls, [bad, good, original])
        self.assertNotIn('upload.wikimedia.org', client.blocked_hosts)

    def test_429_remains_host_wide_for_wikimedia(self):
        bad = 'https://upload.wikimedia.org/wikipedia/commons/thumb/a/bad.jpg'
        good = 'https://upload.wikimedia.org/wikipedia/commons/thumb/b/good.jpg'
        opener = FakeOpener(bad, 429)
        client = HTTP(attempts=1, interval=0, timeout=5)
        with patch('media_pipeline.sources.urllib.request.build_opener', return_value=opener):
            with self.assertRaises(SourceError) as first:
                client.get(bad)
            self.assertEqual(first.exception.code, 'http_429')
            with self.assertRaises(SourceError) as second:
                client.get(good)
            self.assertEqual(second.exception.code, 'http_429')
        self.assertEqual(opener.calls, [bad])

    def test_non_wikimedia_403_remains_host_wide(self):
        bad = 'https://example.org/bad.jpg'
        good = 'https://example.org/good.jpg'
        opener = FakeOpener(bad)
        client = HTTP(attempts=1, interval=0, timeout=5)
        with patch('media_pipeline.sources.urllib.request.build_opener', return_value=opener):
            with self.assertRaises(SourceError):
                client.get(bad)
            with self.assertRaises(SourceError) as second:
                client.get(good)
            self.assertEqual(second.exception.code, 'http_403')
        self.assertEqual(opener.calls, [bad])


if __name__ == '__main__':
    unittest.main()
