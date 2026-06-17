"""Shared draft pick name parsing for dynasty valuation scrapers.

Both DynastyProcess and FantasyCalc name future draft picks the same way
(e.g. "2027 Pick 1.01"), so this parsing logic is shared between their
scrapers rather than duplicated.
"""

from __future__ import annotations

import re


def pick_tier(pick_num: int) -> str:
    """Map a pick number within a round to a tier label."""
    if pick_num <= 4:
        return "early"
    if pick_num <= 8:
        return "mid"
    return "late"


def parse_pick_name(name: str) -> tuple[int, int, str] | None:
    """Parse a dynasty value source's pick name into (season, round, tier).

    Handles two formats:
      "2027 Pick 1.01"   -> (2027, 1, 'early')
      "2027 Early 1st"   -> (2027, 1, 'early')
    """
    name = name.strip()

    # Format 1: "2027 Pick R.SS"  (R=round, SS=slot 01-12)
    m = re.match(r"(\d{4})\s+Pick\s+(\d+)\.(\d+)", name, re.IGNORECASE)
    if m:
        season = int(m.group(1))
        rnd = int(m.group(2))
        slot = int(m.group(3))
        return season, rnd, pick_tier(slot)

    # Format 2: "2027 Early 1st" / "2027 Mid 2nd" / "2027 Late 3rd"
    m = re.match(
        r"(\d{4})\s+(Early|Mid|Late)\s+(\d+)(?:st|nd|rd|th)?",
        name, re.IGNORECASE,
    )
    if m:
        season = int(m.group(1))
        tier = m.group(2).lower()
        rnd = int(m.group(3))
        return season, rnd, tier

    return None
