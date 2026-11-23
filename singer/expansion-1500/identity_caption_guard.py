#!/usr/bin/env python3
"""Conservative identity-caption preflight for expansion-1500 image candidates.

This is a fail-closed *screen*, not a replacement for source, license, QID,
or visual review. Run: python3 -m unittest discover -s singer/expansion-1500/tests
"""
import re
import unicodedata


def normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value or "").casefold().strip()


def caption_mentions_identity(caption: str, names: list[str]) -> bool:
    """Never accept a short CJK name merely as a substring of a longer name.

    The function only says whether a caption has an unambiguous textual name
    mention. It does NOT prove which face in a group photo is the subject.
    """
    caption = normalize(caption)
    for raw_name in names:
        name = normalize(raw_name)
        if len(name) < 2:
            continue
        for match in re.finditer(re.escape(name), caption):
            left = caption[match.start() - 1] if match.start() else ""
            right = caption[match.end()] if match.end() < len(caption) else ""
            if (left and (left.isalnum() or left == "_")) or (
                right and (right.isalnum() or right == "_")
            ):
                continue
            return True
    return False


def eligible_for_identity_review(caption: str, names: list[str],
                                 expected_qid: str = "",
                                 source_qid: str = "") -> bool:
    """Reject explicit QID mismatch, then require a bounded name mention."""
    if expected_qid and source_qid and expected_qid != source_qid:
        return False
    return caption_mentions_identity(caption, names)
