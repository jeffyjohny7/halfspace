"""Fan memory and personal alerts."""

from __future__ import annotations

import asyncio
import contextvars
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

from .config import LANGUAGES
from .llm import ask, model_options, prompt_json
from .schemas import AlertText, MemoryUpdate
from .verifier import Verifier, tidy_text

FAN_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
INTERESTS = {"tactics": "Tactics", "set_pieces": "Set pieces", "stats": "Stats and xG", "goalkeepers": "Goalkeepers",
             "young_players": "Young players", "team_news": "Injuries and team news"}
STYLES = {"casual": "Simple words", "analyst": "Detailed stats"}
MAX_PLAYERS = 5
MAX_ALERTS = 8                 # per fan per match, goals and the result always included
FROM_SETTINGS = "Set in My Halfspace"

# The brief about the current fan, for the FanContext provider (set per question by the Fan Desk).
FAN_BRIEF: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar("fan_brief", default=None)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def clean_name(name: Any) -> str:
    """A first name: letters (any script), apostrophes and hyphens, at most 24 characters."""
    words = str(name or "").strip().split()
    first = words[0] if words else ""
    first = "".join(ch for ch in first if ch.isalpha() or ch in "'-’")[:24]
    return first[:1].upper() + first[1:] if first else ""


# The store

