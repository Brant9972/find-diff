"""Regression tests for the real Commons backoff function embedded in Actions."""
import ast
import pathlib
import unittest
import urllib.error
from unittest.mock import patch

WORKFLOW = pathlib.Path(__file__).resolve().parents[3] / ".github/workflows/expansion-two-portrait-review.yml"


def load_retry():
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("          import json, pathlib, urllib.parse, urllib.request, re,"))
    end = next(i for i in range(start + 1, len(lines)) if lines[i] == "          PY")
    script = "\n".join(line[10:] for line in lines[start:end])
    tree = ast.parse(script)
    func = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "open_with_backoff")
    module = ast.Module(body=[func], type_ignores=[])
    ast.fix_missing_locations(module)
    import urllib.request
    import time
    scope = {"urllib": __import__("urllib"), "headers": {"User-Agent": "test"}, "time": time}
    exec(compile(module, str(WORKFLOW), "exec"), scope)
    return scope["open_with_backoff"]


def error(code, retry_after=None):
    return urllib.error.HTTPError("https://commons.wikimedia.org", code, "test", {"Retry-After": retry_after} if retry_after else {}, None)


class RetryTests(unittest.TestCase):
    def setUp(self):
        self.open = load_retry()

    def test_429_then_success(self):
        with patch("urllib.request.urlopen", side_effect=[error(429, "2"), object()]) as fetch, patch("time.sleep") as sleep:
            self.open("https://commons.wikimedia.org", 10)
        self.assertEqual(fetch.call_count, 2)
        sleep.assert_called_once_with(2)

    def test_503_exhausts_four_attempts(self):
        with patch("urllib.request.urlopen", side_effect=[error(503)] * 4) as fetch, patch("time.sleep") as sleep:
            with self.assertRaises(urllib.error.HTTPError):
                self.open("https://commons.wikimedia.org", 10)
        self.assertEqual(fetch.call_count, 4)
        self.assertEqual(sleep.call_count, 3)

    def test_404_never_retries(self):
        with patch("urllib.request.urlopen", side_effect=error(404)) as fetch, patch("time.sleep") as sleep:
            with self.assertRaises(urllib.error.HTTPError):
                self.open("https://commons.wikimedia.org", 10)
        fetch.assert_called_once()
        sleep.assert_not_called()

    def test_retry_after_capped(self):
        with patch("urllib.request.urlopen", side_effect=[error(429, "999"), object()]), patch("time.sleep") as sleep:
            self.open("https://commons.wikimedia.org", 10)
        sleep.assert_called_once_with(60)


if __name__ == "__main__":
    unittest.main()
