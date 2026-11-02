"""Load game images relative to the project, not the working directory."""

from pathlib import Path

import pico2d

ROOT = Path(__file__).resolve().parent
IMAGE_FILES = {"background": "firststage.png", "character": "MainCharacter.png"}


class ResourceError(RuntimeError):
    pass


def load_images(root=ROOT):
    images = {}
    try:
        for name, filename in IMAGE_FILES.items():
            path = Path(root) / filename
            if not path.is_file():
                raise ResourceError(f"Image file not found: {path}")
            try:
                images[name] = pico2d.load_image(str(path))
            except OSError as error:
                raise ResourceError(f"Cannot load image: {path}") from error
        return images
    except Exception:
        images.clear()
        raise