class FanStore:
    def __init__(self, folder: str | Path, analyst=None):
        self.dir = Path(folder)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.analyst = analyst

    def _path(self, fan_id: str) -> Path:
        if not FAN_ID.match(fan_id or ""):
            raise ValueError("bad fan id")
        return self.dir / f"{fan_id}.json"

    def load(self, fan_id: str) -> dict | None:
        try:
            p = self._path(fan_id)
        except ValueError:
            return None
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def save(self, prof: dict) -> dict:
        prof["updated"] = _now()
        self._path(prof["fan_id"]).write_text(json.dumps(prof, ensure_ascii=False, indent=1), encoding="utf-8")
        return prof

    def delete(self, fan_id: str) -> None:
        for p in (self._path(fan_id), self.dir / f"{fan_id}.alerts.json"):
            if p.exists():
                p.unlink()

    def get_or_new(self, fan_id: str) -> dict:
        prof = self.load(fan_id)
        if prof is None:
            self._path(fan_id)          # validates the id
            prof = {"fan_id": fan_id, "name": "", "memory": False, "alerts": True, "language": "en",
                    "facts": [], "created": _now(), "updated": _now()}
        return prof

    # -- edits from the My Halfspace page
    def update(self, fan_id: str, patch: dict) -> dict:
        prof = self.get_or_new(fan_id)
        if "name" in patch:
            prof["name"] = clean_name(patch["name"])
        for key in ("memory", "alerts"):
            if key in patch:
                prof[key] = bool(patch[key])
        if patch.get("language") in LANGUAGES:
            prof["language"] = patch["language"]
        if "style" in patch:
            self._set_style(prof, patch["style"], FROM_SETTINGS)
        if "club" in patch:
            self._set_club(prof, patch["club"], FROM_SETTINGS)
        if "players" in patch and isinstance(patch["players"], list):
            keep = [f for f in prof["facts"] if f["kind"] != "player"]
            prof["facts"] = keep
            for pid in patch["players"][:MAX_PLAYERS]:
                self._add_player(prof, pid, FROM_SETTINGS)
        if "interests" in patch and isinstance(patch["interests"], list):
            prof["facts"] = [f for f in prof["facts"] if f["kind"] != "interest"]
            for k in patch["interests"]:
                self._add_interest(prof, k, FROM_SETTINGS)
        return self.save(prof)

    def forget(self, fan_id: str, fact_id: str | None = None, everything: bool = False) -> dict | None:
        if everything:
            self.delete(fan_id)
            return None
        prof = self.get_or_new(fan_id)
        prof["facts"] = [f for f in prof["facts"] if f["id"] != fact_id]
        return self.save(prof)

    # -- learning from what the fan said (Memory Keeper output, validated here)
    def learn(self, fan_id: str, upd: MemoryUpdate, said: str) -> list[str]:
        """Apply what the Memory Keeper found; returns the lines added, in plain words."""
        prof = self.load(fan_id)
        if prof is None or not prof.get("memory"):
            return []
        said = " ".join(str(said).split())[:160]
        added: list[str] = []
        if upd.stopped_supporting:
            prof["facts"] = [f for f in prof["facts"] if f["kind"] != "club"]
        for name in upd.unfollow:
            pid = self._player_id(name)
            prof["facts"] = [f for f in prof["facts"] if not (f["kind"] == "player" and f["value"] == pid)]
        if upd.club:
            line = self._set_club(prof, upd.club, said)
            if line:
                added.append(line)
        for name in upd.players[:MAX_PLAYERS]:
            line = self._add_player(prof, name, said)
            if line:
                added.append(line)
        if upd.style:
            line = self._set_style(prof, upd.style, said)
            if line:
                added.append(line)
        for k in upd.interests:
            line = self._add_interest(prof, k, said)
            if line:
                added.append(line)
        self.save(prof)
        return added

    # -- helpers: every value is checked against the league before it is kept
    def _club_id(self, club: Any) -> str | None:
        if not club or self.analyst is None:
            return None
        try:
            return self.analyst.club_id(str(club))
        except Exception:
            return None

    def _player_id(self, player: Any) -> str | None:
        if not player or self.analyst is None:
            return None
        try:
            return self.analyst.player_id(str(player))
        except Exception:
            return None

    def _fact(self, prof: dict, kind: str, value: str, label: str, said: str) -> str:
        prof["facts"].append({"id": uuid.uuid4().hex[:10], "kind": kind, "value": value, "label": label,
                              "said": said, "at": _now()})
        return label

    def _set_club(self, prof: dict, club: Any, said: str) -> str | None:
        cid = self._club_id(club) if club else None
        current = next((f for f in prof["facts"] if f["kind"] == "club"), None)
        if club in (None, "") and said == FROM_SETTINGS:
            prof["facts"] = [f for f in prof["facts"] if f["kind"] != "club"]
            return None
        if cid is None or (current and current["value"] == cid):
            return None
        prof["facts"] = [f for f in prof["facts"] if f["kind"] != "club"]
        return self._fact(prof, "club", cid, f"Supports {self.analyst.store.club_name(cid)}", said)

    def _add_player(self, prof: dict, player: Any, said: str) -> str | None:
        pid = self._player_id(player)
        players = [f for f in prof["facts"] if f["kind"] == "player"]
        if pid is None or any(f["value"] == pid for f in players) or len(players) >= MAX_PLAYERS:
            return None
        return self._fact(prof, "player", pid, f"Follows {self.analyst.store.player_name(pid)}", said)

    def _set_style(self, prof: dict, style: Any, said: str) -> str | None:
        if style not in STYLES:
            if style in (None, "") and said == FROM_SETTINGS:
                prof["facts"] = [f for f in prof["facts"] if f["kind"] != "style"]
            return None
        if any(f["kind"] == "style" and f["value"] == style for f in prof["facts"]):
            return None
        prof["facts"] = [f for f in prof["facts"] if f["kind"] != "style"]
        return self._fact(prof, "style", style, f"Likes {STYLES[style].lower()}", said)

    def _add_interest(self, prof: dict, key: Any, said: str) -> str | None:
        if key not in INTERESTS or any(f["kind"] == "interest" and f["value"] == key for f in prof["facts"]):
            return None
        return self._fact(prof, "interest", key, f"Enjoys {INTERESTS[key].lower()}", said)


def player_club(store, pid: str) -> str | None:
    """The player's club this season."""
    sq = store.squads
    row = sq[(sq.season == store.current_season) & (sq.player_id == pid)]
    return str(row.club_id.iloc[0]) if len(row) else None


def club_of(prof: dict | None) -> str | None:
    return next((f["value"] for f in (prof or {}).get("facts", []) if f["kind"] == "club"), None)


def players_of(prof: dict | None) -> list[str]:
    return [f["value"] for f in (prof or {}).get("facts", []) if f["kind"] == "player"]


def style_of(prof: dict | None) -> str | None:
    return next((f["value"] for f in (prof or {}).get("facts", []) if f["kind"] == "style"), None)


