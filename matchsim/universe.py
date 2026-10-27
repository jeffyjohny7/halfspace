"""The fictional football universe: clubs, players, managers and their hidden truths."""

from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass, field

from . import names

# Positions and formations

POSITIONS = ["GK", "RB", "CB", "LB", "DM", "CM", "AM", "RW", "LW", "ST"]

ATTRIBUTES = [
    "passing", "vision", "press_resistance", "dribbling", "tackling",
    "positioning", "aerial", "finishing", "crossing", "pace", "stamina",
    "discipline", "composure", "set_piece", "gk_handling", "gk_shot_stopping",
    "gk_claiming",
]

# Offset of each attribute from the player's overall quality, by position.
_POS_OFFSETS: dict[str, dict[str, float]] = {
    "GK": {"passing": -12, "vision": -15, "press_resistance": -8, "dribbling": -35,
           "tackling": -40, "positioning": -20, "aerial": -10, "finishing": -50,
           "crossing": -40, "pace": -20, "stamina": -5, "composure": 0,
           "set_piece": -30, "gk_handling": 4, "gk_shot_stopping": 5, "gk_claiming": 3},
    "CB": {"passing": -6, "vision": -10, "press_resistance": -4, "dribbling": -15,
           "tackling": 8, "positioning": 7, "aerial": 10, "finishing": -25,
           "crossing": -20, "pace": -4, "composure": -2, "set_piece": -15},
    "RB": {"pace": 6, "crossing": 4, "tackling": 2, "stamina": 6, "dribbling": -3,
           "finishing": -20, "aerial": -6, "positioning": 0, "set_piece": -8},
    "LB": {"pace": 6, "crossing": 4, "tackling": 2, "stamina": 6, "dribbling": -3,
           "finishing": -20, "aerial": -6, "positioning": 0, "set_piece": -8},
    "DM": {"tackling": 6, "positioning": 6, "passing": 3, "press_resistance": 3,
           "finishing": -15, "crossing": -8, "dribbling": -4, "set_piece": -6},
    "CM": {"passing": 6, "vision": 4, "press_resistance": 4, "stamina": 4,
           "tackling": -2, "finishing": -8, "aerial": -5, "set_piece": 0},
    "AM": {"vision": 8, "passing": 5, "dribbling": 6, "finishing": -2, "tackling": -15,
           "aerial": -10, "positioning": -10, "set_piece": 4},
    "RW": {"pace": 8, "dribbling": 8, "crossing": 5, "finishing": -3, "tackling": -18,
           "aerial": -10, "positioning": -12, "set_piece": 2},
    "LW": {"pace": 8, "dribbling": 8, "crossing": 5, "finishing": -3, "tackling": -18,
           "aerial": -10, "positioning": -12, "set_piece": 2},
    "ST": {"finishing": 10, "aerial": 4, "composure": 5, "passing": -6, "tackling": -20,
           "press_resistance": -2, "positioning": -10, "crossing": -10, "set_piece": -5},
}
for _pos, _offs in _POS_OFFSETS.items():
    if _pos != "GK":
        _offs.setdefault("gk_handling", -45)
        _offs.setdefault("gk_shot_stopping", -45)
        _offs.setdefault("gk_claiming", -45)

SQUAD_TEMPLATE = {"GK": 3, "RB": 2, "CB": 4, "LB": 2, "DM": 2, "CM": 4, "AM": 2,
                  "RW": 2, "LW": 2, "ST": 3}

