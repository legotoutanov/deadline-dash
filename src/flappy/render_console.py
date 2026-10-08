"""A curses-based console renderer and game loop -- one of two front-ends
over the exact same pure engine `render.py` (pygame) uses. This file is
the whole difference between them; nothing in engine.py or models.py
changes.

Needs the stdlib `curses` module on Linux/macOS, or the `windows-curses`
package on Windows (prebuilt wheels, no compiler -- see pyproject.toml's
environment marker).

Run with: python -m flappy.render_console

On keeping a held or auto-repeating key from over-flapping: a terminal's
own key-repeat (unlike pygame, which doesn't auto-repeat KEYDOWN by
default) will happily send a stream of space characters for as long as the
key is held, each one via a separate stdscr.getch(). Without
FLAP_COOLDOWN_TICKS enforcing a minimum real gap between accepted flaps,
that stream could apply a full flap on nearly every 60Hz physics tick --
pinning the essay's upward velocity continuously rather than giving it a
single, distinct flap per press.
"""

from __future__ import annotations

import curses
import random
import time
from typing import Protocol

from .engine import (
    ESSAY_X,
    FIXED_DT,
    GRASS_WIDTH,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    initial_state,
    step,
)
from .models import GameState, GameStatus

CONSOLE_COLS = 60
CONSOLE_ROWS = 22
RENDER_DT = 1.0 / 20.0  # redraw at 20fps even though physics steps at 60Hz
FLAP_COOLDOWN_TICKS = 6  # ~0.1s at 60Hz: see the module docstring

FLAP_KEY = ord(" ")
RESTART_KEY = ord("r")
QUIT_KEYS = (ord("q"), 27)  # 27 = Escape

ESSAY_CHAR = "@"
ESSAY_CRASHED_CHAR = "X"
GRASS_CHAR = "#"


class ConsoleWindow(Protocol):
    """Exactly the subset of curses.window that render() uses -- a Protocol
    rather than `curses.window` directly, so a test can hand render() a
    plain fake instead of needing a real terminal."""

    def erase(self) -> None: ...
    def addstr(self, row: int, col: int, text: str) -> None: ...
    def refresh(self) -> None: ...


def pixel_to_col(x: float) -> int:
    """Map a pixel x-coordinate (0..SCREEN_WIDTH) to a console column. Pure
    and tested without any curses involvement at all."""
    return max(0, min(CONSOLE_COLS - 1, int(x / SCREEN_WIDTH * CONSOLE_COLS)))


def pixel_to_row(y: float) -> int:
    """Map a pixel y-coordinate (0..SCREEN_HEIGHT) to a console row."""
    return max(0, min(CONSOLE_ROWS - 1, int(y / SCREEN_HEIGHT * CONSOLE_ROWS)))


def grass_columns(grass_x: float) -> range:
    """The full span of console columns a patch of grass actually covers.
    Drawing only its left column would make it look far narrower than its
    real, collidable width -- see FINDINGS.md in the original spike for
    exactly what that bug looked like."""
    return range(pixel_to_col(grass_x), pixel_to_col(grass_x + GRASS_WIDTH) + 1)


def row_is_clear(row: int, gap_top: float, gap_bottom: float) -> bool:
    """A row counts as part of the gap (drawn open) only if its *entire*
    pixel height fits inside the gap -- not just a single sample point.
    The terminal should never show more safety than actually exists."""
    row_top = row / CONSOLE_ROWS * SCREEN_HEIGHT
    row_bottom = (row + 1) / CONSOLE_ROWS * SCREEN_HEIGHT
    return row_top >= gap_top and row_bottom <= gap_bottom


def _safe_addstr(win: ConsoleWindow, row: int, col: int, text: str) -> None:
    """curses raises if you write off the edge of the window (including the
    bottom-right cell, a long-standing quirk) -- harmless here, since a
    clipped frame is fine."""
    try:
        win.addstr(row, max(col, 0), text)
    except curses.error:
        pass


def render(win: ConsoleWindow, state: GameState) -> None:
    """Draw one frame. Same contract as render.render() in the pygame
    version: a pure side effect on `win`, nothing fed back into state."""
    win.erase()

    for patch in state.grass:
        if patch.x > SCREEN_WIDTH or patch.x + GRASS_WIDTH < 0:
            continue
        gap_top = patch.gap_y - patch.gap_height / 2
        gap_bottom = patch.gap_y + patch.gap_height / 2
        for col in grass_columns(patch.x):
            for row in range(CONSOLE_ROWS):
                if not row_is_clear(row, gap_top, gap_bottom):
                    _safe_addstr(win, row, col, GRASS_CHAR)

    essay_char = ESSAY_CRASHED_CHAR if state.status is GameStatus.CRASHED else ESSAY_CHAR
    _safe_addstr(win, pixel_to_row(state.essay.y), pixel_to_col(ESSAY_X), essay_char)

    _safe_addstr(win, 0, CONSOLE_COLS // 2 - 2, f"{state.score:>4}")
    if state.status is GameStatus.CRASHED:
        _safe_addstr(win, CONSOLE_ROWS // 2, CONSOLE_COLS // 2 - 12, "Deaned -- r to restart")

    win.refresh()


def run(stdscr: curses.window) -> None:
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.keypad(True)

    rng = random.Random()
    state = initial_state(rng)
    flap_requested = False
    flap_cooldown = 0
    accumulator = 0.0
    last_render = 0.0
    last_tick = time.monotonic()

    while True:
        key = stdscr.getch()
        while key != -1:
            if key == FLAP_KEY:
                flap_requested = True
            elif key in QUIT_KEYS:
                return
            elif key == RESTART_KEY and state.status is GameStatus.CRASHED:
                state = initial_state(rng)
                flap_requested = False
                flap_cooldown = 0
            key = stdscr.getch()

        now = time.monotonic()
        accumulator += now - last_tick
        last_tick = now
        while accumulator >= FIXED_DT:
            if flap_cooldown > 0:
                flap_cooldown -= 1
            flap = flap_requested and flap_cooldown == 0
            if flap:
                flap_requested = False
                flap_cooldown = FLAP_COOLDOWN_TICKS
            state = step(state, flap)
            accumulator -= FIXED_DT

        if now - last_render >= RENDER_DT:
            render(stdscr, state)
            last_render = now

        time.sleep(0.005)  # don't busy-loop a whole CPU core


def main() -> None:
    curses.wrapper(run)


if __name__ == "__main__":
    main()
