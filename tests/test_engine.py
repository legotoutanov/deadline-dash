"""Example-based tests on the pure engine. No pygame or curses import
anywhere in this file -- that's the point of the split."""

from __future__ import annotations

import random

from flappy.engine import (
    ESSAY_X,
    FIXED_DT,
    FLAP_VELOCITY,
    GRASS_WIDTH,
    GRAVITY,
    apply_gravity,
    collides,
    initial_state,
    out_of_bounds,
    score_passed_grass,
    step,
)
from flappy.models import Essay, GameState, GameStatus, Grass


def test_flap_sets_upward_velocity() -> None:
    essay = Essay(y=100.0, velocity=50.0)
    result = apply_gravity(essay, flap=True)
    assert result.velocity == FLAP_VELOCITY
    assert result.y == essay.y + FLAP_VELOCITY * FIXED_DT


def test_without_a_flap_gravity_accelerates_the_essay_downward() -> None:
    essay = Essay(y=100.0, velocity=0.0)
    result = apply_gravity(essay, flap=False)
    assert result.velocity == GRAVITY * FIXED_DT
    assert result.y > essay.y


def test_essay_above_the_top_of_the_screen_is_out_of_bounds() -> None:
    assert out_of_bounds(Essay(y=-1.0, velocity=0.0))


def test_essay_on_the_ground_is_out_of_bounds() -> None:
    assert out_of_bounds(Essay(y=600.0, velocity=0.0))


def test_essay_mid_screen_is_in_bounds() -> None:
    assert not out_of_bounds(Essay(y=300.0, velocity=0.0))


def test_essay_in_the_gap_does_not_collide() -> None:
    patch = Grass(x=ESSAY_X, gap_y=300.0, gap_height=150.0, theme="Old Court")
    essay = Essay(y=300.0, velocity=0.0)  # centred in the gap
    assert not collides(essay, (patch,))


def test_essay_above_the_gap_collides() -> None:
    patch = Grass(x=ESSAY_X, gap_y=300.0, gap_height=150.0, theme="Old Court")
    essay = Essay(y=0.0, velocity=0.0)
    assert collides(essay, (patch,))


def test_essay_below_the_gap_collides() -> None:
    patch = Grass(x=ESSAY_X, gap_y=300.0, gap_height=150.0, theme="Old Court")
    essay = Essay(y=580.0, velocity=0.0)
    assert collides(essay, (patch,))


def test_grass_far_away_never_collides() -> None:
    patch = Grass(x=ESSAY_X + 500.0, gap_y=300.0, gap_height=150.0, theme="Old Court")
    essay = Essay(y=0.0, velocity=0.0)  # would collide if it were near
    assert not collides(essay, (patch,))


def test_score_increments_once_the_essay_has_passed_a_patch() -> None:
    patch = Grass(x=ESSAY_X - GRASS_WIDTH - 1.0, gap_y=300.0, gap_height=150.0, theme="Old Court")
    grass, score = score_passed_grass((patch,), Essay(y=300.0, velocity=0.0), score=0)
    assert score == 1
    assert grass[0].scored


def test_a_patch_is_never_scored_twice() -> None:
    patch = Grass(
        x=ESSAY_X - GRASS_WIDTH - 1.0, gap_y=300.0, gap_height=150.0, theme="Old Court", scored=True
    )
    grass, score = score_passed_grass((patch,), Essay(y=300.0, velocity=0.0), score=5)
    assert score == 5


def test_a_patch_still_ahead_of_the_essay_is_not_scored() -> None:
    patch = Grass(x=ESSAY_X + 10.0, gap_y=300.0, gap_height=150.0, theme="Old Court")
    grass, score = score_passed_grass((patch,), Essay(y=300.0, velocity=0.0), score=0)
    assert score == 0
    assert not grass[0].scored


def test_step_on_a_crashed_state_is_a_no_op() -> None:
    crashed = GameState(
        essay=Essay(y=10.0, velocity=5.0), grass=(), score=3, status=GameStatus.CRASHED
    )
    assert step(crashed, flap=True) == crashed
    assert step(crashed, flap=False) == crashed


def test_flying_into_the_ground_crashes() -> None:
    near_the_ground = 560.0
    state = GameState(
        essay=Essay(y=near_the_ground, velocity=500.0),
        grass=(),
        score=0,
        status=GameStatus.PLAYING,
    )
    result = step(state, flap=False)
    assert result.status is GameStatus.CRASHED


def test_initial_state_is_deterministic_for_the_same_seed() -> None:
    a = initial_state(random.Random(42))
    b = initial_state(random.Random(42))
    assert a == b


def test_initial_state_differs_for_different_seeds() -> None:
    a = initial_state(random.Random(1))
    b = initial_state(random.Random(2))
    assert a.grass != b.grass


def test_a_full_game_from_a_fixed_seed_runs_without_error() -> None:
    """A smoke test that plays a deterministic game to completion (crash),
    always flapping."""
    state = initial_state(random.Random(0))
    for _ in range(100_000):
        state = step(state, flap=True)
        if state.status is GameStatus.CRASHED:
            break
    assert state.status is GameStatus.CRASHED
    assert state.score >= 0
