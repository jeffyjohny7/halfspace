"""Broadcast configuration: viewers, languages, model settings."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

LANGUAGES = {
    "en": "English", "ml": "Malayalam", "hi": "Hindi", "ta": "Tamil", "es": "Spanish", "fr": "French",
    "pt": "Portuguese", "ar": "Arabic", "de": "German",
}

PROFILE_STYLES = {
    "analyst": "Data-literate viewer. Use a metric's name with its number only when the facts give that metric; "
               "never mention a metric the facts don't give, and never say one is unchanged or steady. "
               "Never list metrics, define them, or tell viewers what to monitor. Precise and compact.",
    "casual": "Casual fan. Tell it like a commentator: plain words, no metric names, never define or explain a term. "
              "Say what a number means in everyday words, e.g. 'a big chance (0.39 xG)', "
              "'their corners create chances worth 0.45 goals a game', 'Lowmarsh have 80% of the play in Oxmere's half'. "
              "xG is chance quality, not goals scored: never write it as plain 'goals per match'; keep 'chances worth'. "
              "Keep each number's meaning exactly as in the facts. Short and lively.",
    "club": "Supporter of {club}. Frame it from their side, still factual and fair to the opponent; "
            "bad news for {club} is still told.",
    "player_focus": "Viewer following {player} all match. Put him at the centre.",
}

# How to write each language. Names, club names and digits always stay as they are.
LANGUAGE_NOTES = {
    "en": "",
    "ml": "Write natural Malayalam as a Malayalam TV commentator would, in Malayalam script only. "
          "Football words in Malayalam script too (ഗോൾ, കോർണർ, പെനാൽറ്റി, ഫ്രീ കിക്ക്). No other scripts.",
    "hi": "Write natural Hindi as a Hindi TV commentator would, in Devanagari only. Football words in Devanagari "
          "too (गोल, कॉर्नर, पेनल्टी, फ्री किक). No other scripts.",
    "ta": "Write natural Tamil in Tamil script only, as a Tamil TV commentator would. No other scripts.",
    "es": "Write natural Spanish as a Spanish-language TV commentator would, in a neutral Spanish understood "
          "in Spain and Latin America. Football words in Spanish (gol, córner, penalti, tiro libre).",
    "ar": "Write natural Modern Standard Arabic as an Arabic TV commentator would, in Arabic script only. "
          "Football words in Arabic too (هدف، ركلة ركنية، ركلة جزاء، ركلة حرة). Keep digits as 0-9. No other scripts.",
}
LENGTH_WORDS = {"headline": 8, "body": 26}
@dataclass(frozen=True)
class Viewer:
    profile: str          # analyst | casual | club:<club_id> | player_focus
    language: str = "en"
    audience: str = "all"  # all | player_focus

    @property
    def key(self) -> str:
        return f"{self.profile}/{self.language}"


@dataclass
class BroadcastConfig:
    data_dir: str = "data"
    mode: str = "foundry"                # foundry | offline
    languages: tuple[str, ...] = ()      # extra languages for casual viewers, e.g. ("ml", "hi")
    favourite_club: str | None = None    # club id or name: adds a supporter's view
    focus_player: str | None = None      # player id or name: adds a player-focus stream
    tick_every_s: float = 180.0          # regular check-ins (seconds of play)
    min_gap_s: float = 120.0             # minimum gap between regular cues on screen
    max_writer_attempts: int = 3         # Fan Lens attempts before the safe template is used
    llm_timeout_s: float = 90.0
    llm_retries: int = 1
    reasoning_effort: str | None = field(default_factory=lambda: os.environ.get("AGENT_REASONING_EFFORT", "low") or None)
    max_tool_calls: int = 8              # per agent call (Scout investigations, Analyst look-ups)
    # Other languages: more reasoning by default, and optionally a different deployment.
    translation_effort: str | None = field(
        default_factory=lambda: os.environ.get("AGENT_TRANSLATION_REASONING_EFFORT", "medium") or None)
    writer_model: str | None = field(default_factory=lambda: os.environ.get("FOUNDRY_WRITER_MODEL") or None)
    out_dir: str | None = None           # default: <data_dir>/runtime/broadcast
    trace: bool = field(default_factory=lambda: os.environ.get("HALFSPACE_TRACE", "") == "1")  # Foundry tracing
    # Also record prompts, replies and tool results in the traces. Fine for this synthetic league; keep it off
    # anywhere real people's questions or data pass through.
    trace_content: bool = field(default_factory=lambda: os.environ.get("HALFSPACE_TRACE_CONTENT", "") == "1")
    verbose: bool = True

    def viewers(self, club_names: dict[str, str] | None = None) -> list[Viewer]:
        v = [Viewer("analyst"), Viewer("casual")]
        v += [Viewer("casual", lang) for lang in self.languages if lang != "en"]
        if self.favourite_club:
            v.append(Viewer(f"club:{self.favourite_club}"))
        if self.focus_player:
            v.append(Viewer("player_focus", "en", "player_focus"))
            v += [Viewer("player_focus", lang, "player_focus") for lang in self.languages if lang != "en"]
        return v
