"""Load game images relative to the project, not the working directory."""

from pathlib import Path

import pico2d
import sdl2

ROOT = Path(__file__).resolve().parent
IMAGE_FILES = {
    "background": "newfirststage.png", "character": "assets/character.png", "heart": "Heart.png",
}


class ResourceError(RuntimeError):
    pass


def release_images(images):
    # Tracebacks can retain Image objects after the renderer has been destroyed.
    for image in images.values():
        texture = image.texture
        image.texture = None
        if texture:
            sdl2.SDL_DestroyTexture(texture)
    images.clear()


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
        release_images(images)
        raise
