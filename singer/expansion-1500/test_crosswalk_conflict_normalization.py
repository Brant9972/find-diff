#!/usr/bin/env python3
"""Regression: a padded URL cannot bypass a known rejected identity conflict."""
import importlib.util
import pathlib
import sys
import unittest
from unittest.mock import patch

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("evidence_crosswalk", HERE / "evidence_crosswalk.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RejectedSourceNormalizationTest(unittest.TestCase):
    def test_whitespace_padded_conflict_is_not_reused(self):
        rejected_id, rejected_url = next(iter(module.KNOWN_IDENTITY_CONFLICTS))
        plan = {"selectedNew": []}
        live = []
        media = {"items": [
            {"questionId": rejected_id, "source": "  " + rejected_url + "  ",
             "reviewStatus": "pending"},
            {"questionId": rejected_id, "source": "https://example.org/another.jpg",
             "reviewStatus": "pending"},
        ]}
        row = {"id": rejected_id, "status": "NEEDS_MANUAL_PHOTO_LICENSE_HINT_REVIEW",
               "evidenceScore": 0}
        with patch.object(module, "review_queue", return_value=[row]):
            result = module.crosswalk(plan, live, media)
        self.assertEqual(result["candidates"][0]["mediaLeadCount"], 1)
        self.assertEqual(result["candidates"][0]["existingMediaLeads"][0]["source"],
                         "https://example.org/another.jpg")


if __name__ == "__main__":
    unittest.main()
