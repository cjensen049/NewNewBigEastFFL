"""Shared player name matching utilities for dynasty ranking sources."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

try:
    from rapidfuzz import fuzz, process as rf_process
    _HAS_RAPIDFUZZ = True
except ImportError:
    _HAS_RAPIDFUZZ = False
    log.warning("rapidfuzz not installed — fuzzy name matching unavailable (pip install rapidfuzz)")

_SKILL_POSITIONS = {"QB", "RB", "WR", "TE"}
_SUFFIX_RE = re.compile(r"\b(jr\.?|sr\.?|ii|iii|iv)\b", re.IGNORECASE)
_NON_ALPHA_RE = re.compile(r"[^a-z ]")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """Lowercase, strip suffixes (Jr/Sr/II/III/IV), remove punctuation, collapse whitespace."""
    name = _SUFFIX_RE.sub("", name)
    name = _NON_ALPHA_RE.sub("", name.lower())
    return _WHITESPACE_RE.sub(" ", name).strip()


def build_name_index(players_json_path: Path | str) -> dict[str, str]:
    """
    Build {normalized_full_name: sleeper_id} from players.json cache.
    Only includes QB/RB/WR/TE.
    Returns empty dict if file does not exist.
    """
    path = Path(players_json_path)
    if not path.exists():
        log.warning("players.json not found at %s — name index will be empty", path)
        return {}

    raw: dict = json.loads(path.read_text(encoding="utf-8"))
    index: dict[str, str] = {}
    for player_id, player in raw.items():
        if not isinstance(player, dict):
            continue
        if player.get("position") not in _SKILL_POSITIONS:
            continue
        first = player.get("first_name") or ""
        last = player.get("last_name") or ""
        full = f"{first} {last}".strip()
        if not full:
            continue
        index[normalize_name(full)] = player_id

    return index


def load_aliases(aliases_path: Path | str) -> dict[str, str]:
    """
    Load {normalized_external_name: sleeper_id} from player_aliases.json.
    Returns empty dict if file does not exist.
    """
    path = Path(aliases_path)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def fuzzy_match(
    name: str,
    index: dict[str, str],
    aliases: dict[str, str] | None = None,
    threshold: int = 85,
) -> str | None:
    """
    Return sleeper_id for the best matching name, or None if below threshold.
    Checks explicit aliases first, then fuzzy-matches against the name index.
    Raises ImportError if rapidfuzz is not installed.
    """
    if not _HAS_RAPIDFUZZ:
        raise ImportError("rapidfuzz required for fuzzy matching: pip install rapidfuzz")

    normalized = normalize_name(name)

    if aliases and normalized in aliases:
        return aliases[normalized]

    if not index:
        return None

    match, score, _ = rf_process.extractOne(
        normalized, list(index.keys()), scorer=fuzz.token_sort_ratio
    )
    return index[match] if score >= threshold else None
