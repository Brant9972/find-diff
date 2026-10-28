"""Conservative same-image rejection across JPEG encodings and proportional resizes.
Fingerprints are ephemeral, contain no identity decisions, and never mutate review state.
"""
import io
from pathlib import Path
from PIL import Image, ImageOps


MAX_IMAGE_PIXELS = 30_000_000
MAX_IMAGE_BYTES = 14_000_000


def _fingerprint(blob):
    if not blob or len(blob) > MAX_IMAGE_BYTES:
        return None
    try:
        with Image.open(io.BytesIO(blob)) as source:
            if min(source.size) < 32 or source.width * source.height > MAX_IMAGE_PIXELS:
                return None
            image = ImageOps.exif_transpose(source).convert('RGB')
            gray = image.convert('L')
            horizontal = gray.resize((17, 8), Image.Resampling.LANCZOS).tobytes()
            vertical = gray.resize((8, 17), Image.Resampling.LANCZOS).tobytes()
            bits = 0
            for y in range(8):
                for x in range(16):
                    bits = (bits << 1) | (horizontal[y * 17 + x] > horizontal[y * 17 + x + 1])
            for y in range(16):
                for x in range(8):
                    bits = (bits << 1) | (vertical[y * 8 + x] > vertical[(y + 1) * 8 + x])
            # Flat colour/gradient layouts cannot establish same-photo evidence.
            blocks = {(bits >> shift) & 0xffff for shift in range(0, 256, 16)}
            if len(blocks) < 4 or not 24 <= bits.bit_count() <= 232:
                return None
            return {'dhash': bits, 'aspect': image.width / image.height,
                    'thumbnail': image.resize((32, 32), Image.Resampling.LANCZOS).tobytes()}
    except (OSError, ValueError, Image.DecompressionBombError):
        # A damaged old rejection must not prevent unrelated people from being searched.
        return None


def rejected_fingerprints(root, state):
    """Return game/source fingerprints for explicitly rejected candidates only.

    Matching uses a 256-bit horizontal+vertical dHash, near-identical RGB pixels,
    and the same aspect ratio. Pending, approved, superseded and metadata-only
    records are ignored. No source file or state field is changed.
    """
    root = Path(root).resolve()
    fingerprints, seen = [], set()
    for row in state.get('people', {}).values():
        for candidate in row.get('candidates', []):
            if candidate.get('status') != 'rejected':
                continue
            for key in ('gamePath', 'originalPath'):
                relative = candidate.get(key)
                if not isinstance(relative, str):
                    continue
                try:
                    image = (root / relative).resolve()
                    if not image.is_relative_to(root) or image in seen or not image.is_file() or image.stat().st_size > MAX_IMAGE_BYTES:
                        continue
                    seen.add(image)
                    value = _fingerprint(image.read_bytes())
                    if value is not None:
                        fingerprints.append(value)
                except OSError:
                    continue
    return fingerprints


def matches_rejected(blob, hashes):
    """True only for strongly matching pixels, never merely a similar person's face.

    A match requires dHash Hamming distance <=4/256, aspect ratio difference
    <=1.5%, RGB thumbnail mean absolute difference <=4 and a 95th percentile
    channel difference <=12. This intentionally favours false negatives over
    rejecting a different photograph with a similar pose or background.
    """
    query = _fingerprint(blob)
    if query is None:
        return False
    for previous in hashes:
        if abs(query['aspect'] / previous['aspect'] - 1) > .015:
            continue
        if (query['dhash'] ^ previous['dhash']).bit_count() > 4:
            continue
        differences = [abs(a - b) for a, b in zip(query['thumbnail'], previous['thumbnail'])]
        if len(differences) != 3072 or sum(differences) / len(differences) > 4:
            continue
        if sorted(differences)[int(len(differences) * .95)] > 12:
            continue
        return True
    return False
