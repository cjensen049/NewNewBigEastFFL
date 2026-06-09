"""SQLite table definitions and schema migrations."""

from __future__ import annotations

import aiosqlite

DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS owners (
    user_id         TEXT PRIMARY KEY,
    canonical_name  TEXT NOT NULL,
    sleeper_username TEXT,
    joined_season   INTEGER,
    departed_after  INTEGER
);

CREATE TABLE IF NOT EXISTS leagues (
    league_id       TEXT PRIMARY KEY,
    season          INTEGER NOT NULL,
    name            TEXT,
    status          TEXT,
    total_rosters   INTEGER,
    playoff_week_start INTEGER,
    last_scored_leg INTEGER
);

CREATE TABLE IF NOT EXISTS league_owners (
    league_id   TEXT NOT NULL REFERENCES leagues(league_id),
    user_id     TEXT NOT NULL REFERENCES owners(user_id),
    roster_id   INTEGER NOT NULL,
    team_name   TEXT,
    PRIMARY KEY (league_id, user_id)
);

CREATE TABLE IF NOT EXISTS matchups (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    league_id       TEXT NOT NULL REFERENCES leagues(league_id),
    season          INTEGER NOT NULL,
    week            INTEGER NOT NULL,
    matchup_id      INTEGER NOT NULL,
    roster_id       INTEGER NOT NULL,
    user_id         TEXT REFERENCES owners(user_id),
    points          REAL,
    is_playoff      INTEGER NOT NULL DEFAULT 0,
    starters_json       TEXT,
    players_points_json TEXT,
    UNIQUE(league_id, week, roster_id)
);

CREATE TABLE IF NOT EXISTS season_records (
    league_id   TEXT NOT NULL REFERENCES leagues(league_id),
    user_id     TEXT NOT NULL REFERENCES owners(user_id),
    season      INTEGER NOT NULL,
    wins        INTEGER NOT NULL DEFAULT 0,
    losses      INTEGER NOT NULL DEFAULT 0,
    ties        INTEGER NOT NULL DEFAULT 0,
    fpts        REAL NOT NULL DEFAULT 0,
    fpts_against REAL NOT NULL DEFAULT 0,
    ppts        REAL NOT NULL DEFAULT 0,
    made_playoffs INTEGER NOT NULL DEFAULT 0,
    playoff_wins  INTEGER NOT NULL DEFAULT 0,
    champion      INTEGER NOT NULL DEFAULT 0,
    last_place    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (league_id, user_id)
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id  TEXT PRIMARY KEY,
    league_id       TEXT NOT NULL REFERENCES leagues(league_id),
    season          INTEGER NOT NULL,
    week            INTEGER,
    type            TEXT NOT NULL,
    status          TEXT,
    created_epoch   INTEGER,
    adds_json       TEXT,
    drops_json      TEXT,
    roster_ids_json TEXT,
    waiver_budget_json TEXT,
    waiver_bid_amount  INTEGER
);

CREATE TABLE IF NOT EXISTS transaction_draft_picks (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id      TEXT NOT NULL REFERENCES transactions(transaction_id),
    season              INTEGER NOT NULL,
    round               INTEGER NOT NULL,
    original_roster_id  INTEGER NOT NULL,
    from_roster_id      INTEGER NOT NULL,
    to_roster_id        INTEGER NOT NULL,
    UNIQUE(transaction_id, season, round, original_roster_id)
);

CREATE TABLE IF NOT EXISTS trade_tree_edges (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    from_transaction_id TEXT REFERENCES transactions(transaction_id),
    to_transaction_id   TEXT NOT NULL REFERENCES transactions(transaction_id),
    asset_id            TEXT NOT NULL,
    asset_type          TEXT NOT NULL  -- 'player' or 'pick'
);

CREATE TABLE IF NOT EXISTS drafts (
    draft_id    TEXT PRIMARY KEY,
    league_id   TEXT NOT NULL REFERENCES leagues(league_id),
    season      INTEGER NOT NULL,
    type        TEXT,
    status      TEXT
);

CREATE TABLE IF NOT EXISTS draft_picks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_id    TEXT NOT NULL REFERENCES drafts(draft_id),
    league_id   TEXT NOT NULL,
    season      INTEGER NOT NULL,
    round       INTEGER NOT NULL,
    pick_no     INTEGER NOT NULL,
    roster_id   INTEGER,
    user_id     TEXT REFERENCES owners(user_id),
    player_id   TEXT,
    player_name TEXT,
    draft_slot  INTEGER,
    UNIQUE(draft_id, pick_no)
);

CREATE TABLE IF NOT EXISTS players (
    player_id   TEXT PRIMARY KEY,
    full_name   TEXT,
    position    TEXT,
    team        TEXT
);

CREATE TABLE IF NOT EXISTS player_projections (
    season          INTEGER NOT NULL,
    week            INTEGER NOT NULL,
    player_id       TEXT    NOT NULL,
    position        TEXT    NOT NULL,
    projected_pts   REAL    NOT NULL,
    scraped_at      TEXT    NOT NULL,
    PRIMARY KEY (season, week, player_id)
);

