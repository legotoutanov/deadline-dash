"""Data model for Deadline Dash. Frozen dataclasses only -- no pygame or
curses import here, on purpose: this module (and engine.py, which uses it)
has to stay pure and testable without a display.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GameStatus(str, Enum):
    """Whether the essay is still flying or has been caught on the grass."""

    PLAYING = "playing"
    CRASHED = "crashed"


@dataclass(frozen=True)
class Essay:
    """The player's position and vertical speed. y grows downward, as in
    screen coordinates: 0 is the top of the screen."""

    y: float
    velocity: float


@dataclass(frozen=True)
class Grass:
    """One obstacle: a gap of `gap_height`, centred on `gap_y`, in a patch
    of grass of width GRASS_WIDTH (see engine.py) whose left edge is at
    `x`. `scored` is set once the essay has passed it, so it's only
    counted once. `theme` is purely cosmetic -- see obstacles/__init__.py."""

    x: float
    gap_y: float
    gap_height: float
    theme: str
    scored: bool = False


@dataclass(frozen=True)
class ObstacleTheme:
    """One flavour of grass -- see obstacles/__init__.py for the registry.
    `name` and `sign` are shown to the player; the colours are for the
    pygame renderer (the console renderer just uses the name's first
    letter)."""

    name: str
    sign: str
    light_colour: tuple[int, int, int]
    dark_colour: tuple[int, int, int]


@dataclass(frozen=True)
class GameState:
    """Everything the game needs to know at a single instant."""

    essay: Essay
    grass: tuple[Grass, ...]
    score: int
    status: GameStatus
