# CLAUDE.md - Fantasy Football League Analyzer

This file is the source of truth for Claude Code when working on this project. Read it fully at the start of every session.

---

## Project Overview

A Python CLI tool that pulls Sleeper fantasy football league data and produces historical analysis across multiple seasons. The tool chains league seasons together via Sleeper's `previous_league_id` field to reconstruct full multi-year history for a group of owners.

**Primary goals:**
- Persistent local storage of all Sleeper API data
- Multi-season owner tracking (owners persist across league IDs)
- Trade tree reconstruction across seasons
- Rivalry, nemesis, and head-to-head analysis
- Transaction pattern analysis per owner

---

## Always Do at Session Start

1. Read `memory.md` to understand where the project left off
2. Read `errors.md` to be aware of known issues before touching related code
3. Check which modules exist before creating new ones -- avoid duplication

---

## Tech Stack

| Concern | Choice |
|---|---|
| Language | Python 3.11+ |
| HTTP client | `httpx` (async preferred) |
| Data storage | SQLite via `sqlite3` or `aiosqlite` |
| Data analysis | `pandas` |
| Terminal output | `rich` |
| Config | `PyYAML` + `config.yaml` |
| Models | `pydantic` v2 |
| Packaging | `pyproject.toml` |
| Testing | `pytest` + `pytest-asyncio` |

---

## Project Structure

```
fantasy-analyzer/
├── pyproject.toml
├── config.yaml              # league IDs, owner mappings, settings
├── CLAUDE.md                # this file
├── memory.md                # session state and progress log
├── errors.md                # error log and known issues
├── fantasy_analyzer/
│   ├── __init__.py
│   ├── cli.py
│   ├── api/
│   │   ├── sleeper.py       # Sleeper API client
│   │   └── models.py        # Pydantic response models
│   ├── db/
│   │   ├── schema.py        # table definitions and migrations
│   │   └── store.py         # CRUD helpers
│   ├── analysis/
│   │   ├── history.py       # season records, standings, playoffs
│   │   ├── transactions.py  # trade trees, waiver stats
│   │   └── rivalries.py     # head-to-head, nemesis detection
│   └── reports/
│       ├── terminal.py      # rich tables and panels
│       └── export.py        # JSON and CSV output
└── tests/
    ├── test_api.py
    ├── test_analysis.py
    └── fixtures/            # static API responses for offline tests
```

---

## Sleeper API Rules

- **Base URL:** `https://api.sleeper.app/v1`
- No authentication required for public endpoints
- **Rate limit:** Be conservative -- add 0.5s delay between sequential calls in loops
- **Player endpoint** (`GET /players/nfl`) returns a massive payload -- cache it to `data/players.json` and only refresh weekly
- Matchup data requires iterating weeks 1 through `settings.playoff_week_start + 3` (or league's `last_scored_leg`)
- Transactions are fetched per week -- iterate all weeks for full history
- The `previous_league_id` field on a league object links to the prior season's league -- follow this chain to get full history

### Key Endpoints

```
GET /league/{league_id}
GET /league/{league_id}/rosters
GET /league/{league_id}/users
GET /league/{league_id}/matchups/{week}       # weeks 1..N
GET /league/{league_id}/transactions/{week}   # weeks 1..N
GET /league/{league_id}/drafts
GET /draft/{draft_id}/picks
GET /players/nfl
```

---

## Data Model Notes

### Owner Identity
Owners have a Sleeper `user_id` that is stable across seasons. Always anchor owner identity to `user_id`, not `display_name` or team name (those change). Store a canonical owner record in the `owners` table.

### Trade Trees
A trade tree node contains:
- `transaction_id`
- `league_id` + `season`
- Assets going each direction (player IDs and/or draft pick descriptors)
- Links to child transactions (where traded assets appear next)

Build this as a recursive structure. Store edges in a `trade_tree_edges` table: `(from_transaction_id, to_transaction_id, asset_id, asset_type)`.

### Draft Pick Tracking
Sleeper represents future picks as objects with `season`, `round`, `roster_id` (original owner), and `owner_id` (current owner). When a pick is traded, its `owner_id` changes. When it is used in a draft, link it to the resulting `pick` record.

---

## Code Standards

- All functions must have docstrings
- Use type hints everywhere
- API calls must have retry logic (3 attempts, exponential backoff)
- Never hardcode league IDs -- always read from `config.yaml`
- Database writes must use transactions -- no partial state
- Tests must cover all analysis functions; API calls should use fixture data

---

## Config Format (`config.yaml`)

```yaml
leagues:
  - id: "123456789"
    season: 2024
    name: "The League Season 7"
  - id: "987654321"
    season: 2023
    name: "The League Season 6"

owners:
  - user_id: "abc123"
    canonical_name: "Mike"
  - user_id: "def456"
    canonical_name: "Sarah"

settings:
  db_path: "data/league.db"
  player_cache_path: "data/players.json"
  player_cache_ttl_days: 7
  api_delay_seconds: 0.5
  log_level: "INFO"
```

---

## CLI Commands (target interface)

```bash
# Ingest all data for configured leagues
python -m fantasy_analyzer ingest

# Ingest a specific league
python -m fantasy_analyzer ingest --league-id 123456789

# Show all-time standings
python -m fantasy_analyzer report standings

# Show head-to-head between two owners
python -m fantasy_analyzer report h2h --owner1 "Mike" --owner2 "Sarah"

# Show trade tree for a player
python -m fantasy_analyzer report trade-tree --player "Tyreek Hill"

# Export full history to JSON
python -m fantasy_analyzer export --format json --out data/history.json
```

---

## Common Pitfalls

- Sleeper's `matchups` endpoint returns a flat list -- you must group by `matchup_id` to pair opponents
- Some weeks return `null` scores for teams on bye in playoffs -- handle gracefully
- `transactions` of type `commissioner` can be ignored for analysis purposes
- Draft picks in trades are sometimes represented inconsistently -- always validate pick objects before storing
- The `/players/nfl` endpoint returns ALL sports at times -- filter by `sport == "nfl"` and `position` in `["QB","RB","WR","TE","K","DEF"]`
