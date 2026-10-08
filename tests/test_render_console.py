"""Tests for the curses renderer. No real terminal needed anywhere here:
pixel_to_col/pixel_to_row are pure, and render() only needs something that
satisfies the ConsoleWindow protocol, not an actual curses.window -- that's
what the Protocol in render_console.py is for."""

from __future__ import annotations

import random

from flappy.engine import GRASS_WIDTH, SCREEN_HEIGHT, SCREEN_WIDTH, collides, initial_state, step
from flappy.models import Essay, GameState, GameStatus, Grass
from flappy.render_console import (
    CONSOLE_COLS,
    CONSOLE_ROWS,
    grass_columns,
    pixel_to_col,
    pixel_to_row,
    render,
    row_is_clear,
)


class FakeWindow:
    """A minimal stand-in for curses.window: records every call instead of
    drawing anything, so a test can inspect what render() tried to do."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def erase(self) -> None:
        self.calls.append(("erase",))

    def addstr(self, row: int, col: int, text: str) -> None:
        self.calls.append(("addstr", str(row), str(col), text))

    def refresh(self) -> None:
        self.calls.append(("refresh",))


def test_pixel_to_col_stays_in_range_at_the_screen_edges() -> None:
    assert pixel_to_col(0.0) == 0
    assert pixel_to_col(SCREEN_WIDTH) == CONSOLE_COLS - 1


def test_pixel_to_row_stays_in_range_at_the_screen_edges() -> None:
    assert pixel_to_row(0.0) == 0
    assert pixel_to_row(SCREEN_HEIGHT) == CONSOLE_ROWS - 1


def test_pixel_to_col_clamps_values_outside_the_screen() -> None:
    assert pixel_to_col(-50.0) == 0
    assert pixel_to_col(SCREEN_WIDTH + 500.0) == CONSOLE_COLS - 1


def test_grass_columns_spans_the_full_width_not_just_its_left_edge() -> None:
    """A patch of grass is actually 9 columns wide (GRASS_WIDTH=60px at
    this scale) -- drawing only its left column would make it look far
    narrower than its real, collidable width, and a player could fly well
    past what looked like a cleared patch and still hit the part that was
    never drawn."""
    cols = list(grass_columns(100.0))
    expected_width_in_columns = round(GRASS_WIDTH / (SCREEN_WIDTH / CONSOLE_COLS))
    assert len(cols) >= expected_width_in_columns - 1
    assert len(cols) > 1


def test_a_row_mostly_covered_by_grass_is_never_drawn_as_clear() -> None:
    gap_top, gap_bottom = 300.0, 310.0  # a gap much thinner than one row (~27px)
    row = int(gap_top / SCREEN_HEIGHT * CONSOLE_ROWS)
    assert not row_is_clear(row, gap_top, gap_bottom)


def test_what_is_drawn_as_the_gap_never_extends_into_real_grass() -> None:
    """Build an actual patch, render it, and confirm no row inside the
    drawn gap is a row the real collides() would treat as a hit for an
    essay centred there."""
    patch = Grass(x=100.0, gap_y=300.0, gap_height=80.0, theme="Old Court")
    win = FakeWindow()
    state = GameState(
        essay=Essay(y=-1000.0, velocity=0.0), grass=(patch,), score=0, status=GameStatus.PLAYING
    )
    render(win, state)
    drawn_rows = {int(c[1]) for c in win.calls if c[0] == "addstr" and c[3] == "#"}

    for row in range(CONSOLE_ROWS):
        if row in drawn_rows:
            continue
        row_mid_y = (row + 0.5) / CONSOLE_ROWS * SCREEN_HEIGHT
        probe = Essay(y=row_mid_y, velocity=0.0)
        assert not collides(probe, (patch,)), (
            f"row {row} was drawn as clear gap but an essay there really collides"
        )


def test_render_erases_and_refreshes_every_frame() -> None:
    win = FakeWindow()
    state = initial_state(random.Random(0))
    render(win, state)
    assert win.calls[0] == ("erase",)
    assert win.calls[-1] == ("refresh",)


def test_render_draws_the_essay_somewhere_on_screen() -> None:
    win = FakeWindow()
    state = initial_state(random.Random(0))
    render(win, state)
    essay_chars = [c for c in win.calls if c[0] == "addstr" and c[3] in ("@", "X")]
    assert len(essay_chars) == 1


def test_crashed_essay_is_drawn_differently_from_a_flying_one() -> None:
    win_flying = FakeWindow()
    win_crashed = FakeWindow()
    state = initial_state(random.Random(0))
    render(win_flying, state)

    crashed = state
    for _ in range(10_000):
        crashed = step(crashed, flap=False)
        if crashed.status is GameStatus.CRASHED:
            break
    render(win_crashed, crashed)

    flying_chars = {c[3] for c in win_flying.calls if c[0] == "addstr" and c[3] in ("@", "X")}
    crashed_chars = {c[3] for c in win_crashed.calls if c[0] == "addstr" and c[3] in ("@", "X")}
    assert flying_chars == {"@"}
    assert crashed_chars == {"X"}
