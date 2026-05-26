"""Pydantic models for Sleeper API response shapes."""

from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field, field_validator


class LeagueSettings(BaseModel):
    playoff_week_start: int = 15
    last_scored_leg: int | None = None


class League(BaseModel):
    league_id: str
    name: str
    season: str
    status: str
    previous_league_id: str | None = None
    settings: LeagueSettings = Field(default_factory=LeagueSettings)
    total_rosters: int = 12

    @field_validator("previous_league_id", mode="before")
    @classmethod
    def normalize_prev_id(cls, v: Any) -> str | None:
        if v in (None, "0", 0, ""):
            return None
        return str(v)


class UserMetadata(BaseModel):
    team_name: str | None = None

    model_config = {"extra": "allow"}


class User(BaseModel):
    user_id: str
    display_name: str
    metadata: UserMetadata = Field(default_factory=UserMetadata)
    avatar: str | None = None


class Roster(BaseModel):
    roster_id: int
    owner_id: str | None = None
    league_id: str
    players: list[str] = Field(default_factory=list)
    starters: list[str] = Field(default_factory=list)
    settings: dict[str, Any] = Field(default_factory=dict)

    @property
    def wins(self) -> int:
        return self.settings.get("wins", 0)

    @property
    def losses(self) -> int:
        return self.settings.get("losses", 0)

    @property
    def ties(self) -> int:
        return self.settings.get("ties", 0)

    @property
    def fpts(self) -> float:
        whole = self.settings.get("fpts", 0) or 0
        decimal = self.settings.get("fpts_decimal", 0) or 0
        return whole + decimal / 100.0

    @property
    def fpts_against(self) -> float:
        whole = self.settings.get("fpts_against", 0) or 0
        decimal = self.settings.get("fpts_against_decimal", 0) or 0
        return whole + decimal / 100.0


class Matchup(BaseModel):
    matchup_id: int | None = None
    roster_id: int
    points: float | None = None
    players: list[str] = Field(default_factory=list)
    starters: list[str] = Field(default_factory=list)
    custom_points: float | None = None

    @field_validator("points", mode="before")
    @classmethod
    def coerce_points(cls, v: Any) -> float | None:
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None


class DraftPick(BaseModel):
    """A future draft pick asset referenced in a transaction."""
    season: int
    round: int
    roster_id: int
    owner_id: int
    previous_owner_id: int | None = None

    @field_validator("season", mode="before")
    @classmethod
    def coerce_season(cls, v: Any) -> int:
        return int(v)


class Transaction(BaseModel):
    transaction_id: str
    type: str  # trade, waiver, free_agent, commissioner
    status: str
    creator: str | None = None
    created: int | None = None  # epoch ms
    roster_ids: list[int] = Field(default_factory=list)
    adds: dict[str, int] | None = None   # player_id -> roster_id
    drops: dict[str, int] | None = None  # player_id -> roster_id
    draft_picks: list[DraftPick] = Field(default_factory=list)
    waiver_budget: list[dict[str, Any]] = Field(default_factory=list)
    leg: int | None = None  # week number

    @field_validator("draft_picks", mode="before")
    @classmethod
    def validate_picks(cls, v: Any) -> list[dict]:
        if not v:
            return []
        valid = []
        for pick in v:
            if not isinstance(pick, dict):
                continue
            if all(k in pick for k in ("season", "round", "roster_id", "owner_id")):
                valid.append(pick)
        return valid


class DraftSlot(BaseModel):
    """A single pick in a completed draft."""
    pick_id: str | None = None
    draft_id: str
    picked_by: str | None = None   # user_id
    roster_id: int | None = None
    player_id: str | None = None
    round: int
    pick_no: int
    draft_slot: int | None = None  # original slot owner (1-N); maps to original_roster_id in pick trades
    metadata: dict[str, Any] = Field(default_factory=dict)


class Draft(BaseModel):
    draft_id: str
    league_id: str
    season: str
    type: str
    status: str
    settings: dict[str, Any] = Field(default_factory=dict)


class NFLPlayer(BaseModel):
    player_id: str
    full_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    position: str | None = None
    team: str | None = None
    sport: str | None = None
    active: bool | None = None

    model_config = {"extra": "allow"}