# Formation slots: (slot name, required squad position, x, y) in the team's own frame. x runs from own goal
# (0) to the opponent goal (105); y runs from the team's right touchline (0) to its left touchline (68).
FORMATIONS: dict[str, list[tuple[str, str, float, float]]] = {
    "4-3-3": [("GK", "GK", 5, 34), ("RB", "RB", 25, 8), ("RCB", "CB", 20, 24),
              ("LCB", "CB", 20, 44), ("LB", "LB", 25, 60), ("DM", "DM", 35, 34),
              ("RCM", "CM", 45, 22), ("LCM", "CM", 45, 46), ("RW", "RW", 65, 9),
              ("ST", "ST", 70, 34), ("LW", "LW", 65, 59)],
    "4-2-3-1": [("GK", "GK", 5, 34), ("RB", "RB", 25, 8), ("RCB", "CB", 20, 24),
                ("LCB", "CB", 20, 44), ("LB", "LB", 25, 60), ("RDM", "DM", 35, 26),
                ("LDM", "CM", 35, 42), ("AM", "AM", 55, 34), ("RW", "RW", 60, 10),
                ("LW", "LW", 60, 58), ("ST", "ST", 70, 34)],
    "4-4-2": [("GK", "GK", 5, 34), ("RB", "RB", 25, 8), ("RCB", "CB", 20, 24),
              ("LCB", "CB", 20, 44), ("LB", "LB", 25, 60), ("RM", "RW", 48, 8),
              ("RCM", "CM", 42, 26), ("LCM", "CM", 42, 42), ("LM", "LW", 48, 60),
              ("RST", "ST", 68, 28), ("LST", "ST", 68, 40)],
    "3-5-2": [("GK", "GK", 5, 34), ("RCB", "CB", 20, 18), ("CB", "CB", 18, 34),
              ("LCB", "CB", 20, 50), ("RWB", "RB", 42, 6), ("LWB", "LB", 42, 62),
              ("DM", "DM", 35, 34), ("RCM", "CM", 48, 24), ("LCM", "CM", 48, 44),
              ("RST", "ST", 68, 28), ("LST", "ST", 68, 40)],
    "3-4-3": [("GK", "GK", 5, 34), ("RCB", "CB", 20, 18), ("CB", "CB", 18, 34),
              ("LCB", "CB", 20, 50), ("RWB", "RB", 45, 6), ("RCM", "CM", 42, 26),
              ("LCM", "DM", 42, 42), ("LWB", "LB", 45, 62), ("RW", "RW", 64, 12),
              ("ST", "ST", 70, 34), ("LW", "LW", 64, 56)],
    "4-1-4-1": [("GK", "GK", 5, 34), ("RB", "RB", 25, 8), ("RCB", "CB", 20, 24),
                ("LCB", "CB", 20, 44), ("LB", "LB", 25, 60), ("DM", "DM", 33, 34),
                ("RM", "RW", 50, 8), ("RCM", "CM", 48, 24), ("LCM", "AM", 48, 44),
                ("LM", "LW", 50, 60), ("ST", "ST", 70, 34)],
}

# Manager philosophies -> (formations they like, style centre values).
PHILOSOPHIES: dict[str, dict] = {
    "possession": {"formations": ["4-3-3", "4-2-3-1", "3-4-3"],
                   "style": {"directness": 0.25, "tempo": 0.45, "press_intensity": 0.65,
                             "press_height": 0.65, "line_height": 0.65, "crossing": 0.35,
                             "counter_focus": 0.25, "shot_propensity": 0.45}},
    "high_press": {"formations": ["4-3-3", "4-2-3-1", "3-4-3"],
                   "style": {"directness": 0.45, "tempo": 0.75, "press_intensity": 0.85,
                             "press_height": 0.8, "line_height": 0.75, "crossing": 0.45,
                             "counter_focus": 0.5, "shot_propensity": 0.6}},
    "counter": {"formations": ["4-4-2", "4-2-3-1", "3-5-2", "4-1-4-1"],
                "style": {"directness": 0.7, "tempo": 0.6, "press_intensity": 0.35,
                          "press_height": 0.3, "line_height": 0.3, "crossing": 0.5,
                          "counter_focus": 0.85, "shot_propensity": 0.55}},
    "direct": {"formations": ["4-4-2", "3-5-2", "4-1-4-1"],
               "style": {"directness": 0.8, "tempo": 0.55, "press_intensity": 0.5,
                         "press_height": 0.45, "line_height": 0.45, "crossing": 0.75,
                         "counter_focus": 0.5, "shot_propensity": 0.6}},
    "balanced": {"formations": ["4-2-3-1", "4-3-3", "4-4-2", "4-1-4-1", "3-5-2"],
                 "style": {"directness": 0.5, "tempo": 0.5, "press_intensity": 0.55,
                           "press_height": 0.5, "line_height": 0.5, "crossing": 0.5,
                           "counter_focus": 0.5, "shot_propensity": 0.5}},
}

# Data classes