def public_profile(prof: dict | None, analyst) -> dict | None:
    """The profile as the app shows it: every remembered line, with where it came from."""
    if prof is None:
        return None
    store = analyst.store if analyst is not None else None
    cid = club_of(prof)
    return {**{k: prof.get(k) for k in ("fan_id", "name", "memory", "alerts", "language", "created", "updated")},
            "club": cid, "club_name": store.club_name(cid) if (cid and store) else None,
            "players": [{"id": p, "name": store.player_name(p) if store else p} for p in players_of(prof)],
            "style": style_of(prof),
            "interests": [f["value"] for f in prof.get("facts", []) if f["kind"] == "interest"],
            "facts": prof.get("facts", [])}


# The fan, in the Fan Desk's context

def _club_now(analyst, cid: str, clock_s: float | None) -> str | None:
    """How the fan's club stands right now: today's match at the fan's minute, else their last result."""
    store = analyst.store
    meta = store.showcase_meta
    name = store.club_name(cid)
    if cid in (meta["home_id"], meta["away_id"]) and clock_s and clock_s > 0:
        st = analyst.live_state(min(float(clock_s), analyst.live.end_clock))
        h, a = st["score"]["home"], st["score"]["away"]
        mine, theirs = (h, a) if cid == meta["home_id"] else (a, h)
        opp = meta["away"] if cid == meta["home_id"] else meta["home"]
        when = "at full time" if st["clock"].get("finished") else f"at the minute the fan has reached ({st['clock']['minute']}')"
        state = "winning" if mine > theirs else "losing" if mine < theirs else "level"
        if st["clock"].get("finished"):
            state = "won" if mine > theirs else "lost" if mine < theirs else "drew"
        return f"Today's match {when}: {name} {state}, {mine}-{theirs} against {opp}."
    m = store.matches
    played = m[(m.season == store.current_season) & (m.stage == "league") & m.home_goals.notna()
               & ((m.home_id == cid) | (m.away_id == cid))].sort_values("date")
    if played.empty:
        return None
    r = played.iloc[-1]
    home = r.home_id == cid
    mine, theirs = (int(r.home_goals), int(r.away_goals)) if home else (int(r.away_goals), int(r.home_goals))
    opp = store.club_name(r.away_id if home else r.home_id)
    res = "won" if mine > theirs else "lost" if mine < theirs else "drew"
    return f"{name}'s last league match: {res} {mine}-{theirs} {'at home to' if home else 'away at'} {opp} (matchday {int(r['round'])})."


def fan_brief(prof: dict | None, analyst, clock_s: float | None) -> list[str]:
    """What the Fan Desk is told about this fan."""
    if not prof:
        return []
    store = analyst.store
    lines = []
    if prof.get("name"):
        lines.append(f"The fan's first name is {prof['name']}.")
    cid = club_of(prof)
    if cid:
        lines.append(f"They support {store.club_name(cid)}.")
        now = _club_now(analyst, cid, clock_s)
        if now:
            lines.append(now)
    pl = players_of(prof)
    if pl:
        lines.append("Players they follow: " + ", ".join(store.player_name(p) for p in pl) + ".")
    if style_of(prof) == "analyst":
        lines.append("They like detailed numbers: you may add one extra stat.")
    elif style_of(prof) == "casual":
        lines.append("They like simple words: no jargon.")
    ints = [INTERESTS[f["value"]] for f in prof.get("facts", []) if f["kind"] == "interest"]
    if ints:
        lines.append("Topics they enjoy: " + ", ".join(i.lower() for i in ints) + ".")
    if cid:
        lines.append("Tone: if their club is losing or lost, open with one short, kind line, no drama and no pity. "
                     "If they are winning or won, you may share the moment in a few words. Never pressure them to "
                     "keep watching and never flatter.")
    return lines


def fan_context_provider():
    """The Agent Framework ContextProvider that adds the current fan to every Fan Desk run."""
    from agent_framework import ContextProvider

    class FanContext(ContextProvider):
        def __init__(self) -> None:
            super().__init__("halfspace_fan")

        async def before_run(self, *, agent, session, context, state) -> None:
            lines = FAN_BRIEF.get()
            if lines:
                context.extend_instructions(self.source_id, "About the fan you are answering:\n" + "\n".join(lines))

    return FanContext()


