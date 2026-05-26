# errors.md - Error Log & Known Issues

This file tracks bugs, API quirks, unexpected data shapes, and unresolved issues. Claude Code should read this before touching any module that appears here, and add entries whenever something unexpected is encountered.

---

## How to Use This File

- **Add an entry** any time an API response behaves unexpectedly, a bug is found, or a workaround is applied
- **Mark resolved** entries with `[RESOLVED]` and the date -- do not delete them (history is valuable)
- **Reference entries** by their ID (e.g., `ERR-001`) in code comments when a workaround is in place

---

## Open Issues

_None yet. Entries will be added during development._

---

## Issue Template

```
### ERR-XXX: Short description
**Date:** YYYY-MM-DD
**Severity:** Low | Medium | High | Blocking
**Module:** fantasy_analyzer/...
**Status:** Open | In Progress | Resolved

**Description:**
What happened and where.

**Reproduction:**
How to reproduce it (league ID, week, endpoint, etc.).

**Root Cause:**
What caused it (if known).

**Workaround / Fix:**
What was done to handle it. If a workaround, note what a proper fix would look like.

**Code Reference:**
File and line number where workaround is applied, if any.
```

---

## Known Sleeper API Quirks (Pre-documented)

These are issues documented in advance based on known Sleeper API behavior. They are not bugs in this project, but edge cases to handle defensively.

### QUIRK-001: Matchup pairing requires client-side grouping
**Endpoint:** `GET /league/{league_id}/matchups/{week}`
**Description:** The response is a flat list of roster objects, each with a `matchup_id`. Teams in the same matchup share the same `matchup_id`. There is no direct "home vs away" structure. You must `groupby('matchup_id')` and pair the two rosters yourself.
**Handling:** Always group by `matchup_id` and assert exactly 2 teams per group (except bye weeks in playoffs where one team may be missing).

---

### QUIRK-002: Playoff weeks may have null scores
**Endpoint:** `GET /league/{league_id}/matchups/{week}`
**Description:** Teams eliminated in the first playoff round may appear in later weeks with `null` or `0` points if they are in a consolation bracket that was not played. Some leagues do not run out a full bracket.
**Handling:** Treat `null` points as 0 for storage. Flag these in analysis as "did not play" rather than actual 0-point performances.

---

### QUIRK-003: `/players/nfl` returns a very large payload
**Endpoint:** `GET /players/nfl`
**Description:** This endpoint returns metadata for all players across all sports Sleeper supports (NFL, NBA, etc. depending on version). The payload can be 10MB+.
**Handling:** Cache to `data/players.json` immediately. Filter on load: keep only records where `sport == "nfl"`. Refresh no more than once per week.

---

### QUIRK-004: Draft pick objects in trades are inconsistently shaped
**Endpoint:** `GET /league/{league_id}/transactions/{week}`
**Description:** In the `draft_picks` array of a trade transaction, picks sometimes include `season` as a string and sometimes as an integer. The `round` field is always an integer. Some picks lack `previous_owner_id` if they were never previously traded.
**Handling:** Always cast `season` to `int`. Default `previous_owner_id` to `None` if absent. Validate pick objects before inserting and log any that are missing required fields.

---

### QUIRK-005: Commissioner transactions can be ignored
**Endpoint:** `GET /league/{league_id}/transactions/{week}`
**Description:** Transactions with `type == "commissioner"` represent manual adjustments made by the league commissioner (score corrections, etc.). These are not player movement events and should not appear in trade trees or waiver analysis.
**Handling:** Filter out all `type == "commissioner"` records before processing.

---

### QUIRK-006: `previous_league_id` may be "0" or null for the founding season
**Endpoint:** `GET /league/{league_id}`
**Description:** When walking the season chain backward via `previous_league_id`, the oldest season will have this field set to `"0"` (a string zero) or `null`. Both indicate the end of the chain.
**Handling:** Stop chain traversal when `previous_league_id` is `null`, `"0"`, or `0`.

---

### QUIRK-007: User display names and avatar IDs can change between seasons
**Endpoint:** `GET /league/{league_id}/users`
**Description:** A user's `display_name` and team name (`metadata.team_name`) are mutable -- owners rename their teams every season. The only stable identifier is `user_id`.
**Handling:** Always join on `user_id`. Store display names per-season for historical accuracy but use `user_id` as the primary key in the `owners` table.

---

## Resolved Issues

_None yet._

---

## Error Severity Guide

| Severity | Meaning |
|---|---|
| **Low** | Cosmetic or edge case -- does not affect core analysis |
| **Medium** | Affects some data accuracy but workaround is in place |
| **High** | Affects core features; needs a real fix soon |
| **Blocking** | Prevents ingestion or analysis from running at all |
