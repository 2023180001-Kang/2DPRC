"""Align the supplied enemy's four-row sheet without changing its source."""

from resources import ROOT
from settings import ENEMY_SOURCE
from tools.prepare_character import prepare


if __name__ == "__main__":
    prepare(ROOT / ENEMY_SOURCE, ROOT / "assets/enemy.png", preview=True)
