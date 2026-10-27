"""Structured outputs the LLM agents must return (validated with pydantic)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Storyline(BaseModel):
    title: str = Field(description="3-6 words")
    text: str = Field(description="1-2 broadcast-ready sentences. Numbers as digits, copied exactly from tool results.")
    evidence_ids: list[str] = Field(description="edge_id, finding_id or prediction_id values from tool results")
    confidence: Literal["high", "medium"]


class PreMatchBrief(BaseModel):
    headline: str = Field(description="One line, max 80 characters")
    storylines: list[Storyline] = Field(description="3 to 5 storylines, most important first")
    players_to_watch: list[str] = Field(description="Player names only, exactly as in tool results (no positions)")
    tactical_preview: str = Field(description="2-3 sentences on how the styles meet")


class Pick(BaseModel):
    candidate_id: str
    importance: float = Field(description="0 to 1")
    angle: str = Field(description="One sentence: why it matters now. Numbers only from the facts or tool results.")


class AnalystReading(BaseModel):
    picks: list[Pick]
    game_read: str = Field(description="One sentence on how the match is going")


class Variant(BaseModel):
    profile: str
    language: str
    headline: str = Field(description="Max 60 characters")
    body: str = Field(description="Max 160 characters")


class Rendered(BaseModel):
    variants: list[Variant]


class Recap(BaseModel):
    headline: str = Field(description="Max 80 characters")
    summary: str = Field(description="3-4 sentences")
    plan_vs_reality: str = Field(description="2-3 sentences: which pre-match predictions came true and which did not")
    player_of_the_match: str = Field(description="Exact player name from the facts")
    player_reason: str = Field(description="One sentence with numbers from the facts")


class Answer(BaseModel):
    answer: str = Field(description="2-4 short sentences (a line-up may be a short list). Numbers copied exactly from tool results.")
    answered: bool = Field(description="false if the league data does not cover the question")


class MemoryUpdate(BaseModel):
    """What the fan said about their own football preferences in one message. Empty when nothing qualifies."""
    club: str | None = Field(None, description="the club the fan says they support, exactly as they wrote it; null if they did not say")
    players: list[str] = Field(default_factory=list, description="players the fan says they love, follow or rate highly; not players they only ask about")
    style: Literal["casual", "analyst"] | None = Field(None, description="casual if they ask for simple words, analyst if they ask for detailed stats; null otherwise")
    interests: list[Literal["tactics", "set_pieces", "stats", "goalkeepers", "young_players", "team_news"]] = Field(
        default_factory=list, description="topics the fan says they enjoy")
    stopped_supporting: bool = Field(False, description="true if the fan says they no longer support their club")
    unfollow: list[str] = Field(default_factory=list, description="players the fan says they no longer follow")


class AlertText(BaseModel):
    title: str = Field(description="at most 50 characters, starts with the fan's first name")
    body: str = Field(description="one or two short sentences, at most 150 characters")