@dataclass
class Player:
    player_id: str
    name: str
    position: str
    birth_year: int
    height_cm: int
    preferred_foot: str
    shirt: int
    club_id: str
    attrs: dict[str, float]

    @property
    def overall(self) -> float:
        keys = KEY_ATTRS[self.position]
        return sum(self.attrs[k] for k in keys) / len(keys)


KEY_ATTRS = {
    "GK": ["gk_handling", "gk_shot_stopping", "gk_claiming", "passing"],
    "CB": ["tackling", "positioning", "aerial", "passing", "pace"],
    "RB": ["tackling", "pace", "crossing", "passing", "stamina"],
    "LB": ["tackling", "pace", "crossing", "passing", "stamina"],
    "DM": ["tackling", "positioning", "passing", "press_resistance"],
    "CM": ["passing", "vision", "press_resistance", "stamina"],
    "AM": ["vision", "passing", "dribbling", "finishing"],
    "RW": ["pace", "dribbling", "crossing", "finishing"],
    "LW": ["pace", "dribbling", "crossing", "finishing"],
    "ST": ["finishing", "composure", "aerial", "pace"],
}


@dataclass
class Manager:
    manager_id: str
    name: str
    philosophy: str
    formation: str
    style: dict[str, float]


@dataclass
class Club:
    club_id: str
    name: str
    short_name: str
    town: str
    stadium: str
    colours: tuple[str, str]
    division: int
    quality: float
    manager: Manager
    # Hidden team traits not tied to the manager's style.
    traits: dict[str, float] = field(default_factory=dict)
    squad: list[Player] = field(default_factory=list)

    @property
    def formation(self) -> str:
        return self.manager.formation

    def style(self) -> dict[str, float]:
        """Manager style plus club traits: everything the engine needs."""
        out = dict(self.manager.style)
        out.update(self.traits)
        return out


@dataclass
class Truth:
    """One entry in the answer key."""

    truth_id: str
    season: str
    scope: str            # "team" | "player"
    club_id: str
    club_name: str
    trait: str
    direction: str        # "weakness" | "strength" | "change"
    hidden_value: float
    league_percentile: float
    description: str
    expected_signal: str
    planted: bool
    player_id: str | None = None
    player_name: str | None = None
    position: str | None = None


# Trait catalogue: what we can plant, and how it should show up in the data.

TEAM_TRAITS = {
    # name: (style/trait key, extreme value, direction, description, expected signal)
    "set_piece_defense_weak": ("set_piece_defense", 0.08, "weakness",
                               "Poor at defending set pieces (corners and wide free kicks).",
                               "Goals and shots conceded from set pieces per match well above league average"),
    "set_piece_attack_strong": ("set_piece_attack", 0.93, "strength",
                                "Dangerous from attacking set pieces.",
                                "Set-piece goals and xG per match well above league average"),
    "late_fade": ("fitness", 0.08, "weakness",
                  "Fitness drops sharply late in matches.",
                  "Share of goals conceded after the 75th minute well above league average"),
    "high_line_exposed": ("line_height", 0.95, "weakness",
                          "Plays a very high defensive line that is exposed by balls in behind.",
                          "Shots and goals conceded from counter-attacks and through balls above average"),
    "poor_discipline": ("discipline", 0.08, "weakness",
                        "Commits many fouls and picks up cards.",
                        "Fouls and yellow cards per match well above league average"),
    "fortress_home": ("home_boost", 0.95, "strength",
                      "Much stronger at home than away.",
                      "Home-minus-away points per match gap well above league average"),
    "left_flank_focus": ("left_bias", 0.9, "strength",
                         "Builds most attacks down the left flank.",
                         "Share of final-third entries on the left well above league average"),
    "right_flank_focus": ("right_bias", 0.9, "strength",
                          "Builds most attacks down the right flank.",
                          "Share of final-third entries on the right well above league average"),
}

