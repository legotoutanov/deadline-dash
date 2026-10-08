"""Safety-net tests for the obstacle-theme registry. These exist for
Friday: they're what catches a lazily-resolved merge conflict even when
the file still runs (see obstacles/__init__.py)."""

from __future__ import annotations

from pathlib import Path

from flappy.obstacles import THEMES


def test_every_theme_has_a_name_and_a_sign() -> None:
    for theme in THEMES:
        assert theme.name.strip()
        assert theme.sign.strip()


def test_every_theme_name_is_unique() -> None:
    names = [theme.name for theme in THEMES]
    assert len(names) == len(set(names))


def test_every_theme_module_is_actually_registered() -> None:
    """Scans the actual files in obstacles/ and fails loudly if someone's
    theme module exists on disk but was never wired into THEMES -- exactly
    what a lazy "just take theirs" conflict resolution does, silently, to
    whoever you overwrote."""
    obstacles_dir = Path(__file__).parent.parent / "src" / "flappy" / "obstacles"
    module_files = {
        p.stem for p in obstacles_dir.glob("*.py") if p.stem not in ("__init__",)
    }
    assert len(module_files) == len(THEMES), (
        f"{len(module_files)} theme module(s) on disk but only {len(THEMES)} in THEMES -- "
        "someone's theme didn't make it into the registry"
    )