class MemoryKeeper:
    """LLM agent: what the fan said about their own football preferences. The FanStore validates it."""

    def __init__(self, client, reasoning_effort: str | None = None, timeout_s: float = 45.0):
        from agent_framework import Agent

        from . import prompts
        self.agent = Agent(client, prompts.MEMORY_KEEPER, name="MemoryKeeper",
                           default_options=model_options(reasoning_effort))
        self.timeout_s = timeout_s

    async def read(self, message: str) -> MemoryUpdate | None:
        res = await ask(self.agent, f"The fan's message: {message}", MemoryUpdate, timeout_s=self.timeout_s, retries=0)
        return res.value


# Alerts

def _side(analyst, cid: str | None) -> str | None:
    meta = analyst.store.showcase_meta
    return "home" if cid == meta["home_id"] else "away" if cid == meta["away_id"] else None


def find_alerts(prof: dict | None, analyst) -> list[dict]:
    """Every moment of today's match worth an alert for this fan (the whole match; released by clock later)."""
    if not prof or not prof.get("alerts"):
        return []
    store = analyst.store
    live = analyst.live
    meta = store.showcase_meta
    cid = club_of(prof)
    mine = cid if _side(analyst, cid) else None
    fav = {store.player_name(p): p for p in players_of(prof)}
    out: list[dict] = []

    def add(m_id, clock_s, minute, kind, tone, facts, priority):
        out.append({"id": m_id, "clock_s": float(clock_s), "minute": int(minute), "kind": kind, "tone": tone,
                    "facts": facts, "priority": priority})

    # Before kick-off: favourite players out or doubtful, and the fan's club playing today.
    for pid in players_of(prof):
        pcid = player_club(store, pid)
        try:
            news = analyst.team_news(pcid) if pcid else None
        except Exception:
            news = None
        for status in ("unavailable", "doubtful"):
            for x in (news or {}).get(status, []):
                if x.get("player_id") == pid:
                    add(f"news:{pid}", 0.0, 0, "team_news", "bad",
                        {"player": x["player"], "club": news["club"], "status": x["status"], "reason": x["reason"],
                         "opponent": news["fixture"]["opponent"]}, 3)
    if mine:
        opp = meta["away"] if mine == meta["home_id"] else meta["home"]
        add(f"kickoff:{mine}", 0.0, 0, "kick_off", "neutral",
            {"club": store.club_name(mine), "opponent": opp, "kick_off": meta.get("kick_off", "12:30"),
             "fixture": f"{meta['home']} v {meta['away']}"}, 2)

    moments = live.key_moments(live.end_clock, 0.0, 0.0)
    for m in moments:
        t, f, team_id = m["type"], m["facts"], m.get("team_id")
        good = mine is not None and team_id == mine
        if t == "goal":
            scorer, assist = f.get("scorer"), f.get("assist")
            if mine or scorer in fav or assist in fav:
                tone = ("good" if good else "bad") if mine else "good"
                add(m["moment_id"], m["clock_s"], m["minute"], "goal", tone,
                    {"scorer": scorer, "assist": assist, "team": m["team"], "score": f["score_after"],
                     "home": meta["home"], "away": meta["away"], "own_goal": f.get("own_goal")}, 5)
        elif t in ("red_card", "yellow_card"):
            if f.get("player") in fav or (t == "red_card" and mine):
                tone = "bad" if (good or f.get("player") in fav) else "good"
                add(m["moment_id"], m["clock_s"], m["minute"], t, tone, {"player": f["player"], "team": m["team"]},
                    4 if t == "red_card" else 1)
        elif t == "injury":
            if f.get("player") in fav or (good and f.get("outcome") == "replaced"):
                add(m["moment_id"], m["clock_s"], m["minute"], "injury", "bad",
                    {"player": f["player"], "team": m["team"], "outcome": f["outcome"],
                     "replaced_by": f.get("replaced_by")}, 3)
        elif t == "substitution":
            if f.get("on") in fav or f.get("off") in fav:
                add(m["moment_id"], m["clock_s"], m["minute"], "substitution", "neutral",
                    {"on": f["on"], "off": f["off"], "team": m["team"]}, 1)
    if mine:
        for p, label in ((live.ev[live.ev.period == 1].clock_s.max(), "half_time"), (live.end_clock, "full_time")):
            st = analyst.live_state(float(p))
            h, a = st["score"]["home"], st["score"]["away"]
            my, their = (h, a) if mine == meta["home_id"] else (a, h)
            tone = "good" if my > their else "bad" if my < their else "neutral"
            add(f"{label}:{mine}", float(p), st["clock"]["minute"], label, tone,
                {"club": store.club_name(mine), "score": f"{h}-{a}", "home": meta["home"], "away": meta["away"]},
                5 if label == "full_time" else 2)
    # Cap: keep the most important, then put them back in match order.
    out.sort(key=lambda x: (-x["priority"], x["clock_s"]))
    out = sorted(out[:MAX_ALERTS], key=lambda x: (x["clock_s"], x["id"]))
    return out


