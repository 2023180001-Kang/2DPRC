import hashlib
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from resources import ROOT
from settings import (
    ARMED_ANIMATION_ROWS, ARMED_CHARACTER_SOURCE, ARMED_FRAME_ROWS, CHARACTER_SOURCE,
    FRAME_BOTTOM_PADDING, FRAME_HEIGHT, FRAME_ROWS, FRAME_WIDTH, WEAPON_HAND_OFFSETS,
)
from tools.prepare_character import prepare


class AssetTests(unittest.TestCase):
    def test_right_fist_overlay_covers_the_grip_without_copying_the_other_hand(self):
        with (Image.open(ROOT / "assets/armed_character.png") as body,
              Image.open(ROOT / "assets/armed_character_right_hand.png") as fists):
            self.assertEqual(fists.size, body.size)
            for state, row in ARMED_ANIMATION_ROWS.items():
                for frame, (hand_x, hand_y) in enumerate(WEAPON_HAND_OFFSETS[state]):
                    with self.subTest(state=state, frame=frame):
                        anchor = (frame * 256 + 128 + hand_x, row * 256 + 244 - hand_y)
                        self.assertEqual(fists.getpixel(anchor), body.getpixel(anchor))
                        crop = fists.crop((frame * 256, row * 256, (frame + 1) * 256, (row + 1) * 256))
                        left, top, right, bottom = crop.getbbox()
                        self.assertLess(right - left, 32)
                        self.assertLess(bottom - top, 32)
            # In the right-facing neutral pose, the old left-hand grip is on
            # the opposite side. Only the near-side right fist is extracted.
            self.assertLess(WEAPON_HAND_OFFSETS["IDLE"][0][0], 0)
            self.assertEqual(fists.getpixel((128 + 27, 244 - 68))[3], 0)

    def test_weapon_grips_are_on_visible_hands_in_every_new_pose(self):
        with Image.open(ROOT / "assets/armed_character.png") as sheet:
            for state, row in ARMED_ANIMATION_ROWS.items():
                for frame, (hand_x, hand_y) in enumerate(WEAPON_HAND_OFFSETS[state]):
                    with self.subTest(state=state, frame=frame):
                        r, g, b, a = sheet.getpixel((frame * 256 + 128 + hand_x,
                                                    row * 256 + 244 - hand_y))
                        self.assertGreaterEqual(a, 128)
                        self.assertGreater(r, g + 12)
                        self.assertGreater(g, b + 8)

    def test_armed_sheet_preserves_every_visible_pixel_including_cross_row_heads(self):
        source = ROOT / ARMED_CHARACTER_SOURCE
        original_hash = hashlib.sha256(source.read_bytes()).digest()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "armed_character.png"
            prepare(source, output, rows=ARMED_FRAME_ROWS)
            self.assertEqual(output.read_bytes(), (ROOT / "assets/armed_character.png").read_bytes())
            self.assertEqual(output.with_name("armed_character_right_hand.png").read_bytes(),
                             (ROOT / "assets/armed_character_right_hand.png").read_bytes())
            with Image.open(source) as original, Image.open(output) as aligned:
                self.assertEqual(aligned.size, (2048, 1280))
                visible = original.getchannel("A").point(lambda value: value if value >= 128 else 0)
                self.assertEqual(visible.histogram(), aligned.getchannel("A").histogram())
                for row in range(5):
                    for column in range(8):
                        frame = aligned.crop((column * 256, row * 256, (column + 1) * 256, (row + 1) * 256))
                        left, top, right, bottom = frame.getbbox()
                        self.assertGreater(top, 0)
                        self.assertEqual(bottom, 256 - FRAME_BOTTOM_PADDING)
                        self.assertLessEqual(abs((left + right) / 2 - 128), 0.5)
        self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), original_hash)

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