PLAYER_TRAITS = {
    # name: (eligible positions, attribute, extreme value, direction, description, signal)
    "loses_ball_under_pressure": (["RB", "LB", "CB", "DM", "CM"], "press_resistance", 36,
                                  "weakness", "Loses the ball often when pressed.",
                                  "Dispossessions/turnovers under pressure per 90 well above position average"),
    "weak_in_the_air": (["CB"], "aerial", 38, "weakness", "Loses aerial duels, especially at set pieces.",
                        "Aerial duel win rate well below centre-back average"),
    "error_prone_passer": (["CB", "DM", "CM"], "passing", 40, "weakness",
                           "Misplaces passes, including short ones.",
                           "Pass completion well below position average for similar pass difficulty"),
    "clinical_finisher": (["ST", "RW", "LW", "AM"], "finishing", 94, "strength",
                          "Converts chances far above expectation.",
                          "Goals minus xG strongly positive"),
    "elite_crosser": (["RB", "LB", "RW", "LW"], "crossing", 93, "strength",
                      "Delivers dangerous crosses.",
                      "Cross completion and shots assisted from crosses well above average"),
    "press_resistant_playmaker": (["CM", "DM", "AM"], "press_resistance", 95, "strength",
                                  "Keeps the ball under pressure and breaks the press.",
                                  "Turnovers under pressure per 90 well below position average"),
    "goalkeeper_weak_on_crosses": (["GK"], "gk_claiming", 35, "weakness",
                                   "Struggles to claim crosses.",
                                   "Cross claims low; goals conceded from crosses/corners above average"),
    "hothead": (["CB", "DM", "CM", "RB", "LB"], "discipline", 15, "weakness",
                "Fouls a lot and picks up cards.",
                "Fouls and cards per 90 well above position average"),
}


# Building the universe


class UniverseBuilder:
    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        self.used_names: set[str] = set()
        self.used_stadiums: set[str] = set()
        self._pid = 0
        self._mid = 0

    # -- helpers --------------------------------------------------------------
    def _next_pid(self) -> str:
        self._pid += 1
        return f"P{self._pid:05d}"

    def _next_mid(self) -> str:
        self._mid += 1
        return f"M{self._mid:03d}"

    def make_player(self, position: str, quality: float, club_id: str, season_year: int,
                    shirt: int, age: int | None = None) -> Player:
        rng = self.rng
        if age is None:
            age = int(min(36, max(17, rng.gauss(26, 4))))
        # Prime-age players are a little better.
        age_adj = -3.0 if age <= 20 else (-1.0 if age <= 22 else (-1.5 if age >= 33 else 0.0))
        q = quality + rng.gauss(0, 4.5) + age_adj
        attrs = {}
        offs = _POS_OFFSETS[position]
        for a in ATTRIBUTES:
            val = q + offs.get(a, 0.0) + rng.gauss(0, 6)
            attrs[a] = round(min(97.0, max(20.0, val)), 1)
        if position == "GK":
            height = int(rng.gauss(190, 4))
        elif position in ("CB", "ST"):
            height = int(rng.gauss(186, 5))
        else:
            height = int(rng.gauss(178, 5))
        foot = "left" if (position in ("LB", "LW") and rng.random() < 0.7) or rng.random() < 0.2 else "right"
        return Player(
            player_id=self._next_pid(),
            name=names.person_name(rng, self.used_names),
            position=position,
            birth_year=season_year - age,
            height_cm=height,
            preferred_foot=foot,
            shirt=shirt,
            club_id=club_id,
            attrs=attrs,
        )

    def make_manager(self, philosophy: str | None = None) -> Manager:
        rng = self.rng
        if philosophy is None:
            philosophy = rng.choices(list(PHILOSOPHIES), weights=[3, 2, 2, 2, 3])[0]
        phil = PHILOSOPHIES[philosophy]
        formation = rng.choice(phil["formations"])
        style = {k: round(min(0.98, max(0.02, v + rng.gauss(0, 0.1))), 3)
                 for k, v in phil["style"].items()}
        return Manager(self._next_mid(), names.person_name(rng, self.used_names),
                       philosophy, formation, style)

    def make_club(self, idx: int, town: str, division: int, quality: float) -> Club:
        rng = self.rng
        suffix = rng.choice(names.CLUB_SUFFIXES)
        club_id = f"C{idx:02d}"
        name = f"{town} {suffix}"
        short = town.split()[0][:3].upper()
        club = Club(
            club_id=club_id, name=name, short_name=short, town=town,
            stadium=names.stadium_name(rng, self.used_stadiums),
            colours=names.KIT_COLOURS[idx % len(names.KIT_COLOURS)],
            division=division, quality=quality, manager=self.make_manager(),
            traits={
                "set_piece_attack": round(rng.uniform(0.3, 0.7), 3),
                "set_piece_defense": round(rng.uniform(0.3, 0.7), 3),
                "fitness": round(rng.uniform(0.35, 0.75), 3),
                "discipline": round(rng.uniform(0.3, 0.75), 3),
                "home_boost": round(rng.uniform(0.3, 0.7), 3),
                "left_bias": round(rng.uniform(0.3, 0.6), 3),
                "right_bias": round(rng.uniform(0.3, 0.6), 3),
            },
        )
        shirt = 1
        for pos, count in SQUAD_TEMPLATE.items():
            for i in range(count):
                # First choices are better than backups.
                q = quality + (1.5 if i == 0 else -2.5 * i)
                club.squad.append(self.make_player(pos, q, club_id, 2025, shirt))
                shirt += 1
        return club


