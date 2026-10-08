"""The pure game-logic core. No pygame or curses import, no wall-clock
time, no I/O.

step() advances the game by exactly one fixed-size tick (FIXED_DT
seconds). Call it repeatedly from a real-time loop (see render.py /
render_console.py) or from a test -- either way it behaves identically,
because it only ever looks at the GameState it's given.
"""

from dataclasses import replace

from .models import Essay, GameState, GameStatus, Grass
from .obstacles import THEMES

FIXED_DT = 1.0 / 60.0

SCREEN_WIDTH = 400.0
SCREEN_HEIGHT = 600.0
GROUND_Y = SCREEN_HEIGHT - 20.0

ESSAY_X = 80.0
ESSAY_SIZE = 24.0
GRAVITY = 950.0  # px/s^2
FLAP_VELOCITY = -260.0  # px/s, negative is upward

GRASS_WIDTH = 60.0
GRASS_GAP = 150.0
GRASS_SPACING = 230.0
GRASS_SPEED = 140.0  # px/s
NUM_GRASS = 40  # pre-generated up front; see initial_state()


def initial_state(rng, num_grass=NUM_GRASS):
    """A fresh game. The whole course is generated here, once, from `rng`
    -- step() itself never touches randomness, which is what keeps it
    exactly reproducible given the same starting state and flap sequence."""
    grass = []
    x = SCREEN_WIDTH + 100.0
    for _ in range(num_grass):
        gap_y = rng.uniform(GRASS_GAP, GROUND_Y - GRASS_GAP)
        theme = THEMES[0]
        grass.append(Grass(x=x, gap_y=gap_y, gap_height=GRASS_GAP, theme=theme.name))
        x += GRASS_SPACING
    return GameState(
        essay=Essay(y=SCREEN_HEIGHT / 2, velocity=0.0),
        grass=tuple(grass),
        score=0,
        status=GameStatus.PLAYING,
    )


def apply_gravity(essay, flap):
    """One tick of vertical physics. A flap overrides velocity outright;
    otherwise gravity accelerates the essay downward."""
    velocity = FLAP_VELOCITY if flap else essay.velocity - GRAVITY * FIXED_DT
    return Essay(y=essay.y + velocity * FIXED_DT, velocity=velocity)


def advance_grass(grass):
    """Move every patch of grass left by one tick's worth of GRASS_SPEED."""
    return tuple(replace(g, x=g.x - GRASS_SPEED * FIXED_DT) for g in grass)


def out_of_bounds(essay):
    """True if the essay has hit the ground or flown off the top."""
    return essay.y < 0 or essay.y + ESSAY_SIZE >= GROUND_Y


def collides(essay, grass):
    """Axis-aligned bounding-box collision between the essay and any grass
    it currently overlaps horizontally. Deliberately not pixel-perfect
    collision: that would need image data inside this otherwise-pure
    function, which is exactly what we don't want here."""
    essay_left, essay_right = ESSAY_X, ESSAY_X + ESSAY_SIZE
    essay_top, essay_bottom = essay.y, essay.y + ESSAY_SIZE
    for patch in grass:
        if patch.x > essay_right or patch.x + GRASS_WIDTH < essay_left:
            continue
        gap_top = patch.gap_y - patch.gap_height / 2
        gap_bottom = patch.gap_y + patch.gap_height / 2
        if essay_top < gap_top and essay_bottom > gap_bottom:
            return True
    return False


def score_passed_grass(grass, essay, score):
    """Mark any grass the essay has just fully passed as scored, and bump
    the score once per patch -- the `scored` flag is what stops a patch
    being counted twice."""
    new_grass = []
    new_score = score
    for patch in grass:
        if not patch.scored and patch.x + GRASS_WIDTH < ESSAY_X:
            new_grass.append(replace(patch, scored=True))
            new_score += 1
        else:
            new_grass.append(patch)
    return tuple(new_grass), new_score


def step(state, flap):
    """Advance the game by one fixed tick. Once CRASHED, step() is a no-op
    forever -- that's deliberate and tested (see test_crashed_state_is_terminal)."""
    if state.status is GameStatus.CRASHED:
        return state

    essay = apply_gravity(state.essay, flap)
    grass = advance_grass(state.grass)

    if collides(essay, grass) or out_of_bounds(essay):
        return replace(state, essay=essay, grass=grass, status=GameStatus.CRASHED)

    grass, score = score_passed_grass(grass, essay, state.score)
    return GameState(essay=essay, grass=grass, score=score, status=GameStatus.PLAYING)
