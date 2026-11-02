"""Align the new transparent four-row sheet without modifying the source."""

import argparse
from pathlib import Path

from PIL import Image

from settings import (
    CHARACTER_SOURCE, FRAME_BOTTOM_PADDING, FRAME_COUNT, FRAME_HEIGHT, FRAME_ROWS, FRAME_WIDTH,
)

ROOT = Path(__file__).resolve().parents[1]


def prepare(source=ROOT / CHARACTER_SOURCE, output=ROOT / "assets/character.png", preview=False):
    with Image.open(source) as original:
        sheet = original.convert("RGBA")
    if sheet.size != (FRAME_COUNT * FRAME_WIDTH, FRAME_ROWS * FRAME_HEIGHT):
        raise ValueError("Sprite sheet must contain 8 by 4 cells of 256 by 256 pixels")
    if sheet.getchannel("A").getextrema()[0] != 0:
        raise ValueError("The new sprite sheet must have a transparent background")
    width, height = FRAME_WIDTH, FRAME_HEIGHT
    for row in range(FRAME_ROWS):
        for column in range(FRAME_COUNT):
            box = (column * width, row * height, (column + 1) * width, (row + 1) * height)
            frame = sheet.crop(box)
            # Almost invisible matte remnants must not determine the frame anchor.
            frame.putalpha(frame.getchannel("A").point(lambda alpha: alpha if alpha >= 128 else 0))
            bounds = frame.getbbox()
            if bounds is None:
                raise ValueError(f"No character remained at row {row}, column {column}")
            sprite = frame.crop(bounds)
            aligned = Image.new("RGBA", frame.size, (0, 0, 0, 0))
            aligned.paste(sprite, (
                (width - sprite.width) // 2,
                height - FRAME_BOTTOM_PADDING - sprite.height,
            ))
            sheet.paste(aligned, box)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    print(f"Prepared {output}: {sheet.width}x{sheet.height}, cells {width}x{height}")
    if preview:
        preview_path = ROOT / "artifacts/character-preview.png"
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        canvas = Image.new("RGBA", sheet.size, (52, 95, 125, 255))
        canvas.alpha_composite(sheet)
        canvas.save(preview_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true")
    prepare(preview=parser.parse_args().preview)
