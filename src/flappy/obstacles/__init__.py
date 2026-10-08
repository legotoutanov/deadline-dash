"""The registry of grass themes -- cosmetic flavour for the obstacles, all
built on the same underlying mechanic (a gap you fly through; everywhere
else is grass you're not allowed to walk on). Each theme lives in its own
module, imported here, exactly so two people can add one each without
touching each other's files -- except this file itself, which is where
Friday's exercise lives.

To add your own: copy the pattern in old_court.py, give your college or
society its own grass, then wire it in below (import, CONTRIBUTORS, and
the THEMES tuple), all in alphabetical order by module name.
"""

from __future__ import annotations

from ..models import ObstacleTheme
from .old_court import OLD_COURT
from .the_backs import THE_BACKS

# --- add new imports above this line ---

CONTRIBUTORS: tuple[str, ...] = ()

# --- add your name to CONTRIBUTORS above this line ---

THEMES: tuple[ObstacleTheme, ...] = (
    OLD_COURT,
    THE_BACKS,
)

# --- add your theme to THEMES above this line ---