def alert_facts(a: dict) -> list[str]:
    """The alert's facts as sentences (for the Notifier and the Verifier)."""
    f = a["facts"]
    k = a["kind"]
    when = f"Minute {a['minute']}." if a["minute"] else ""
    if k == "goal":
        s = f"{when} {'Own goal' if f.get('own_goal') else 'Goal'} for {f['team']}: {f['scorer']}"
        s += f", assisted by {f['assist']}." if f.get("assist") else "."
        return [s, f"Score: {f['home']} {f['score']} {f['away']}."]
    if k in ("red_card", "yellow_card"):
        return [f"{when} {'Red' if k == 'red_card' else 'Yellow'} card for {f['player']} ({f['team']})."]
    if k == "injury":
        s = f"{when} {f['player']} ({f['team']}) is injured"
        s += f" and replaced by {f['replaced_by']}." if f.get("replaced_by") else (", and carries on." if f["outcome"] == "carries on" else ".")
        return [s]
    if k == "substitution":
        return [f"{when} Substitution for {f['team']}: {f['on']} comes on for {f['off']}."]
    if k in ("half_time", "full_time"):
        return [f"{'Half-time' if k == 'half_time' else 'Full time'}: {f['home']} {f['score']} {f['away']}."]
    if k == "team_news":
        return [f"Team news before {f['club']} v {f['opponent']}: {f['player']} is {f['status']} ({f['reason']})."]
    if k == "kick_off":
        return [f"{f['club']} play {f['opponent']} today at {f['kick_off']}."]
    return []


def template_alert(a: dict, name: str) -> dict:
    """The safe alert, in English, built from the facts alone."""
    f, k = a["facts"], a["kind"]
    who = f"{name}, " if name else ""
    if k == "goal":
        title = f"{who}goal for {f['team']}"
        body = f"{f['scorer']} scores ({a['minute']}'). {f['home']} {f['score']} {f['away']}."
    elif k == "red_card":
        title, body = f"{who}red card", f"{f['player']} ({f['team']}) is sent off ({a['minute']}')."
    elif k == "yellow_card":
        title, body = f"{who}yellow card", f"{f['player']} is booked ({a['minute']}')."
    elif k == "injury":
        title = f"{who}{f['player']} is hurt"
        body = (f"{f['player']} goes off injured ({a['minute']}'), {f['replaced_by']} comes on." if f.get("replaced_by")
                else f"{f['player']} took a knock ({a['minute']}') and carries on.")
    elif k == "substitution":
        title, body = f"{who}substitution", f"{f['on']} comes on for {f['off']} ({a['minute']}')."
    elif k in ("half_time", "full_time"):
        title = f"{who}{'half-time' if k == 'half_time' else 'full time'}"
        body = f"{f['home']} {f['score']} {f['away']}."
    elif k == "team_news":
        title, body = f"{who}team news", f"{f['player']} is {f['status']} for {f['club']} v {f['opponent']} ({f['reason']})."
    else:
        title, body = f"{who}{f['club']} play today", f"{f.get('fixture') or f['club'] + ' v ' + f['opponent']} kicks off at {f['kick_off']}."
    return {"title": title[:1].upper() + title[1:], "body": body, "lang": "en", "source": "template"}


