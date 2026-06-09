# CLAUDE.md - Fantasy Football League Analyzer

This file is the source of truth for Claude Code when working on this project. Read it fully at the start of every session.

---

## Project Overview

A full-stack fantasy football league analytics web application. The backend is FastAPI (Python), the frontend is React + Vite. Data is pulled from the Sleeper public API and persisted in SQLite. The app is deployed to Railway and served at nnbefootball.com.

**Primary goals:**
- Persistent local storage of all Sleeper API data
- Multi-season owner tracking (owners persist across league IDs)
- Trade tree reconstruction across seasons
- Rivalry, nemesis, and head-to-head analysis
- Transaction pattern analysis per owner
- Clean web UI accessible at nnbefootball.com

**Important context:** The frontend developer has no React experience. Keep frontend code well-commented, simple, and consistent. When in doubt, follow the History page pattern.

---

## Always Do at Session Start

1. Read `memory.md` to understand where the project left off
2. Read `errors.md` to be aware of known issues before touching related code
3. Check which modules exist before creating new ones -- avoid duplication

---

## Tech Stack

### Backend
| Concern | Choice |
|---|---|
| Language | Python 3.11+ |
| Web framework | FastAPI + Uvicorn |
| HTTP client | `httpx` (async) |
| Data storage | SQLite via `aiosqlite` |
| Data analysis | `pandas` |
| Models | `pydantic` v2 |
| Config | `PyYAML` + `config.yaml` |
| Packaging | `pyproject.toml` |
| Testing | `pytest` + `pytest-asyncio` |

### Frontend
| Concern | Choice |
|---|---|
| Framework | React 18 |
| Build tool | Vite |
| Styling | Tailwind CSS |
| Routing | React Router v6 |
| Data fetching | TanStack Query (React Query) |
| Language | JavaScript (JSX) -- no TypeScript |

### Infrastructure
| Concern | Choice |
|---|---|
| Hosting | Railway |
| Domain | nnbefootball.com (Google Domains CNAME) |
| CI/CD | GitHub Actions (weekly data refresh) |
| Container | Dockerfile (FastAPI serves API + built React static files) |

### Git / Deployment Workflow

**ALWAYS push to `staging` first. Never push directly to `master` unless the user explicitly says to deploy to production.**

| Branch | Environment |
|---|---|
| `staging` | Railway staging (review before going live) |
| `master` | Railway production — nnbefootball.com |

Standard flow for any change:
1. Make changes on `master` locally (or `staging`)
2. Switch to `staging`: `git checkout staging`
3. Merge master: `git merge master --no-edit`
4. Push: `git push origin staging`
5. Only merge `staging → master` and push master when the user explicitly says "push to production" or "deploy".

---

## Project Structure

```
fantasy-analyzer/
├── pyproject.toml
├── config.yaml                   # league IDs, owner mappings, settings
├── Dockerfile                    # Railway deployment
├── CLAUDE.md                     # this file
├── memory.md                     # session state and progress log
├── errors.md                     # error log and known issues
├── backend/
│   ├── main.py                   # FastAPI app entry point
│   ├── routers/
│   │   ├── history.py
│   │   ├── owner.py
│   │   ├── h2h.py
│   │   ├── transactions.py
│   │   └── in_season.py
│   └── fantasy_analyzer/
│       ├── api/
│       │   ├── sleeper.py
│       │   └── models.py
│       ├── db/
│       │   ├── schema.py
│       │   └── store.py
│       └── analysis/
│           ├── history.py
│           ├── transactions.py
│           └── rivalries.py
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── components/
│       └── pages/
│           ├── History.jsx       # REFERENCE PATTERN for all pages
│           ├── Owner.jsx
│           ├── HeadToHead.jsx
│           ├── Transactions.jsx
│           └── InSeason.jsx
└── tests/
    ├── test_api.py
    ├── test_analysis.py
    └── fixtures/
```

---

## How FastAPI Serves the Frontend

In production, FastAPI serves the built React app as static files. The pattern in `main.py`:

```python
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI

app = FastAPI()

# API routes registered first
app.include_router(history_router, prefix="/api/history")
# ... other routers

# Static files catch-all (must be last)
app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")
```

