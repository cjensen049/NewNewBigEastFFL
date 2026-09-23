"""AI-generated weekly recap/preview paragraphs, cached per matchup.

Builds a compact facts package per matchup (final/projected scores, standout
and bust performances vs. that week's own pre-game projection, bye-week and
kickoff-slot context) and asks Claude for one short paragraph per matchup.
Generated once per week and cached in weekly_narratives -- pages never call
the LLM at request time.

Requires ANTHROPIC_API_KEY in the environment; if it's missing, generation
is skipped and the recap/preview panels just show the stats grid without
prose, same as if projections data were unavailable.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone

from fantasy_analyzer.analysis.roster_quality import select_optimal_lineup
from fantasy_analyzer.analysis.weekly_digest import get_weekly_preview, get_weekly_recap

log = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"

_NO_EM_DASH_RULE = (
    "Never use an em dash (—) or a double hyphen (--) as punctuation. Write in simpler "
    "sentences instead, and use commas or parentheses where you'd otherwise reach for a dash."
)

_RECAP_SYSTEM = (
    "You are a witty fantasy football beat writer. For each matchup you're given, write "
    "ONE short paragraph (2-4 sentences) recapping the result, in a punchy, conversational "
    "tone. Reference specific players by name, their point totals, and whether they beat or "
    "missed their usual per-game pace (the 'projected_rate' field) when notable. Mention the "
    "game-time slot (Thursday Night / Sunday Early / Sunday Late / Sunday Night / Monday Night) "
    "only when it adds real color, e.g. a game decided by a Monday night performance. Do not "
    "invent any facts not given to you -- if a field is null, just don't mention it. "
    f"{_NO_EM_DASH_RULE} Respond "
    "with ONLY a JSON array like [{\"matchup_id\": 1, \"text\": \"...\"}], no other text."
)

_PREVIEW_SYSTEM = (
    "You are a witty fantasy football beat writer previewing this week's matchups. For each "
    "matchup you're given, write ONE short paragraph (2-4 sentences): who's favored and by how "
    "much, standout projected performers by name, any bye-week absences worth flagging, and "
    "notable game-time slot concentration (e.g. several key starters all playing Monday night, "
    "adding late suspense). Do not invent any facts not given to you -- if a field is null or "
    f"empty, just don't mention it. {_NO_EM_DASH_RULE} Respond with ONLY a JSON array like "
    "[{\"matchup_id\": 1, \"text\": \"...\"}], no other text."
)


def _player_perf(con: sqlite3.Connection, player_id: str, actual_pts: float, season: int, week: int, slots: dict[str, str]) -> dict:
    row = con.execute("SELECT full_name, position, team FROM players WHERE player_id=?", (player_id,)).fetchone()
    name, position, team = row if row else (player_id, None, None)
    # That week's own pre-game projection, not the season-long average -- an
    # injured/doubtful player has no weekly projection at all that week, so
    # comparing against it (rather than a healthy season rate) reflects what
    # was actually expected of him going into that specific game.
    proj_row = con.execute(
        "SELECT projected_pts FROM player_projections WHERE season=? AND week=? AND player_id=?",
        (season, week, player_id),
    ).fetchone()
    projected_rate = round(proj_row[0], 1) if proj_row else None
    return {
        "name": name,
        "position": position,
        "points": round(actual_pts, 1),
        "projected_rate": projected_rate,
        "diff": round(actual_pts - projected_rate, 1) if projected_rate is not None else None,
        "slot": slots.get(team),
    }


def _build_recap_facts(con: sqlite3.Connection, league_id: str, season: int) -> tuple[int, list[dict]] | None:
    recap = get_weekly_recap(con, league_id, season)
    if not recap:
        return None
    week = recap["week"]
    slots = {r[0]: r[1] for r in con.execute("SELECT team, slot FROM game_slots WHERE season=? AND week=?", (season, week))}

    rows = con.execute(
        """SELECT o.canonical_name, m.starters_json, m.players_points_json
           FROM matchups m JOIN owners o ON o.user_id = m.user_id
           WHERE m.league_id=? AND m.week=? AND m.is_playoff=0""",
        (league_id, week),
    ).fetchall()

    perf_by_owner: dict[str, dict] = {}
    for name, starters_raw, pp_raw in rows:
        starters = json.loads(starters_raw) if starters_raw else []
        pp = json.loads(pp_raw) if pp_raw else {}
        performances = [_player_perf(con, pid, pp.get(pid) or 0.0, season, week, slots) for pid in starters]
        with_diff = [p for p in performances if p["diff"] is not None]
        perf_by_owner[name] = {
            "standout": max(with_diff, key=lambda p: p["diff"]) if with_diff else None,
            "bust": min(with_diff, key=lambda p: p["diff"]) if with_diff else None,
        }

    facts = [
        {
            "matchup_id": m["matchup_id"],
            "a": {**m["a"], **perf_by_owner.get(m["a"]["owner"], {})},
            "b": {**m["b"], **perf_by_owner.get(m["b"]["owner"], {})},
            "winner": m["winner"],
            "margin": m["margin"],
        }
        for m in recap["matchups"]
    ]
    return week, facts


def _build_preview_facts(con: sqlite3.Connection, league_id: str, season: int, pws: int) -> tuple[int, list[dict]] | None:
    preview = get_weekly_preview(con, league_id, season, pws)
    if not preview:
        return None
    week = preview["week"]
    slots = {r[0]: r[1] for r in con.execute("SELECT team, slot FROM game_slots WHERE season=? AND week=?", (season, week))}
    bye_teams = {r[0] for r in con.execute("SELECT team FROM nfl_byes WHERE season=? AND week=?", (season, week))}

    roster_by_owner: dict[str, int] = {
        r[0]: r[1] for r in con.execute(
            "SELECT o.canonical_name, lo.roster_id FROM league_owners lo "
            "JOIN owners o ON o.user_id = lo.user_id WHERE lo.league_id=?",
            (league_id,),
        )
    }

    def roster_context(owner: str) -> dict:
        roster_id = roster_by_owner.get(owner)
        if roster_id is None:
            return {"key_players": [], "bye_players": []}
        rows = con.execute(
            """SELECT p.full_name, p.position, p.team, wp.projected_pts
               FROM current_rosters cr
               JOIN players p ON p.player_id = cr.player_id
               LEFT JOIN player_projections wp ON wp.player_id = p.player_id AND wp.season=? AND wp.week=?
               WHERE cr.league_id=? AND cr.roster_id=?""",
            (season, week, league_id, roster_id),
        ).fetchall()
        # Pick "key players" from the ACTUAL optimal lineup, not just top-N raw
        # points -- otherwise a 2QB/superflex roster can surface 3 QBs as if
        # all three start, when the lineup only has room for 2.
        projected = [
            {"name": n, "position": pos, "team": team, "projected_pts": pts}
            for n, pos, team, pts in rows if pts is not None
        ]
        starters = select_optimal_lineup(projected)
        top3 = sorted(starters, key=lambda p: -p["projected_pts"])[:3]
        return {
            "key_players": [
                {"name": p["name"], "position": p["position"], "projected_rate": round(p["projected_pts"], 1),
                 "slot": slots.get(p["team"])}
                for p in top3
            ],
            "bye_players": [
                {"name": n, "position": pos} for n, pos, team, _ in rows if team in bye_teams
            ],
        }

    facts = [
        {
            "matchup_id": m["matchup_id"],
            "a": {**m["a"], **roster_context(m["a"]["owner"])},
            "b": {**m["b"], **roster_context(m["b"]["owner"])},
            "proj_gap": m["proj_gap"],
        }
        for m in preview["matchups"]
    ]
    return week, facts


def _call_claude(system: str, facts: list[dict]) -> dict[int, str]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.warning("ANTHROPIC_API_KEY not set -- skipping narrative generation")
        return {}
    try:
        import anthropic
    except ImportError:
        log.warning("anthropic package not installed -- skipping narrative generation")
        return {}

    client = anthropic.Anthropic(api_key=api_key)
    try:
        resp = client.messages.create(
            model=_MODEL,
            max_tokens=2048,
            system=system,
            messages=[
                {"role": "user", "content": json.dumps(facts)},
                # Prefilling the assistant turn with "[" strongly discourages Claude from
                # wrapping the reply in a ```json code fence despite the system prompt.
                {"role": "assistant", "content": "["},
            ],
        )
        raw = "[" + resp.content[0].text
        parsed = json.loads(_strip_code_fence(raw))
        return {int(item["matchup_id"]): item["text"] for item in parsed}
    except Exception as e:
        log.warning("Claude narrative generation failed: %s; raw response: %.500s", e, locals().get("raw", "<no response>"))
        return {}


def _strip_code_fence(text: str) -> str:
    """Remove a leading ```json / trailing ``` fence, if Claude added one anyway."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _store_narratives(con: sqlite3.Connection, league_id: str, season: int, week: int, kind: str, texts: dict[int, str]) -> int:
    if not texts:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    con.executemany(
        """INSERT INTO weekly_narratives (league_id, season, week, kind, matchup_id, text, generated_at)
           VALUES (?,?,?,?,?,?,?)
           ON CONFLICT(league_id, season, week, kind, matchup_id) DO UPDATE SET
               text = excluded.text, generated_at = excluded.generated_at""",
        [(league_id, season, week, kind, mid, text, now) for mid, text in texts.items()],
    )
    con.commit()
    return len(texts)


def run_recap_narratives(con: sqlite3.Connection, league_id: str, season: int) -> int:
    """Generate and store this league's recap paragraphs for the last completed week."""
    built = _build_recap_facts(con, league_id, season)
    if not built:
        return 0
    week, facts = built
    texts = _call_claude(_RECAP_SYSTEM, facts)
    return _store_narratives(con, league_id, season, week, "recap", texts)


def run_preview_narratives(con: sqlite3.Connection, league_id: str, season: int, pws: int) -> int:
    """Generate and store this league's preview paragraphs for the upcoming week."""
    built = _build_preview_facts(con, league_id, season, pws)
    if not built:
        return 0
    week, facts = built
    texts = _call_claude(_PREVIEW_SYSTEM, facts)
    return _store_narratives(con, league_id, season, week, "preview", texts)
