"""Fail-closed regression for an acknowledged live-photo rights gap.

This is a metadata guard, NOT independent rights/identity or visual approval.
It permits the known legacy hold to remain visible while preventing another
unlicensed t1500_ photo from being silently introduced.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "media_pipeline"))
from audit_expansion_release import BANKS, OPEN  # noqa: E402

LEGACY_ID = "t1500_0095"
LEGACY_SOURCE = (
    "https://p7.itc.cn/images01/20220815/"
    "f88933f4f0174b10a5517bcff201c946.jpeg"
)
LEGACY_PHOTO = "photos/t1500_0095.jpg"


class KnownLiveRightsHoldTest(unittest.TestCase):
    def test_no_new_unlicensed_expansion_portraits_or_false_clearance(self):
        banks = {
            bank: json.loads((ROOT.parent / bank).read_text(encoding="utf-8"))["questions"]
            for bank in BANKS
        }
        expansion = [
            (bank, row) for bank in BANKS for row in banks[bank]
            if str(row.get("id", "")).startswith("t1500_")
        ]
        unlicensed = [
            (bank, row) for bank, row in expansion
            if not OPEN.fullmatch(str((row.get("attribution") or {}).get("license") or "").strip())
        ]
        # Existing exception is a BLOCKER, not an approved photograph.
        # If a replacement is independently reviewed, the exception can disappear.
        self.assertTrue(all(
            bank == "actors.json"
            and row.get("id") == LEGACY_ID
            and row.get("photo") == LEGACY_PHOTO
            and (row.get("attribution") or {}).get("source") == LEGACY_SOURCE
            and row.get("humanReviewed") is not True
            for bank, row in unlicensed
        ), "A new t1500_ entry lacks a declared open license; hold publication.")

        matching = [
            row for bank, row in expansion
            if bank == "actors.json" and row.get("id") == LEGACY_ID
        ]
        self.assertEqual(len(matching), 1)
        row = matching[0]
        attribution = row.get("attribution") or {}
        if attribution.get("source") == LEGACY_SOURCE:
            # Never 'fix' rights by merely changing the metadata label.
            self.assertEqual(row.get("photo"), LEGACY_PHOTO)
            self.assertFalse(OPEN.fullmatch(str(attribution.get("license") or "").strip()))
            self.assertIsNot(row.get("humanReviewed"), True)
        else:
            # Metadata-only minimum; still requires independent source/pixel
            # review, SHA, five-stage visual QA, branch QA and Pages QA.
            self.assertNotEqual(row.get("photo"), LEGACY_PHOTO)
            self.assertTrue(OPEN.fullmatch(str(attribution.get("license") or "").strip()))
            self.assertTrue(attribution.get("source"))
            self.assertTrue(attribution.get("artist"))
            self.assertTrue(attribution.get("licenseUrl"))
            self.assertIs(row.get("humanReviewed"), True)


if __name__ == "__main__":
    unittest.main()
