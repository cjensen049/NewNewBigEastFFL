# memory.md - Session Progress Log

This file tracks what has been built, what is in progress, and what comes next. Claude Code should read this at the start of every session and update it at the end.

---

## Project Status: INGESTION COMPLETE — FRONTEND BUILT, NOT YET DEPLOYED

**Last updated:** 2026-05-25
**Current phase:** Frontend deployment + analysis layer (rivalries, trade trees)

---

## What Has Been Built

| Module | Status | Notes |
|---|---|---|
| `pyproject.toml` | Done | build-backend = setuptools.build_meta |
| `requirements.txt` | Done | Includes streamlit, plotly, certifi |
| `config.yaml` | Done | All 6 seasons + 13 owners configured |
| `.gitignore` | Done | At repo root (NNBE History/), excludes players.json, keeps league.db |
| `fantasy_analyzer/api/sleeper.py` | Done | verify=False for httpx (Windows Store Python SSL issue) |
| `fantasy_analyzer/api/models.py` | Done | Pydantic v2 models for all Sleeper shapes |
| `fantasy_analyzer/db/schema.py` | Done | SQLite schema, all tables, WAL mode |
| `fantasy_analyzer/db/store.py` | Done | All CRUD helpers, idempotent upserts |
| `fantasy_analyzer/ingest.py` | Done | Full pipeline, rich progress output |
| `fantasy_analyzer/cli.py` | Done | `ingest` and `report standings` commands |
| `fantasy_analyzer/analysis/history.py` | Done | All-time + season standings, full playoff finish detection |
| `fantasy_analyzer/reports/terminal.py` | Done | Rich CLI tables (width=120 for Windows) |
| `streamlit_app.py` | Done | 4 pages: Overview, Owner Profile, Season, H2H |
| `fantasy_analyzer/analysis/transactions.py` | Not started | Trade trees, waiver analysis |
| `fantasy_analyzer/analysis/rivalries.py` | Not started | Head-to-head, nemesis logic |
| Tests | Not started | |

---

## League IDs Configured

| Season | League ID | Name | Ingested? |
|---|---|---|---|
| 2026 | 1314316658872979456 | The New New Big East | Yes (pre-draft, no matchups yet) |
| 2025 | 1182090817286635520 | The New New Big East | Yes |
| 2024 | 1049028752438616064 | The New New Big East | Yes |
| 2023 | 918166251111993344 | The New New Big East | Yes |
| 2022 | 784433157503037440 | The New New Big East | Yes |
| 2021 | 673580972368801792 | The New New Big East | Yes |

---

## Owner Mapping

| Canonical Name | Sleeper User ID | Sleeper Username | Active Through |
|---|---|---|---|
| Andy | 689875084793438208 | AKaiser25 | 2026 |
| Chase | 686048277128359936 | DickOsgood | 2026 |
| Eric | 685580600140185600 | Epatnode | 2026 |
| John | 733163469704151040 | JWalsh883 | 2026 (new in 2026) |
| Rick | 685556523568541696 | YOURGODKING | 2026 |
| Chris | 685553516458106880 | chrisokeefe90 | 2026 |
| Jensen | 459390418249838592 | cjensen | 2026 |
| Casey | 686282087371714560 | csefton21 | 2026 |
| Sean | 460621169834323968 | mccartsp12 | 2026 |
| Matt | 685564883013550080 | mjohn7wy | 2026 |
| Turo | 685554560860790784 | mturo | 2026 |
| Tom | 98448185739329536 | tomok1 | 2026 |
| Ian | 684860052317773824 | itblumenfeld | 2025 (replaced by John in 2026) |

---

## Database State

- **DB path:** `fantasy-analyzer/data/league.db`
- **Schema version:** current
- **Rows ingested:**
  - owners: 13
  - leagues: 6
  - league_owners: 72
  - matchups: 980
  - season_records: 72
  - transactions: 2,233 (227 trades, 1,292 waivers, 714 free agent)
  - transaction_draft_picks: 417
  - drafts: 6
  - draft_picks: 540
  - players: 4,250

---

## Key Findings (for context)

- **League name:** "The New New Big East" (NNBE)
- **Playoff structure:** 12 teams, 6 playoff spots, 3 weeks (wk15-17). matchup_id ≤ 3 = championship bracket; matchup_id ≥ 4 = toilet bowl bracket. Champion = winner of matchup_id=1 in wk17. Last place = loser of matchup_id=5 in wk17.
- **SSL issue:** httpx fails on Windows Store Python. Fixed with `verify=False` (public read-only API, no credentials).
- **Windows encoding:** Rich console requires `width=120`; no em dashes or emoji in output.
- **All-time leader:** Turo (74.3% win rate, 2 championships, 5/5 playoff appearances)
- **Most pts scored:** Matt (9,334 total, 133.3 PPG) — 1 championship
- **Most last places:** Ian (3x, in 2021/2022/2024) — 0 playoff appearances in 5 seasons
- **Odd stat:** Chase won the 2021 championship despite all-time 31.4% win rate

---

## Decisions Made

- Static data strategy: run ingest locally, commit DB, deploy to Streamlit Cloud
- Use `verify=False` for httpx (Windows Store Python SSL cert issue, public API)
- Streamlit for frontend (shareable with league via free Streamlit Community Cloud)
- `fantasy-analyzer/` is the Python project root; `streamlit_app.py` lives there
- `.gitignore` is at `NNBE History/` (repo root), not inside `fantasy-analyzer/`
- `players.json` excluded from git (10MB+, regenerated weekly); `league.db` committed

---

## In Progress

- Streamlit app built but not yet deployed (GitHub repo not yet created)

---

## Up Next (ordered)

1. **GitHub setup:** `git init` in `NNBE History/`, create remote repo, push
2. **Streamlit Cloud deployment:** connect GitHub repo, deploy `fantasy-analyzer/streamlit_app.py`
3. **rivalries.py:** head-to-head matrix, nemesis detection (owner beaten most by a single opponent)
4. **transactions.py:** trade tree reconstruction across seasons, waiver wire tendencies per owner
5. **Add Streamlit pages** for rivalries and trade trees once analysis is done
6. **Tests** with fixture data

---

## API Observations

- `previous_league_id` chain works correctly; all 6 seasons discovered via walk
- 2026 season is pre_draft — no matchup data, no draft picks yet
- Player cache (`/players/nfl`) returned 4,250 NFL skill position players
- Transactions filtered to exclude `type == "commissioner"` before storage

---

## Session Log

### Session 1 — 2026-05-25
- Initialized project structure files (CLAUDE.md, memory.md, errors.md, prompt.md)
- No code written

### Session 2 — 2026-05-25
- Confirmed 6 seasons (2021-2026) via league_ids.txt
- Identified all 13 owners (12 active in 2026, Ian replaced by John)
- Created full `fantasy-analyzer/` project structure and all stub files
- Built `pyproject.toml`, `config.yaml`, `requirements.txt`, `.gitignore`
- Built `api/models.py`, `api/sleeper.py` (with verify=False SSL fix)
- Built `db/schema.py`, `db/store.py`, `ingest.py`, `cli.py`
- Ran full ingest across all 6 seasons successfully
- Built `analysis/history.py` with full playoff bracket detection
- Built `reports/terminal.py` with Windows-safe rich output
- Built `streamlit_app.py` with 4 pages (Overview, Owner Profile, Season, H2H)
- App verified working locally; GitHub/deployment pending for next session
