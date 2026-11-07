"""Align transparent character sheets without modifying the sources."""

import argparse
from itertools import groupby
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter

from settings import (
    ARMED_ANIMATION_ROWS, ARMED_CHARACTER_SOURCE, ARMED_FRAME_ROWS, CHARACTER_SOURCE, CHARACTER_FRAME_ROWS,
    FRAME_BOTTOM_PADDING, FRAME_COUNT, FRAME_HEIGHT, FRAME_ROWS, FRAME_WIDTH, WEAPON_HAND_OFFSETS,
)

ROOT = Path(__file__).resolve().parents[1]


def prepare_right_hand_overlay(sheet, output):
    """Extract an opaque right fist and its outline to occlude held weapons."""
    overlay = Image.new("RGBA", sheet.size)
    for state, row in ARMED_ANIMATION_ROWS.items():
        for column, (hand_x, hand_y) in enumerate(WEAPON_HAND_OFFSETS[state]):
            origin_x, origin_y = column * FRAME_WIDTH, row * FRAME_HEIGHT
            seed = (origin_x + FRAME_WIDTH // 2 + hand_x,
                    origin_y + FRAME_HEIGHT - FRAME_BOTTOM_PADDING - hand_y)

            def is_skin(point):
                x, y = point
                if not (origin_x <= x < origin_x + FRAME_WIDTH and origin_y <= y < origin_y + FRAME_HEIGHT):
                    return False
                r, g, b, a = sheet.getpixel(point)
                return a >= 128 and r > 150 and r > g + 12 and g > b + 8

            if not is_skin(seed):
                raise ValueError(f"Right-hand anchor is not on the fist: {state} {column}")
            seen, pending = {seed}, [seed]
            while pending:
                x, y = pending.pop()
                for point in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if point not in seen and is_skin(point):
                        seen.add(point)
                        pending.append(point)
            mask = Image.new("L", (FRAME_WIDTH, FRAME_HEIGHT))
            for x, y in seen:
                mask.putpixel((x - origin_x, y - origin_y), 255)
            # Include the dark outline around the fingers, not just the skin.
            # A thin/partly transparent overlay lets the pipe show through.
            mask = mask.filter(ImageFilter.MaxFilter(7))
            box = (origin_x, origin_y, origin_x + FRAME_WIDTH, origin_y + FRAME_HEIGHT)
            fist = sheet.crop(box)
            visible = fist.getchannel("A").point(lambda alpha: 255 if alpha >= 128 else 0)
            fist.putalpha(ImageChops.multiply(mask, visible))
            overlay.paste(fist, (origin_x, origin_y), fist.getchannel("A"))
    overlay.save(output)


def prepare(source=ROOT / CHARACTER_SOURCE, output=ROOT / "assets/character.png", preview=False,
            rows=CHARACTER_FRAME_ROWS, hand_overlay=False):
    with Image.open(source) as original:
        sheet = original.convert("RGBA")
    if sheet.size != (FRAME_COUNT * FRAME_WIDTH, rows * FRAME_HEIGHT):
        raise ValueError(f"Sprite sheet must contain 8 by {rows} cells of 256 by 256 pixels")
    if sheet.getchannel("A").getextrema()[0] != 0:
        raise ValueError("The new sprite sheet must have a transparent background")
    width, height = FRAME_WIDTH, FRAME_HEIGHT
    source_sheet = sheet.copy()
    bands = {}
    if rows > FRAME_ROWS:
        # Split five-row player sheets at transparent gaps so jump hoods
        # crossing a nominal row boundary remain in their own silhouette.
        for column in range(FRAME_COUNT):
            alpha = source_sheet.crop((column * width, 0, (column + 1) * width, sheet.height)).getchannel("A")
            alpha = alpha.point(lambda value: 255 if value >= 128 else 0)
            occupied = [y for y in range(sheet.height) if alpha.crop((0, y, width, y + 1)).getbbox()]
            spans = [list(group) for _, group in groupby(enumerate(occupied), lambda pair: pair[1] - pair[0])]
            if len(spans) != rows:
                raise ValueError(f"Expected {rows} separated silhouettes in column {column}")
            bands[column] = [(span[0][1], span[-1][1] + 1) for span in spans]
    for row in range(rows):
        for column in range(FRAME_COUNT):
            box = (column * width, row * height, (column + 1) * width, (row + 1) * height)
            if bands:
                top, bottom = bands[column][row]
                frame = source_sheet.crop((column * width, top, (column + 1) * width, bottom))
            else:
                frame = source_sheet.crop(box)
            # Almost invisible matte remnants must not determine the frame anchor.
            frame.putalpha(frame.getchannel("A").point(lambda alpha: alpha if alpha >= 128 else 0))
            bounds = frame.getbbox()
            if bounds is None:
                raise ValueError(f"No character remained at row {row}, column {column}")
            sprite = frame.crop(bounds)
            aligned = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            aligned.paste(sprite, (
                (width - sprite.width) // 2,
                height - FRAME_BOTTOM_PADDING - sprite.height,
            ))
            sheet.paste(aligned, box)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    if hand_overlay:
        prepare_right_hand_overlay(sheet, output.with_name(f"{output.stem}_right_hand.png"))
    print(f"Prepared {output}: {sheet.width}x{sheet.height}, cells {width}x{height}")
    if preview:
        preview_path = ROOT / f"artifacts/{output.stem}-preview.png"
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        canvas = Image.new("RGBA", sheet.size, (52, 95, 125, 255))
        canvas.alpha_composite(sheet)
        canvas.save(preview_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--armed", action="store_true", help="Prepare the five-state weaponless sheet")
    args = parser.parse_args()
    if args.armed:
        prepare(ROOT / ARMED_CHARACTER_SOURCE, ROOT / "assets/armed_character.png",
                preview=args.preview, rows=ARMED_FRAME_ROWS, hand_overlay=True)
    else:
        prepare(preview=args.preview)
