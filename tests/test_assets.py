import hashlib
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from resources import ROOT
from settings import CHARACTER_SOURCE, FRAME_BOTTOM_PADDING, FRAME_HEIGHT, FRAME_ROWS, FRAME_WIDTH
from tools.prepare_character import prepare


class AssetTests(unittest.TestCase):
    def test_all_frames_have_stable_visible_bounds(self):
        with Image.open(ROOT / "assets/character.png") as sheet:
            self.assertEqual(sheet.size, (2048, 1024))
            for row in range(FRAME_ROWS):
                for column in range(8):
                    with self.subTest(row=row, column=column):
                        frame = sheet.crop((column * FRAME_WIDTH, row * FRAME_HEIGHT,
                                            (column + 1) * FRAME_WIDTH, (row + 1) * FRAME_HEIGHT))
                        left, top, right, bottom = frame.getbbox()
                        self.assertLessEqual(abs((left + right) / 2 - FRAME_WIDTH / 2), 0.5)
                        self.assertEqual(bottom, FRAME_HEIGHT - FRAME_BOTTOM_PADDING)
                        self.assertGreater(top, 0)
                        self.assertEqual(frame.getpixel((0, 0))[3], 0)

    def test_invisible_remnants_cannot_change_alignment(self):
        with Image.open(ROOT / "assets/character.png") as sheet:
            alpha = sheet.getchannel("A")
            visible = alpha.point(lambda value: 255 if value >= 128 else 0)
            self.assertEqual(alpha.getbbox(), visible.getbbox())
            self.assertEqual(sum(alpha.histogram()[1:128]), 0)

    def test_generation_is_reproducible_and_preserves_source(self):
        source = ROOT / CHARACTER_SOURCE
        original_hash = hashlib.sha256(source.read_bytes()).digest()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "character.png"
            prepare(output=output)
            self.assertEqual(output.read_bytes(), (ROOT / "assets/character.png").read_bytes())
        self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), original_hash)
