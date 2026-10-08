"""Drawing and the real-time loop. The only file in this package (besides
render_console.py) that imports pygame -- nothing here is unit tested the
way engine.py is.

The one real subtlety in splitting logic from rendering: a flap is a single
discrete key-press, not something you can just sample once per real frame,
because the inner fixed-timestep loop below may run engine.step() zero,
one, or several times per real frame depending on how late the frame was.
The fix is a small pending-flap latch: a KEYDOWN sets it, and the next
eligible fixed step consumes it.

A second subtlety: without some minimum gap between accepted flaps, a key
that auto-repeats while held (pygame doesn't do this by default, but
render_console.py's terminal input does) would apply a full flap on nearly
every 60Hz tick. FLAP_COOLDOWN_TICKS enforces a short minimum gap.

On the window being bigger than the game's own coordinate space: all game
logic stays in engine.py's native SCREEN_WIDTH x SCREEN_HEIGHT units --
scaling up is purely a rendering concern. Everything is drawn onto an
offscreen "world" surface at that native resolution first, then scaled up
once onto the real, bigger window; HUD text is drawn directly onto the
real window afterward, at full resolution, so it stays crisp.
"""

from __future__ import annotations

import random

import pygame
import pygame.gfxdraw

from .engine import (
    ESSAY_SIZE,
    ESSAY_X,
    FIXED_DT,
    GRASS_WIDTH,
    GROUND_Y,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    initial_state,
    step,
)
from .models import GameState, GameStatus, Grass
from .obstacles import THEMES

_THEME_COLOURS = {t.name: (t.light_colour, t.dark_colour) for t in THEMES}
_DEFAULT_THEME_COLOURS = ((92, 188, 97), (64, 158, 74))

RENDER_SCALE = 1.6
WINDOW_WIDTH = round(SCREEN_WIDTH * RENDER_SCALE)
WINDOW_HEIGHT = round(SCREEN_HEIGHT * RENDER_SCALE)

FLAP_COOLDOWN_TICKS = 6  # ~0.1s at 60Hz: see the module docstring

SKY_TOP = (120, 200, 245)
SKY_BOTTOM = (205, 235, 250)
CLOUD_COLOUR = (255, 255, 255, 160)

GROUND_COLOUR = (221, 198, 120)
GROUND_STRIPE_COLOUR = (201, 173, 90)

SIGN_POST_COLOUR = (120, 90, 60)
SIGN_FACE_COLOUR = (250, 248, 235)
SIGN_BORDER_COLOUR = (190, 40, 40)

# The player is a panicking supervision essay, not a bird -- loose pages
# fanned out like wings, a worried face on the top sheet.
PAGE_COLOUR = (250, 248, 238)
PAGE_SHADOW_COLOUR = (206, 200, 184)
PAGE_BORDER_COLOUR = (55, 50, 40)
PAGE_TEXT_COLOUR = (195, 190, 175)
RED_PEN_COLOUR = (205, 40, 40)
ESSAY_CRASHED_PAGE = (245, 205, 200)
ESSAY_CRASHED_SHADOW = (220, 165, 160)

TEXT_COLOUR = (35, 30, 20)
TEXT_SHADOW = (255, 255, 255)

ESSAY_CANVAS_W = int(ESSAY_SIZE * 1.9)
ESSAY_CANVAS_H = int(ESSAY_SIZE * 1.6)

_world: pygame.Surface | None = None
_sky_gradient: pygame.Surface | None = None


def _world_surface() -> pygame.Surface:
    global _world
    if _world is None:
        _world = pygame.Surface((int(SCREEN_WIDTH), int(SCREEN_HEIGHT)))
    return _world


def _sky() -> pygame.Surface:
    global _sky_gradient
    if _sky_gradient is None:
        surface = pygame.Surface((int(SCREEN_WIDTH), int(SCREEN_HEIGHT)))
        height = int(SCREEN_HEIGHT)
        for y in range(height):
            t = y / max(1, height - 1)
            colour = tuple(int(SKY_TOP[i] + (SKY_BOTTOM[i] - SKY_TOP[i]) * t) for i in range(3))
            pygame.draw.line(surface, colour, (0, y), (int(SCREEN_WIDTH), y))
        _sky_gradient = surface
    return _sky_gradient


