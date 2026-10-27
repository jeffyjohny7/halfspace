"""The Verifier: checks every line of on-screen text before it is published.

Checks (all deterministic):
* numbers  - every number must match a number in the cue's facts or the tool results
             the agents saw (allowing for rounding and 0.27 <-> 27% conversions);
* names    - only players named in the facts may appear; no other squad player;
* language - non-English text must be in the requested script, with only names,
             metric names and digits left in Latin letters;
* safety   - no betting language, emojis or hashtags;
* length   - headline and body fit the graphic.
Problems go back to the Fan Lens as feedback for a rewrite.
"""

from __future__ import annotations

import re
import unicodedata

from .config import LANGUAGES

LIMITS = {"en": (60, 160)}
DEFAULT_LIMITS = (64, 170)          # other languages: counted in visible characters (graphemes)
LATIN_LANGS = {"en", "es", "fr", "pt", "de"}
SCRIPTS = {"ml": (0x0D00, 0x0D7F), "hi": (0x0900, 0x097F), "ta": (0x0B80, 0x0BFF), "ar": (0x0600, 0x06FF)}
ALWAYS_OK = {0, 1, 2, 10, 11, 45, 90}
METRIC_WORDS = {"xg", "xt", "ppda", "var", "fc", "afc", "cb", "fb", "dm", "cm", "am", "st", "gk", "wb", "w", "vs",
                "rb", "lb", "rw", "lw", "lcb", "rcb", "lcm", "rcm", "ht", "ft"}
FORM = re.compile(r"^[WDL]{2,6}$")
SPACES = {"\u00a0": " ", "\u202f": " ", "\u2009": " ", "\u2007": " ", "\u200b": "", "\ufeff": "", "\u2060": ""}
SENTENCE_END = re.compile(r"(?<=[.!?।])\s+")
GLOSSARY = re.compile(r"(\bxG\b|\bPPDA\b|\bxT\b|field tilt)\s*(:|=|means|is how|shows how)", re.I)
BANNED = re.compile(r"\b(bet|bets|betting|odds|wager\w*|gambl\w*|bookmaker\w*|bookie\w*|accumulator|punter\w*)\b", re.I)
NUM = re.compile(r"(?<![\w.,])(\d+(?:[.,]\d+)?)(\s?%)?")
# A metric the writer names must be one the facts actually give (a graphic once said "xG and PPDA profiles
# unchanged" when the facts held neither). Each name is accepted if the facts use it or describe it.
METRIC_NAMES = {
    "xG": (re.compile(r"\bxG\b", re.I), re.compile(r"\bxG\b|expected goals", re.I)),
    "PPDA": (re.compile(r"\bPPDA\b", re.I), re.compile(r"\bPPDA\b|passes per defensive action", re.I)),
    "xT": (re.compile(r"\bxT\b"), re.compile(r"\bxT\b|expected threat", re.I)),
    "field tilt": (re.compile(r"field[\s-]tilt", re.I), re.compile(r"field[\s-]tilt|final[\s-]third", re.I)),
}
# "... at West Lea": a place the writer named after "at". It must be a real ground or town, or be in the facts
# (the recap once invented a stadium).
PLACE_AFTER_AT = re.compile(r"\bat ((?:[A-Z][\w'’-]+)(?: [A-Z][\w'’-]+){0,3})")
LATIN_WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ'’-]+")


try:                                     # grapheme clusters: what a viewer sees as one character
    import regex as _regex

    def visible_len(text: str) -> int:
        return len(_regex.findall(r"\X", text))
except ImportError:                      # pragma: no cover
    def visible_len(text: str) -> int:
        return sum(1 for ch in text if unicodedata.category(ch)[0] != "M")


def tidy_text(text: str) -> str:
    """Normalise odd spaces a model sometimes emits (no-break, zero-width), keep Indic joiners."""
    for a, b in SPACES.items():
        text = text.replace(a, b)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def text_len(text: str, language: str) -> int:
    return len(text) if language == "en" else visible_len(text)


def trim_to_fit(text: str, limit: int, language: str) -> str | None:
    """Drop trailing sentences until the text fits. None if even the first sentence is too long.
    Dropping whole sentences can only remove information, never make a statement wrong."""
    if text_len(text, language) <= limit:
        return text
    parts = SENTENCE_END.split(text.strip())
    out = ""
    for part in parts:
        cand = (out + " " + part).strip()
        if text_len(cand, language) > limit:
            break
        out = cand
    return out or None


def _norm_digits(text: str) -> str:
    """Native digits (൧, १, ٣ ...) -> ASCII, so they are checked like any other number."""
    return "".join(str(unicodedata.digit(ch)) if ch.isdigit() and not ch.isascii() else ch for ch in text)


def numbers(text: str) -> list[tuple[float, int, bool]]:
    """(value, decimals, is_percent) for each number in text."""
    out = []
    for m in NUM.finditer(_norm_digits(text)):
        raw = m.group(1).replace(",", ".")
        dec = len(raw.split(".")[1]) if "." in raw else 0
        out.append((float(raw), dec, bool(m.group(2))))
    return out


def pool_from(texts: list[str]) -> set[float]:
    """Every number in the evidence, plus its percent/fraction twin (0.27 <-> 27%)."""
    pool: set[float] = set()
    for t in texts:
        for v, _d, pct in numbers(t):
            pool.add(v)
            if pct:
                pool.add(v / 100)
            elif v <= 1:
                pool.add(v * 100)
    return pool