def _normal_quantiles(n: int) -> list[float]:
    """Standard-normal quantiles at (i + 0.5) / n, highest first."""
    from statistics import NormalDist
    nd = NormalDist()
    return [nd.inv_cdf(1 - (i + 0.5) / n) for i in range(n)]


@dataclass
class Universe:
    clubs: list[Club]
    builder: UniverseBuilder

    def club(self, club_id: str) -> Club:
        return next(c for c in self.clubs if c.club_id == club_id)

    def division(self, div: int) -> list[Club]:
        return [c for c in self.clubs if c.division == div]


def build_universe(seed: int, top_size: int = 20, second_size: int = 24) -> Universe:
    """Create all clubs for the previous season (top division + second tier)."""
    b = UniverseBuilder(seed)
    towns = list(names.TOWNS)
    b.rng.shuffle(towns)
    clubs: list[Club] = []
    # Top division: a few elite clubs, a big middle, a weak tail.
    top_q = [70 + (1.8 if z > 0 else 1.35) * z + b.rng.gauss(0, 0.35) for z in _normal_quantiles(top_size)]
    top_q[0] += 2.0
    top_q[1] += 1.3
    top_q[2] += 0.7
    top_q[3] += 0.3
    top_q.sort(reverse=True)
    for i, q in enumerate(top_q):
        clubs.append(b.make_club(i + 1, towns[i], 1, round(q, 2)))
    sec_q = sorted([63.5 + 1.7 * z + b.rng.gauss(0, 0.35) for z in _normal_quantiles(second_size)],
                   reverse=True)
    for j, q in enumerate(sec_q):
        clubs.append(b.make_club(top_size + j + 1, towns[top_size + j], 2, round(q, 2)))
    return Universe(clubs, b)


# Lineups


def best_xi(club: Club, exclude: set[str] | None = None) -> list[tuple[str, Player]]:
    """Pick the best available player for each formation slot."""
    exclude = exclude or set()
    used: set[str] = set(exclude)
    xi: list[tuple[str, Player]] = []
    for slot, pos, _x, _y in FORMATIONS[club.formation]:
        candidates = [p for p in club.squad if p.position == pos and p.player_id not in used]
        if not candidates:  # fall back to any outfield/keeper of a related position
            related = RELATED_POSITIONS.get(pos, [])
            candidates = [p for p in club.squad if p.position in related and p.player_id not in used]
        if not candidates:
            candidates = [p for p in club.squad if p.player_id not in used and p.position != "GK"]
        best = max(candidates, key=lambda p: p.overall)
        used.add(best.player_id)
        xi.append((slot, best))
    return xi


RELATED_POSITIONS = {
    "RB": ["CB", "RW", "DM"], "LB": ["CB", "LW", "DM"], "CB": ["DM", "RB", "LB"],
    "DM": ["CM", "CB"], "CM": ["DM", "AM"], "AM": ["CM", "RW", "LW", "ST"],
    "RW": ["LW", "AM", "ST"], "LW": ["RW", "AM", "ST"], "ST": ["AM", "RW", "LW"],
    "GK": ["GK"],
}


# Planting traits and the answer key