def _draw_clouds(world: pygame.Surface) -> None:
    for cx, cy, scale in ((70, 90, 1.0), (260, 60, 0.7), (330, 150, 0.85)):
        cloud = pygame.Surface((int(70 * scale), int(34 * scale)), pygame.SRCALPHA)
        w, h = cloud.get_size()
        puffs = ((0, h // 2, h // 2), (w * 0.35, h * 0.3, h * 0.6), (w * 0.65, h * 0.45, h * 0.5))
        for dx, dy, r in puffs:
            pygame.gfxdraw.filled_circle(cloud, int(dx + r), int(dy), int(r), CLOUD_COLOUR)
        world.blit(cloud, (cx, cy))


def _draw_ground(world: pygame.Surface, scroll_phase: float) -> None:
    rect = pygame.Rect(0, int(GROUND_Y), int(SCREEN_WIDTH), int(SCREEN_HEIGHT - GROUND_Y))
    pygame.draw.rect(world, GROUND_COLOUR, rect)
    stripe_width = 20
    offset = int(scroll_phase) % stripe_width
    x = -offset
    while x < SCREEN_WIDTH:
        pygame.draw.rect(world, GROUND_STRIPE_COLOUR, (x, rect.top, stripe_width / 2, rect.height))
        x += stripe_width


def _draw_keep_off_sign(world: pygame.Surface, cx: float, edge_y: float) -> None:
    """No text (illegible at this scale anyway) -- a post and a crossed-out
    placard, universally readable as "don't"."""
    post_height = 10
    face_w, face_h = 22, 14
    pygame.draw.rect(world, SIGN_POST_COLOUR, (cx - 1.5, edge_y - post_height / 2, 3, post_height))
    face_rect = pygame.Rect(0, 0, face_w, face_h)
    face_rect.center = (int(cx), int(edge_y))
    pygame.draw.rect(world, SIGN_FACE_COLOUR, face_rect)
    pygame.draw.rect(world, SIGN_BORDER_COLOUR, face_rect, width=2)
    pygame.draw.line(world, SIGN_BORDER_COLOUR, face_rect.topleft, face_rect.bottomright, 2)


def _draw_grass_patch(world: pygame.Surface, patch: Grass) -> None:
    light, dark = _THEME_COLOURS.get(patch.theme, _DEFAULT_THEME_COLOURS)
    gap_top = patch.gap_y - patch.gap_height / 2
    gap_bottom = patch.gap_y + patch.gap_height / 2
    num_stripes = 4
    stripe_width = GRASS_WIDTH / num_stripes

    for body_top, body_bottom in ((0, gap_top), (gap_bottom, SCREEN_HEIGHT)):
        if body_bottom <= body_top:
            continue
        for i in range(num_stripes):
            colour = light if i % 2 == 0 else dark
            pygame.draw.rect(
                world,
                colour,
                (patch.x + i * stripe_width, body_top, stripe_width + 1, body_bottom - body_top),
            )
        edge_y = body_bottom if body_top == 0 else body_top
        _draw_keep_off_sign(world, patch.x + GRASS_WIDTH / 2, edge_y)


def _fanned_page(
    width: int, height: int, colour: tuple[int, int, int], angle: float
) -> pygame.Surface:
    page = pygame.Surface((width, height), pygame.SRCALPHA)
    page.fill(colour)
    pygame.draw.rect(page, PAGE_BORDER_COLOUR, page.get_rect(), width=1)
    return pygame.transform.rotate(page, angle)


def _essay_sprite(crashed: bool) -> pygame.Surface:
    page_colour = ESSAY_CRASHED_PAGE if crashed else PAGE_COLOUR
    shadow_colour = ESSAY_CRASHED_SHADOW if crashed else PAGE_SHADOW_COLOUR

    surface = pygame.Surface((ESSAY_CANVAS_W, ESSAY_CANVAS_H), pygame.SRCALPHA)
    cx, cy = ESSAY_CANVAS_W * 0.5, ESSAY_CANVAS_H * 0.52
    page_w, page_h = int(ESSAY_CANVAS_W * 0.56), int(ESSAY_CANVAS_H * 0.74)

    for angle in (-28, 28):
        wing = _fanned_page(page_w, page_h, shadow_colour, angle)
        surface.blit(wing, wing.get_rect(center=(cx, cy)))

    main_page = pygame.Surface((page_w, page_h), pygame.SRCALPHA)
    main_page.fill(page_colour)
    pygame.draw.rect(main_page, PAGE_BORDER_COLOUR, main_page.get_rect(), width=2)

    for i in range(3):
        y = page_h * (0.64 + i * 0.1)
        pygame.draw.line(main_page, PAGE_TEXT_COLOUR, (page_w * 0.16, y), (page_w * 0.84, y), 2)

    pygame.draw.line(
        main_page, RED_PEN_COLOUR, (page_w * 0.18, page_h * 0.56), (page_w * 0.48, page_h * 0.5), 2
    )
    pygame.draw.line(
        main_page, RED_PEN_COLOUR, (page_w * 0.48, page_h * 0.5), (page_w * 0.3, page_h * 0.6), 2
    )

    left_eye_x, right_eye_x = page_w * 0.34, page_w * 0.66
    eye_y = page_h * 0.3
    eye_white_r, eye_pupil_r = max(2, int(page_h * 0.1)), max(1, int(page_h * 0.045))
    for eye_x in (left_eye_x, right_eye_x):
        pygame.gfxdraw.filled_circle(
            main_page, int(eye_x), int(eye_y), eye_white_r, (255, 255, 255)
        )
        pygame.gfxdraw.filled_circle(main_page, int(eye_x), int(eye_y), eye_pupil_r, (25, 20, 15))
    brow_dy = page_h * 0.08
    pygame.draw.line(
        main_page,
        PAGE_BORDER_COLOUR,
        (left_eye_x - page_w * 0.09, eye_y - brow_dy * 0.5),
        (left_eye_x + page_w * 0.09, eye_y - brow_dy),
        2,
    )
    pygame.draw.line(
        main_page,
        PAGE_BORDER_COLOUR,
        (right_eye_x - page_w * 0.09, eye_y - brow_dy),
        (right_eye_x + page_w * 0.09, eye_y - brow_dy * 0.5),
        2,
    )

    mouth_rect = pygame.Rect(0, 0, int(page_w * 0.18), int(page_h * 0.12))
    mouth_rect.center = (int(page_w * 0.5), int(page_h * 0.46))
    pygame.draw.ellipse(main_page, PAGE_BORDER_COLOUR, mouth_rect)

    main_rotated = pygame.transform.rotate(main_page, -6)
    surface.blit(main_rotated, main_rotated.get_rect(center=(cx, cy)))
    return surface


def _rotated_essay(crashed: bool, velocity: float) -> pygame.Surface:
    sprite = _essay_sprite(crashed)
    angle = max(-30.0, min(70.0, velocity / 6.0))
    return pygame.transform.rotate(sprite, -angle)


def render(screen: pygame.Surface, state: GameState) -> None:
    """Draw one frame. Pure side effect on `screen`; nothing here feeds back
    into the game state."""
    world = _world_surface()
    world.blit(_sky(), (0, 0))
    _draw_clouds(world)

    scroll_phase = state.grass[0].x if state.grass else 0.0
    _draw_ground(world, scroll_phase)

    for patch in state.grass:
        if patch.x > SCREEN_WIDTH or patch.x + GRASS_WIDTH < 0:
            continue
        _draw_grass_patch(world, patch)

    crashed = state.status is GameStatus.CRASHED
    essay_surface = _rotated_essay(crashed, state.essay.velocity)
    essay_rect = essay_surface.get_rect(
        center=(ESSAY_X + ESSAY_SIZE / 2, state.essay.y + ESSAY_SIZE / 2)
    )
    world.blit(essay_surface, essay_rect)

    pygame.transform.smoothscale(world, screen.get_size(), screen)

    def _text_with_shadow(
        font: pygame.font.Font, text: str, colour: tuple[int, int, int]
    ) -> pygame.Surface:
        shadow = font.render(text, True, TEXT_SHADOW)
        main = font.render(text, True, colour)
        combined = pygame.Surface(
            (main.get_width() + 2, main.get_height() + 2), pygame.SRCALPHA
        )
        combined.blit(shadow, (0, 2))
        combined.blit(shadow, (2, 0))
        combined.blit(shadow, (2, 2))
        combined.blit(shadow, (0, 0))
        combined.blit(main, (1, 1))
        return combined

    score_font = pygame.font.SysFont(None, int(44 * RENDER_SCALE))
    score_text = _text_with_shadow(score_font, str(state.score), TEXT_COLOUR)
    screen.blit(score_text, (WINDOW_WIDTH / 2 - score_text.get_width() / 2, 16 * RENDER_SCALE))

    if crashed:
        big_font = pygame.font.SysFont(None, int(40 * RENDER_SCALE))
        msg = _text_with_shadow(big_font, "Deaned -- press R to restart", TEXT_COLOUR)
        panel = pygame.Surface((msg.get_width() + 24, msg.get_height() + 16), pygame.SRCALPHA)
        panel.fill((255, 255, 255, 180))
        panel_rect = panel.get_rect(center=(WINDOW_WIDTH / 2, WINDOW_HEIGHT / 2))
        screen.blit(panel, panel_rect)
        screen.blit(msg, msg.get_rect(center=panel_rect.center))


def run() -> None:
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Deadline Dash")
    clock = pygame.time.Clock()

    rng = random.Random()
    state = initial_state(rng)
    accumulator = 0.0
    flap_requested = False
    flap_cooldown = 0
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                flap_requested = True
            elif (
                event.type == pygame.KEYDOWN
                and event.key == pygame.K_r
                and state.status is GameStatus.CRASHED
            ):
                state = initial_state(rng)
                flap_requested = False
                flap_cooldown = 0

        accumulator += clock.tick(60) / 1000
        while accumulator >= FIXED_DT:
            if flap_cooldown > 0:
                flap_cooldown -= 1
            flap = flap_requested and flap_cooldown == 0
            if flap:
                flap_requested = False
                flap_cooldown = FLAP_COOLDOWN_TICKS
            state = step(state, flap)
            accumulator -= FIXED_DT

        render(screen, state)
        pygame.display.flip()

    pygame.quit()
