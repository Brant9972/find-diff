"""Audit retained original bytes before requesting a new manual crop.

The source must never be re-downloaded merely because a newer curated metadata
record exists. This test checks the saved bytes against the original SHA256 and
prints a compact diagnostic for an actual reviewer to select crop geometry.
"""
import hashlib
import json
import unittest
from pathlib import Path

SINGER = Path(__file__).resolve().parents[2]
STATE = SINGER / "expansion-1500" / "pipeline" / "state.json"
PERSON_ID = "t1500_0562"


class RetainedCheungSourceIntegrityTest(unittest.TestCase):
    def test_retained_original_is_immutable_and_not_approved(self):
        state = json.loads(STATE.read_text(encoding="utf-8"))
        person = state["people"][PERSON_ID]
        retained = [
            item for item in person.get("candidates", [])
            if item.get("originalPath")
            and "張達明.jpg" in (item.get("filename", "") + item.get("source", ""))
        ]
        self.assertTrue(retained, "Expected the already-retained Commons 張達明 original")
        for item in retained:
            raw = SINGER / item["originalPath"]
            self.assertTrue(raw.is_file(), f"Retained source missing: {raw}")
            digest = hashlib.sha256(raw.read_bytes()).hexdigest()
            self.assertEqual(digest, item["originalSha256"])
            self.assertFalse(item.get("eligibleForLive", False))
            diagnostic = {
                "personId": PERSON_ID, "candidateId": item["id"],
                "status": item.get("status"), "source": item.get("source"),
                "originalPath": item["originalPath"],
                "originalSha256": digest,
                "validation": item.get("validation"),
                "cropFailure": item.get("cropFailure"),
                "warnings": item.get("warnings", []),
            }
            print("CHEUNG_RETAINED_SOURCE " +
                  json.dumps(diagnostic, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    unittest.main()