def _percentile(value: float, population: list[float]) -> float:
    below = sum(1 for v in population if v < value)
    equal = sum(1 for v in population if v == value)
    return round(100.0 * (below + 0.5 * equal) / max(1, len(population)), 1)


def plant_traits(clubs: list[Club], division: int, season: str, rng: random.Random,
                 team_traits_per_club: tuple[int, int] = (1, 2),
                 player_traits_per_club: tuple[int, int] = (1, 2)) -> list[Truth]:
    """Push some hidden values to extremes and record them as truths."""
    truths: list[Truth] = []
    div_clubs = [c for c in clubs if c.division == division]
    for club in div_clubs:
        # --- team traits
        n_team = rng.randint(*team_traits_per_club)
        options = list(TEAM_TRAITS)
        rng.shuffle(options)
        chosen: list[str] = []
        for name in options:
            if len(chosen) >= n_team:
                break
            if name == "left_flank_focus" and "right_flank_focus" in chosen:
                continue
            if name == "right_flank_focus" and "left_flank_focus" in chosen:
                continue
            chosen.append(name)
        for name in chosen:
            key, value, direction, desc, signal = TEAM_TRAITS[name]
            if key in club.manager.style:
                club.manager.style[key] = value
            else:
                club.traits[key] = value
            if name == "left_flank_focus":
                club.traits["right_bias"] = 0.2
            if name == "right_flank_focus":
                club.traits["left_bias"] = 0.2
            pop = [c.style()[key] for c in div_clubs]
            truths.append(Truth(
                truth_id=f"{season}-{club.club_id}-{name}", season=season, scope="team",
                club_id=club.club_id, club_name=club.name, trait=name, direction=direction,
                hidden_value=value, league_percentile=_percentile(value, pop),
                description=desc, expected_signal=signal, planted=True))
        # --- player traits (only on likely starters)
        starters = {p.player_id for _, p in best_xi(club)}
        n_player = rng.randint(*player_traits_per_club)
        ptraits = list(PLAYER_TRAITS)
        rng.shuffle(ptraits)
        planted_players: set[str] = set()
        for name in ptraits:
            if n_player <= 0:
                break
            positions, attr, value, direction, desc, signal = PLAYER_TRAITS[name]
            candidates = [p for p in club.squad if p.position in positions
                          and p.player_id in starters and p.player_id not in planted_players]
            if not candidates:
                continue
            player = rng.choice(candidates)
            before = player.overall
            player.attrs[attr] = float(value)
            _restore_overall(player, before, attr)
            planted_players.add(player.player_id)
            n_player -= 1
            pop = [q.attrs[attr] for c in div_clubs for q in c.squad if q.position == player.position]
            truths.append(Truth(
                truth_id=f"{season}-{player.player_id}-{name}", season=season, scope="player",
                club_id=club.club_id, club_name=club.name, trait=name, direction=direction,
                hidden_value=float(value), league_percentile=_percentile(float(value), pop),
                description=desc, expected_signal=signal, planted=True,
                player_id=player.player_id, player_name=player.name, position=player.position))
    return truths


def _restore_overall(player: Player, target: float, planted_attr: str) -> None:
    """A planted weakness should not drop the player out of the team: raise his other key attributes so his
    overall rating is unchanged."""
    keys = [k for k in KEY_ATTRS[player.position] if k != planted_attr]
    for _ in range(40):
        gap = target - player.overall
        if gap <= 0.05 or not keys:
            break
        bump = gap * len(KEY_ATTRS[player.position]) / len(keys)
        for k in keys:
            player.attrs[k] = round(min(97.0, player.attrs[k] + bump), 1)


def refresh_truths(truths: list[Truth], clubs: list[Club], season: str) -> list[Truth]:
    """Carry planted truths into a new season if they still hold for a top-flight club."""
    by_id = {c.club_id: c for c in clubs}
    players = {p.player_id: (p, c) for c in clubs for p in c.squad}
    out: list[Truth] = []
    for t in truths:
        if t.scope == "team":
            club = by_id.get(t.club_id)
            if club is None or club.division != 1:
                continue
            key = TEAM_TRAITS[t.trait][0]
            value = club.style().get(key)
            if value is None or abs(value - t.hidden_value) > 0.15:
                continue  # new manager changed it
            out.append(Truth(**{**asdict(t), "truth_id": t.truth_id.replace(t.season, season, 1),
                                "season": season, "hidden_value": value}))
        else:
            found = players.get(t.player_id or "")
            if not found:
                continue
            player, club = found
            if club.division != 1:
                continue
            attr = PLAYER_TRAITS[t.trait][1]
            out.append(Truth(**{**asdict(t), "truth_id": t.truth_id.replace(t.season, season, 1),
                                "season": season, "club_id": club.club_id,
                                "club_name": club.name, "hidden_value": player.attrs[attr]}))
    return out