def _matches(value: float, dec: int, pool: set[float]) -> bool:
    """True if `value`, written with `dec` decimals, is a fair rounding of an evidence number."""
    if value in ALWAYS_OK:
        return True
    tol = 0.5 * 10 ** (-dec) + 1e-9
    return any(abs(v - value) <= tol for v in pool)


def _other_scripts(text: str, lang: str) -> set[str]:
    """Letters that belong to neither Latin nor the language's own script (a model slipping into
    Georgian, Hebrew or Korean mid-sentence, say)."""
    lo, hi = SCRIPTS.get(lang, (0, 0))
    bad = set()
    for ch in text:
        if not ch.isalpha():
            continue
        o = ord(ch)
        if o < 0x250 or lo <= o <= hi:          # Latin (incl. accents) or the target script
            continue
        if lang == "ar" and 0x0750 <= o <= 0x077F:
            continue
        bad.add(ch)
    return bad


def _script_chars(text: str, lang: str) -> int:
    lo, hi = SCRIPTS[lang]
    return sum(lo <= ord(ch) <= hi for ch in text)


class Verifier:
    def __init__(self, roster: dict[str, str], clubs: list[str], places: list[str] | None = None):
        """roster: player name -> club name for every player in the league. places: real grounds and towns."""
        self.roster = roster
        self.clubs = clubs
        self.places = [p for p in (places or []) if p]
        self.by_surname: dict[str, list[str]] = {}
        for name in roster:
            parts = name.split()
            if len(parts) > 1:
                self.by_surname.setdefault(parts[-1].lower(), []).append(name)

    def check(self, profile: str, language: str, headline: str, body: str, facts: list[str], angle: str,
              allowed_names: list[str], evidence: list[str], english_body: str | None = None,
              check_length: bool = True, metrics_from_facts_only: bool = False) -> list[str]:
        problems: list[str] = []
        text = f"{headline}\n{body}"
        h_max, b_max = LIMITS.get(language, DEFAULT_LIMITS)
        if not body.strip() or (check_length and not headline.strip()):
            problems.append("headline and body must both be filled in")
        if check_length and text_len(headline, language) > h_max:
            problems.append(f"headline is {text_len(headline, language)} characters; maximum {h_max}: shorten it")
        if check_length and text_len(body, language) > b_max:
            problems.append(f"body is {text_len(body, language)} characters; maximum {b_max}: one short sentence")

        # Numbers: only from facts and the tool results the agents saw.
        pool = pool_from(facts + evidence)
        bad = sorted({f"{v:g}{'%' if pct else ''}" for v, d, pct in numbers(text) if not _matches(v, d, pool)})
        if bad:
            problems.append("these numbers are not in the facts: " + ", ".join(bad) + ". Use only numbers from the facts.")

        # Names: no squad player who is not part of this cue.
        allowed = " ".join(allowed_names).lower()
        words = {w.lower().strip("'’") for w in LATIN_WORD.findall(text)}
        stray = set()
        for w in words:
            for full in self.by_surname.get(w, []):
                if full.lower() not in allowed and w not in allowed:
                    stray.add(full)
        if stray:
            problems.append("these players are not part of this cue: " + ", ".join(sorted(stray)))

        if self.places:
            given = " ".join(facts) + " " + (angle or "")
            known = self.places + self.clubs + list(self.roster)
            invented = []
            for m in PLACE_AFTER_AT.finditer(body):
                place = re.sub(r"['’]s$", "", m.group(1))
                if place not in given and not any(place in k or k in place for k in known):
                    invented.append(place)
            if invented:
                problems.append("these places are not in the facts: " + ", ".join(invented) + ". Leave the venue out.")

        if metrics_from_facts_only:
            given = " ".join(facts) + " " + (angle or "")
            unsupported = [m for m, (said, ok) in METRIC_NAMES.items() if said.search(text) and not ok.search(given)]
            if unsupported:
                problems.append("these metrics are not in the facts, so leave them out: " + ", ".join(unsupported))

        if BANNED.search(text):
            problems.append("remove betting language")
        if GLOSSARY.search(text):
            problems.append("do not define or explain metrics; just say what happened in plain words")
        if "#" in text or any(unicodedata.category(ch) == "So" for ch in text):
            problems.append("remove emojis, symbols and hashtags")

        # Language: names, club names and metric names stay in Latin letters; everything else
        # must be in the requested script.
        others = _other_scripts(text, language)
        if others:
            problems.append("remove characters from other writing systems: " + " ".join(sorted(others)[:6]))
        if language in SCRIPTS:
            vocab = set(re.sub(r"[()]", " ", allowed + " " + " ".join(self.clubs).lower()).split()) | METRIC_WORDS
            foreign = [w for w in LATIN_WORD.findall(text) if len(w) > 2 and w.lower().strip("'’-") not in vocab
                       and not FORM.match(w)]
            if _script_chars(text, language) < 4:
                problems.append(f"write in {LANGUAGES[language]} script; only names and metric names stay in Latin letters")
            elif len(foreign) > 2:
                problems.append(f"these English words should be in {LANGUAGES[language]}: " + ", ".join(foreign[:5]))
        elif language != "en" and english_body and body.strip() == english_body.strip():
            problems.append(f"translate into {LANGUAGES.get(language, language)}")
        return problems