class Notifier:
    """LLM agent that writes each alert for the fan, checked by the Verifier; a template if it fails."""

    def __init__(self, client, verifier: Verifier, reasoning_effort: str | None = None, timeout_s: float = 45.0):
        self.verifier = verifier
        self.timeout_s = timeout_s
        self.agent = None
        if client is not None:
            from agent_framework import Agent

            from . import prompts
            self.agent = Agent(client, prompts.NOTIFIER, name="Notifier", default_options=model_options(reasoning_effort))

    async def write(self, a: dict, prof: dict) -> dict:
        name, lang = prof.get("name") or "", prof.get("language") or "en"
        if self.agent is None:
            return template_alert(a, name)
        facts = alert_facts(a)
        names = [v for v in a["facts"].values() if isinstance(v, str)]
        prompt = prompt_json({"fan_first_name": name or "(no name given: start the title with the news)",
                              "language": LANGUAGES.get(lang, "English"), "news_for_the_fan": a["tone"],
                              "kind": a["kind"], "facts": facts})
        for _ in range(2):
            res = await ask(self.agent, prompt, AlertText, timeout_s=self.timeout_s, retries=0)
            if res.value is None:
                break
            title, body = tidy_text(res.value.title), tidy_text(res.value.body)
            problems = self.verifier.check("casual", lang, title, body, facts, "", names, [], check_length=False)
            if len(title) > 70 or len(body) > 200:
                problems.append("too long: title at most 50 characters, body at most 150")
            if not problems:
                return {"title": title, "body": body, "lang": lang, "source": "llm"}
            prompt += "\nRejected by the fact checker: " + "; ".join(problems) + ". Rewrite it."
        return template_alert(a, name)


class AlertService:
    """Writes a fan's alerts ahead of time (in the background) and releases them as the fan's replay reaches
    them."""

    def __init__(self, store: FanStore, analyst, notifier: Notifier, concurrency: int = 3):
        self.store, self.analyst, self.notifier = store, analyst, notifier
        self.sem = asyncio.Semaphore(concurrency)
        self.tasks: dict[str, asyncio.Task] = {}
        self._found: dict[str, tuple[str, list[dict]]] = {}

    @staticmethod
    def _signature(prof: dict) -> str:
        return json.dumps([prof.get("name"), prof.get("language"), prof.get("alerts"), club_of(prof),
                           sorted(players_of(prof))])

    def _cache_path(self, fan_id: str) -> Path:
        return self.store.dir / f"{fan_id}.alerts.json"

    def _cache(self, fan_id: str) -> dict:
        p = self._cache_path(fan_id)
        try:
            return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        except (OSError, json.JSONDecodeError):
            return {}

    async def _write_all(self, prof: dict, alerts: list[dict], sig: str) -> None:
        cache = {"signature": sig, "texts": {}}

        async def one(a):
            async with self.sem:
                try:
                    cache["texts"][a["id"]] = await self.notifier.write(a, prof)
                except Exception:       # never let an alert break the app
                    cache["texts"][a["id"]] = template_alert(a, prof.get("name") or "")
                self._cache_path(prof["fan_id"]).write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

        await asyncio.gather(*(one(a) for a in alerts))

    def prepare(self, prof: dict) -> list[dict]:
        """The fan's alerts for the whole match; starts writing them if they aren't written for this profile."""
        sig = self._signature(prof)
        fid0 = prof["fan_id"]
        if self._found.get(fid0, ("", []))[0] != sig:
            self._found[fid0] = (sig, find_alerts(prof, self.analyst))
        alerts = self._found[fid0][1]
        cache = self._cache(prof["fan_id"])
        fid = prof["fan_id"]
        if cache.get("signature") != sig and not (fid in self.tasks and not self.tasks[fid].done()
                                                  and getattr(self.tasks[fid], "sig", None) == sig):
            self._cache_path(fid).write_text(json.dumps({"signature": sig, "texts": {}}), encoding="utf-8")
            task = asyncio.ensure_future(self._write_all(prof, alerts, sig))
            task.sig = sig  # type: ignore[attr-defined]
            self.tasks[fid] = task
        return alerts

    def due(self, fan_id: str, clock_s: float) -> dict:
        """Alerts whose moment the fan has reached. Never anything later than their replay (not even how
        many)."""
        prof = self.store.load(fan_id)
        if prof is None or not prof.get("alerts"):
            return {"alerts": []}
        alerts = self.prepare(prof)
        texts = self._cache(fan_id).get("texts", {})
        out = []
        for a in alerts:
            if a["clock_s"] > clock_s:
                continue
            text = texts.get(a["id"]) or template_alert(a, prof.get("name") or "")
            out.append({"id": a["id"], "clock_s": a["clock_s"], "minute": a["minute"], "kind": a["kind"],
                        "tone": a["tone"], **text})
        return {"alerts": out}