# Offseason: ageing, transfers, promoted-club signings, manager changes


@dataclass
class OffseasonLog:
    transfers: list[dict] = field(default_factory=list)
    manager_changes: list[dict] = field(default_factory=list)
    signings: list[dict] = field(default_factory=list)
    retirements: list[dict] = field(default_factory=list)


def run_offseason(universe: Universe, relegated: list[str], promoted: list[str],
                  underperformers: list[str], season_year: int, transfers: int,
                  rng: random.Random) -> tuple[OffseasonLog, list[Truth]]:
    """Mutate clubs in place for the new season. Returns a log and new truths."""
    clubs = universe.clubs
    b = universe.builder
    log = OffseasonLog()
    new_truths: list[Truth] = []
    by_id = {c.club_id: c for c in clubs}

    # 1. Promotion / relegation
    for cid in relegated:
        by_id[cid].division = 2
    for cid in promoted:
        by_id[cid].division = 1

    # 2. Ageing and development (planted traits drift only a little)
    for club in clubs:
        keep: list[Player] = []
        for p in club.squad:
            age = season_year - p.birth_year
            if age >= 36 or (age >= 34 and rng.random() < 0.35):
                log.retirements.append({"player_id": p.player_id, "name": p.name,
                                        "club_id": club.club_id, "age": age})
                continue
            if age <= 21:
                delta = rng.uniform(1.0, 4.5)
            elif age <= 24:
                delta = rng.uniform(0.0, 2.5)
            elif age <= 29:
                delta = rng.uniform(-1.0, 1.0)
            elif age <= 32:
                delta = rng.uniform(-2.5, 0.0)
            else:
                delta = rng.uniform(-4.0, -1.0)
            for a in p.attrs:
                p.attrs[a] = round(min(97.0, max(20.0, p.attrs[a] + delta + rng.gauss(0, 0.8))), 1)
            keep.append(p)
        club.squad = keep

    # 3. Refill squads to template (youth / free agents)
    for club in clubs:
        _refill_squad(club, b, season_year, quality=club.quality - 4)

    # 4. Transfers: strong top-flight clubs buy the best player at a position
    #    from a weaker club, if he is better than their starter there.
    top = sorted([c for c in clubs if c.division == 1], key=lambda c: -c.quality)
    buyers = top[:10]
    sellers = [c for c in clubs if c not in buyers]
    for _ in range(transfers):
        buyer = rng.choice(buyers)
        pos = rng.choice([p for p in POSITIONS if p != "GK"])
        their_best = max((p for p in buyer.squad if p.position == pos), key=lambda p: p.overall,
                         default=None)
        pool = [(p, s) for s in sellers for p in s.squad if p.position == pos
                and season_year - p.birth_year <= 29]
        if not pool or their_best is None:
            continue
        target, seller = max(pool, key=lambda ps: ps[0].overall + rng.gauss(0, 2))
        if target.overall <= their_best.overall + 1.0:
            continue
        seller.squad.remove(target)
        target.club_id = buyer.club_id
        buyer.squad.append(target)
        # Buyer sells its weakest player at that position to keep squad size.
        weakest = min((p for p in buyer.squad if p.position == pos), key=lambda p: p.overall)
        buyer.squad.remove(weakest)
        weakest.club_id = seller.club_id
        seller.squad.append(weakest)
        log.transfers.append({"player_id": target.player_id, "name": target.name,
                              "position": pos, "from": seller.club_id, "to": buyer.club_id,
                              "swap_player_id": weakest.player_id})

    # 5. Promoted clubs strengthen with signings around top-flight level.
    floor_q = min(c.quality for c in clubs if c.division == 1 and c.club_id not in promoted)
    for cid in promoted:
        club = by_id[cid]
        club.quality = round(max(club.quality + 2.5, floor_q - 0.5), 2)
        for pos in rng.sample(["CB", "CM", "ST", "RW", "LW", "DM", "LB", "RB"], 3):
            new = b.make_player(pos, club.quality + 1.0, club.club_id, season_year,
                                shirt=40 + len(log.signings))
            club.squad.append(new)
            log.signings.append({"player_id": new.player_id, "name": new.name,
                                 "position": pos, "club_id": cid})

    # 6. Manager changes: relegated clubs + underperformers sack their manager.
    for cid in list(relegated) + list(underperformers):
        club = by_id[cid]
        old = club.manager
        new_phil = rng.choice([p for p in PHILOSOPHIES if p != old.philosophy])
        club.manager = b.make_manager(new_phil)
        log.manager_changes.append({"club_id": cid, "old_manager": old.name,
                                    "old_philosophy": old.philosophy, "old_formation": old.formation,
                                    "new_manager": club.manager.name,
                                    "new_philosophy": new_phil,
                                    "new_formation": club.manager.formation})
        if club.division == 1:
            div1 = [c for c in clubs if c.division == 1]
            for key in ("press_intensity", "directness"):
                before, after = old.style[key], club.manager.style[key]
                if abs(after - before) >= 0.25:
                    pop = [c.style()[key] for c in div1]
                    new_truths.append(Truth(
                        truth_id=f"{season_year}-{cid}-style_change-{key}",
                        season="", scope="team", club_id=cid, club_name=club.name,
                        trait=f"style_change_{key}", direction="change",
                        hidden_value=after, league_percentile=_percentile(after, pop),
                        description=(f"New manager {club.manager.name} changed {key.replace('_', ' ')} "
                                     f"from {before:.2f} to {after:.2f} ({old.formation} -> "
                                     f"{club.manager.formation})."),
                        expected_signal=("Pressures per opponent pass changed vs last season"
                                         if key == "press_intensity" else
                                         "Long-pass share changed vs last season"),
                        planted=True))
    return log, new_truths


