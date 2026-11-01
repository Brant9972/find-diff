"""Offline regression: Wikimedia HTTP 429 must not consume retries or release pixels."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from media_pipeline.legacy_source_stage import stage


class CommonsRateLimitEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = json.loads(
            (ROOT / "pipeline/legacy-portrait-request.json").read_text(encoding="utf-8")
        )

    def test_429_is_fail_fast_with_retry_after_and_no_draft(self):
        response = requests.Response()
        response.status_code = 429
        response.url = "https://upload.wikimedia.org/wikipedia/commons/example.jpg"
        response.headers["Retry-After"] = "3600"
        response._content = b"rate limited"

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with patch("media_pipeline.legacy_source_stage.requests.Session") as session_class:
                session = session_class.return_value
                session.get.return_value = response
                with self.assertRaises(requests.HTTPError):
                    stage(self.request, output)

                session.get.assert_called_once()
                adapters = [call.args[1] for call in session.mount.call_args_list]
                self.assertEqual(len(adapters), 1)
                retry = adapters[0].max_retries
                self.assertNotIn(429, retry.status_forcelist)
                self.assertIn(503, retry.status_forcelist)
                self.assertFalse(retry.respect_retry_after_header)

            evidence = json.loads((output / "staging-failure.json").read_text())
            self.assertEqual(evidence["httpStatus"], 429)
            self.assertEqual(evidence["retryAfter"], "3600")
            self.assertTrue(evidence["rateLimited"])
            self.assertEqual(evidence["retryPolicy"], "wait_for_later_run_no_same_url_retry")
            self.assertTrue(evidence["noOriginalPixelsObtained"])
            self.assertFalse(evidence["eligibleForLive"])
            self.assertFalse((output / "draft-600x720.jpg").exists())
            self.assertFalse((output / "staging-report.json").exists())

    def test_non_429_http_error_is_not_mislabeled_rate_limit(self):
        response = requests.Response()
        response.status_code = 403
        response.url = "https://upload.wikimedia.org/wikipedia/commons/example.jpg"
        response._content = b"forbidden"

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with patch("media_pipeline.legacy_source_stage.requests.Session") as session_class:
                session_class.return_value.get.return_value = response
                with self.assertRaises(requests.HTTPError):
                    stage(self.request, output)
            evidence = json.loads((output / "staging-failure.json").read_text())
            self.assertEqual(evidence["httpStatus"], 403)
            self.assertIsNone(evidence["retryAfter"])
            self.assertFalse(evidence["rateLimited"])
            self.assertEqual(evidence["retryPolicy"], "no_unverified_fallback")


if __name__ == "__main__":
    unittest.main()
