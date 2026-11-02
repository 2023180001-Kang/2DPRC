"""Remove border-connected sheet background without modifying the source."""

from collections import deque
import argparse
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
COLUMNS, ROWS = 8, 3


def prepare(source=ROOT / "MainCharacter.png", output=ROOT / "assets/character.png", preview=False):
    with Image.open(source) as original:
        sheet = original.convert("RGBA")
    if sheet.width % COLUMNS or sheet.height % ROWS:
        raise ValueError("Sprite sheet must contain an 8 by 3 grid")
    width, height = sheet.width // COLUMNS, sheet.height // ROWS
    print(f"Source corner: {sheet.getpixel((0, 0))}; extrema: {sheet.getextrema()}")
    for row in range(ROWS):
        for column in range(COLUMNS):
            box = (column * width, row * height, (column + 1) * width, (row + 1) * height)
            frame = sheet.crop(box)
            pixels = frame.load()
            visited = set()
            queue = deque(
                [(x, y) for x in range(width) for y in (0, height - 1)]
                + [(x, y) for y in range(height) for x in (0, width - 1)]
            )
            # The closed, near-black character outline is the flood-fill barrier.
            while queue:
                x, y = queue.popleft()
                if (x, y) in visited or not (0 <= x < width and 0 <= y < height):
                    continue
                visited.add((x, y))
                r, g, b, alpha = pixels[x, y]
                if max(r, g, b) <= 32 and alpha:
                    continue
                pixels[x, y] = (r, g, b, 0)
                queue.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
            if frame.getbbox() is None:
                raise ValueError(f"No character remained at row {row}, column {column}")
            sheet.paste(frame, box)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    print(f"Prepared {output}: {sheet.width}x{sheet.height}, cells {width}x{height}")
    print(f"Alpha range: {sheet.getchannel('A').getextrema()}")
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
