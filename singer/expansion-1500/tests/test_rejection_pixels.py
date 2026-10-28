import copy
import io
import random
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.rejection_pixels import matches_rejected, rejected_fingerprints


def picture(seed=1):
    rng = random.Random(seed)
    image = Image.new('RGB', (600, 720), '#8ca8b3')
    draw = ImageDraw.Draw(image)
    for i in range(50):
        x, y = rng.randrange(560), rng.randrange(680)
        color = tuple(rng.randrange(30, 230) for _ in range(3))
        draw.ellipse((x, y, x + rng.randrange(15, 90), y + rng.randrange(15, 90)), fill=color)
    draw.rectangle((170, 140, 430, 570), outline='#48372a', width=12)
    draw.line((210, 220, 380, 270), fill='#211f2b', width=15)
    return image


def jpeg(image, quality=95):
    stream = io.BytesIO()
    image.save(stream, 'JPEG', quality=quality)
    return stream.getvalue()


class RejectionPixelsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.game = self.root / 'game.jpg'
        self.game.write_bytes(jpeg(picture()))
        self.state = {'people': {'p1': {'candidates': [{'id': 'rejected1', 'status': 'rejected', 'gamePath': 'game.jpg'}]}}}

    def tearDown(self):
        self.temp.cleanup()

    def test_jpeg_reencoding_and_proportional_resize_match(self):
        hashes = rejected_fingerprints(self.root, self.state)
        self.assertEqual(len(hashes), 1)
        source = Image.open(io.BytesIO(self.game.read_bytes())).convert('RGB')
        for size, quality in [((600, 720), 70), ((300, 360), 80), ((1200, 1440), 85)]:
            variant = jpeg(source.resize(size, Image.Resampling.LANCZOS), quality)
            self.assertTrue(matches_rejected(variant, hashes), (size, quality))

    def test_different_picture_not_matched(self):
        hashes = rejected_fingerprints(self.root, self.state)
        self.assertFalse(matches_rejected(jpeg(picture(42)), hashes))
        # Same luminance layout recoloured substantially is also not strong same-pixel evidence.
        recolored = picture().convert('RGB')
        red, green, blue = recolored.split()
        recolored = Image.merge('RGB', (blue, red, green))
        self.assertFalse(matches_rejected(jpeg(recolored), hashes))

    def test_pending_approved_published_and_superseded_are_ignored(self):
        for status in ['pending_review', 'pending_evidence', 'approved', 'published', 'superseded', 'metadata_only']:
            self.state['people']['p1']['candidates'][0]['status'] = status
            self.assertEqual(rejected_fingerprints(self.root, self.state), [], status)

    def test_source_image_is_included_and_state_is_unchanged(self):
        other = self.root / 'source.jpg'
        other.write_bytes(jpeg(picture(42)))
        self.state['people']['p1']['candidates'][0]['originalPath'] = 'source.jpg'
        before = copy.deepcopy(self.state)
        hashes = rejected_fingerprints(self.root, self.state)
        self.assertTrue(matches_rejected(other.read_bytes(), hashes))
        self.assertEqual(before, self.state)
        self.assertEqual(self.game.read_bytes(), jpeg(picture()))

    def test_corrupt_missing_escaping_and_flat_images_do_not_stop_batch(self):
        self.state['people']['p1']['candidates'].extend([
            {'status': 'rejected', 'gamePath': 'missing.jpg'},
            {'status': 'rejected', 'gamePath': '../outside.jpg'},
            {'status': 'rejected', 'gamePath': 'bad.jpg'}])
        (self.root / 'bad.jpg').write_bytes(b'not a photo')
        hashes = rejected_fingerprints(self.root, self.state)
        self.assertEqual(len(hashes), 1)
        self.assertFalse(matches_rejected(b'broken new image', hashes))
        self.assertFalse(matches_rejected(jpeg(Image.new('RGB', (600, 720), 'white')), hashes))


if __name__ == '__main__':
    unittest.main()