def _refill_squad(club: Club, b: UniverseBuilder, season_year: int, quality: float) -> None:
    counts: dict[str, int] = {}
    for p in club.squad:
        counts[p.position] = counts.get(p.position, 0) + 1
    shirts = {p.shirt for p in club.squad}
    for pos, need in SQUAD_TEMPLATE.items():
        while counts.get(pos, 0) < need:
            shirt = next(s for s in range(1, 99) if s not in shirts)
            shirts.add(shirt)
            age = b.rng.randint(18, 22)
            club.squad.append(b.make_player(pos, quality, club.club_id, season_year, shirt, age=age))
            counts[pos] = counts.get(pos, 0) + 1


def natural_extremes(clubs: list[Club], season: str, planted_ids: set[str],
                     pct: float = 3.0) -> list[Truth]:
    """Unplanted but extreme attributes of regular starters (bonus truths)."""
    out: list[Truth] = []
    div1 = [c for c in clubs if c.division == 1]
    by_pos: dict[str, list[Player]] = {}
    starters: dict[str, Club] = {}
    for c in div1:
        for _slot, p in best_xi(c):
            starters[p.player_id] = c
    for c in div1:
        for p in c.squad:
            by_pos.setdefault(p.position, []).append(p)
    for trait, (positions, attr, _v, direction, desc, signal) in PLAYER_TRAITS.items():
        for pid, club in starters.items():
            p = next(q for q in club.squad if q.player_id == pid)
            if p.position not in positions or pid in planted_ids:
                continue
            pop = [q.attrs[attr] for q in by_pos[p.position]]
            perc = _percentile(p.attrs[attr], pop)
            hit = perc <= pct if direction == "weakness" else perc >= 100 - pct
            if hit:
                out.append(Truth(
                    truth_id=f"{season}-{pid}-{trait}-natural", season=season, scope="player",
                    club_id=club.club_id, club_name=club.name, trait=trait, direction=direction,
                    hidden_value=p.attrs[attr], league_percentile=perc, description=desc,
                    expected_signal=signal, planted=False, player_id=pid, player_name=p.name,
                    position=p.position))
    return out


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))