In development, Vite runs on port 5173 and proxies `/api/*` calls to FastAPI on port 8000 via `vite.config.js`.

---

## Frontend Page Pattern (follow History.jsx)

Every page should follow this structure:

```jsx
import { useQuery } from '@tanstack/react-query'

// 1. Define the fetch function
async function fetchData() {
  const res = await fetch('/api/route')
  if (!res.ok) throw new Error('Failed to fetch')
  return res.json()
}

// 2. Export a default function component named after the page
export default function PageName() {
  // 3. Use useQuery to load data
  const { data, isLoading, error } = useQuery({
    queryKey: ['unique-key'],
    queryFn: fetchData,
  })

  // 4. Handle loading and error states
  if (isLoading) return <div>Loading...</div>
  if (error) return <div>Error: {error.message}</div>

  // 5. Render the data
  return (
    <div>
      {/* page content */}
    </div>
  )
}
```

---

## API Endpoint Convention

```
GET /api/history/standings
GET /api/history/records
GET /api/history/weekly-scoring
GET /api/history/champions
GET /api/owner/{owner_id}
GET /api/h2h?owner1={id}&owner2={id}
GET /api/transactions?type={type}&owner={id}
GET /api/in-season/current
```

All endpoints return JSON. Errors return `{ "detail": "message" }` with appropriate HTTP status codes.

---

## Sleeper API Rules

- **Base URL:** `https://api.sleeper.app/v1`
- No authentication required for public endpoints
- **Rate limit:** Add 0.5s delay between sequential calls in loops
- **Player endpoint** (`GET /players/nfl`) returns a massive payload -- cache to `data/players.json`, refresh weekly
- Matchup data requires iterating weeks 1 through `settings.playoff_week_start + 3`
- Transactions are fetched per week -- iterate all weeks for full history
- The `previous_league_id` field links to the prior season -- follow this chain for full history

### Key Endpoints

```
GET /league/{league_id}
GET /league/{league_id}/rosters
GET /league/{league_id}/users
GET /league/{league_id}/matchups/{week}
GET /league/{league_id}/transactions/{week}
GET /league/{league_id}/drafts
GET /draft/{draft_id}/picks
GET /players/nfl
```

---

## Data Model Notes

### Owner Identity
Owners have a Sleeper `user_id` stable across seasons. Always anchor to `user_id`, not `display_name` or team name. Store a canonical owner record in the `owners` table.

### Trade Trees
A trade tree node contains:
- `transaction_id`, `league_id`, `season`
- Assets going each direction (player IDs and/or draft pick descriptors)
- Links to child transactions (where traded assets appear next)

Store edges in a `trade_tree_edges` table: `(from_transaction_id, to_transaction_id, asset_id, asset_type)`.

### Draft Pick Tracking
Sleeper represents future picks with `season`, `round`, `roster_id` (original owner), and `owner_id` (current owner). When a pick is traded, `owner_id` changes. When used in a draft, link it to the resulting pick record.

---

## Verification Policy

Do **not** start local dev servers (uvicorn, `npm run dev`) to verify UI changes. Playwright is not installed and screenshot automation is not available in this environment. Instead, hand completed changes back to the user for visual review. State clearly what was changed and what to look for when they open the app.

---

## Code Standards

- All Python functions must have docstrings
- Use type hints everywhere in Python
- API calls must have retry logic (3 attempts, exponential backoff)
- Never hardcode league IDs -- always read from `config.yaml`
- Database writes must use transactions -- no partial state
- Frontend components must have a comment block describing what they render
- Tests must cover all analysis functions; API calls use fixture data

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

## Common Pitfalls

- Sleeper's `matchups` endpoint returns a flat list -- group by `matchup_id` to pair opponents
- Some weeks return `null` scores for teams on bye in playoffs -- handle gracefully
- `transactions` of type `commissioner` can be ignored
- Draft picks in trades are sometimes inconsistently shaped -- validate before storing
- The `/players/nfl` endpoint may include non-NFL sports -- filter by `sport == "nfl"`
- In development, Vite and FastAPI run on separate ports -- always proxy `/api/*` through Vite config
- React Router requires the FastAPI catch-all to serve `index.html` for all non-API routes