CREATE TABLE IF NOT EXISTS current_rosters (
    league_id   TEXT    NOT NULL,
    roster_id   INTEGER NOT NULL,
    player_id   TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'active',
    updated_at  TEXT    NOT NULL,
    PRIMARY KEY (league_id, roster_id, player_id)
);

CREATE TABLE IF NOT EXISTS player_dynasty_values (
    player_id   TEXT    NOT NULL,
    value       REAL    NOT NULL,
    age         REAL,
    scraped_at  TEXT    NOT NULL,
    PRIMARY KEY (player_id)
);

CREATE TABLE IF NOT EXISTS pick_dynasty_values (
    season      INTEGER NOT NULL,
    round       INTEGER NOT NULL,
    tier        TEXT    NOT NULL DEFAULT 'mid',
    value       REAL    NOT NULL,
    scraped_at  TEXT    NOT NULL,
    PRIMARY KEY (season, round, tier)
);

CREATE INDEX IF NOT EXISTS idx_matchups_league_week ON matchups(league_id, week);
CREATE INDEX IF NOT EXISTS idx_matchups_user ON matchups(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_league ON transactions(league_id);
CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(type);
CREATE INDEX IF NOT EXISTS idx_draft_picks_draft ON draft_picks(draft_id);
CREATE INDEX IF NOT EXISTS idx_draft_picks_user ON draft_picks(user_id);
"""


async def init_db(db_path: str) -> None:
    """Create all tables if they do not exist."""
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(DDL)
        await db.commit()


async def apply_migrations(db_path: str) -> None:
    """Add columns and indexes introduced after initial schema creation."""
    async with aiosqlite.connect(db_path) as db:
        try:
            await db.execute("ALTER TABLE draft_picks ADD COLUMN draft_slot INTEGER")
            await db.commit()
        except Exception:
            pass  # column already exists

        try:
            await db.execute("ALTER TABLE matchups ADD COLUMN starters_json TEXT")
            await db.commit()
        except Exception:
            pass  # column already exists

        try:
            await db.execute("ALTER TABLE matchups ADD COLUMN players_points_json TEXT")
            await db.commit()
        except Exception:
            pass  # column already exists

        try:
            await db.execute("ALTER TABLE season_records ADD COLUMN ppts REAL NOT NULL DEFAULT 0")
            await db.commit()
        except Exception:
            pass  # column already exists

        # Deduplicate transaction_draft_picks (no unique constraint on original table).
        # Keep the row with the lowest id for each logical pick key.
        await db.execute(
            """
            DELETE FROM transaction_draft_picks
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM transaction_draft_picks
                GROUP BY transaction_id, season, round, original_roster_id
            )
            """
        )
        await db.commit()

        try:
            await db.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_txn_pick_unique
                ON transaction_draft_picks(transaction_id, season, round, original_roster_id)
                """
            )
            await db.commit()
        except Exception:
            pass  # index already exists

        try:
            await db.execute("ALTER TABLE transactions ADD COLUMN waiver_bid_amount INTEGER")
            await db.commit()
        except Exception:
            pass  # column already exists

        # New tables for FantasyPros projections and current rosters
        await db.execute("""
            CREATE TABLE IF NOT EXISTS player_projections (
                season          INTEGER NOT NULL,
                week            INTEGER NOT NULL,
                player_id       TEXT    NOT NULL,
                position        TEXT    NOT NULL,
                projected_pts   REAL    NOT NULL,
                scraped_at      TEXT    NOT NULL,
                PRIMARY KEY (season, week, player_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS current_rosters (
                league_id   TEXT    NOT NULL,
                roster_id   INTEGER NOT NULL,
                player_id   TEXT    NOT NULL,
                status      TEXT    NOT NULL DEFAULT 'active',
                updated_at  TEXT    NOT NULL,
                PRIMARY KEY (league_id, roster_id, player_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS player_dynasty_values (
                player_id   TEXT    NOT NULL,
                value       REAL    NOT NULL,
                age         REAL,
                scraped_at  TEXT    NOT NULL,
                PRIMARY KEY (player_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pick_dynasty_values (
                season      INTEGER NOT NULL,
                round       INTEGER NOT NULL,
                tier        TEXT    NOT NULL DEFAULT 'mid',
                value       REAL    NOT NULL,
                scraped_at  TEXT    NOT NULL,
                PRIMARY KEY (season, round, tier)
            )
        """)
        await db.commit()

        try:
            await db.execute("ALTER TABLE owners ADD COLUMN joined_season INTEGER")
            await db.commit()
        except Exception:
            pass  # column already exists

        try:
            await db.execute("ALTER TABLE owners ADD COLUMN departed_after INTEGER")
            await db.commit()
        except Exception:
            pass  # column already exists
