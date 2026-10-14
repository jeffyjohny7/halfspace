"""Fictional names for the league universe.

Everything here is invented: town names, club suffixes, stadiums and player
surnames are built so they do not point at real clubs, players or trademarks.
"""

from __future__ import annotations

import random

LEAGUE_NAMES = {
    1: "Crown League",
    2: "Crown League Two",
}

# Invented town names (44 needed: 20 top flight + 24 second tier).
TOWNS = [
    "Kelvarth", "Duncliffe", "Marrowgate", "Saltmere", "Ravenholt", "Corrowby",
    "Thistlewick", "Brennamoor", "Hollowmere", "Vexley Cross", "Grimsforth",
    "Penmarrow", "Elderbridge", "Stonemarsh", "Fairhollow", "Larkspur Bay",
    "Varnholm", "Calderwyn", "Ashbrook Vale", "Morrowdene", "Tallowfield",
    "Breckhaven", "Quarlston", "Dunvarrow", "Highcrest", "Lowmarsh", "Swanmoor",
    "Ironvale", "Coldwyke", "Gallowmere", "Mistlecombe", "Rookhaven",
    "Blackmire", "Harrowdeen", "Kestrelford", "Ambershaw", "Pellmoor",
    "Sedgecombe", "Torvale", "Wrenfield", "Oxmere", "Glimmerstone", "Fennholt",
    "Briarstead", "Cragmouth", "Wyncaster",
]

CLUB_SUFFIXES = [
    "United", "City", "Athletic", "Rovers", "Wanderers", "Town", "County",
    "Rangers", "Harriers", "Borough", "FC", "Albion",
]

STADIUM_SUFFIXES = ["Park", "Road", "Lane", "Ground", "Arena", "Meadow", "Field"]
STADIUM_PREFIXES = [
    "Harbour", "Mill", "Kingsgate", "Old Quarry", "Riverside", "Foundry",
    "Chapel", "Beacon", "Lantern", "Ferry", "Copper", "Saltworks", "Orchard",
    "Signal", "Weaver", "Granary", "Tannery", "Wharf", "Rope Walk", "Bellfield",
]

# Colours as hex pairs (primary, secondary).
KIT_COLOURS = [
    ("#1F4E9C", "#FFFFFF"), ("#B3202A", "#FFFFFF"), ("#0B6E4F", "#F2C14E"),
    ("#2B2D42", "#EF233C"), ("#F4A259", "#2E294E"), ("#5F0F40", "#FB8B24"),
    ("#3A86FF", "#FFBE0B"), ("#264653", "#E9C46A"), ("#6A040F", "#FFBA08"),
    ("#023E8A", "#90E0EF"), ("#2D6A4F", "#D8F3DC"), ("#7B2CBF", "#E0AAFF"),
    ("#212529", "#FFD60A"), ("#9D0208", "#F48C06"), ("#003049", "#FCBF49"),
    ("#386641", "#F2E8CF"), ("#5A189A", "#FFFFFF"), ("#E63946", "#1D3557"),
    ("#0077B6", "#FFFFFF"), ("#8D0801", "#BF9B30"), ("#14213D", "#FCA311"),
    ("#4A4E69", "#F2E9E4"), ("#6D597A", "#EAAC8B"), ("#355070", "#E56B6F"),
]

FIRST_NAMES = [
    # Deliberately broad and international.
    "Aaron", "Adam", "Adrian", "Ade", "Ali", "Amir", "Andre", "Anton", "Arjun",
    "Arlo", "Ben", "Bruno", "Caleb", "Carlos", "Cian", "Daniel", "Dario", "David",
    "Dev", "Diego", "Elias", "Emeka", "Emil", "Eric", "Ethan", "Felix", "Finn",
    "Gabriel", "Hamza", "Hugo", "Ibrahim", "Isaac", "Ivan", "Jakub", "Jamal",
    "Javier", "Jonas", "Jordan", "Joel", "Kai", "Karim", "Kenji", "Kofi", "Leo",
    "Liam", "Lucas", "Luka", "Malik", "Marco", "Mateo", "Max", "Milan", "Musa",
    "Nathan", "Nico", "Noah", "Oliver", "Omar", "Oscar", "Pablo", "Pedro",
    "Rafael", "Rhys", "Rohan", "Ruben", "Sami", "Santiago", "Sebastian", "Sven",
    "Tariq", "Theo", "Tomas", "Tyrone", "Victor", "Wesley", "Yannick", "Yusuf",
    "Zane", "Callum", "Declan", "Kwame", "Mikel", "Nils", "Aurelio", "Stellan",
]

_SURNAME_START = [
    "Ash", "Bel", "Bran", "Cal", "Dar", "Del", "Ek", "Fal", "Gar", "Hal", "Ish",
    "Jar", "Kel", "Kor", "Lan", "Mar", "Mor", "Nal", "Ob", "Ol", "Pel", "Quin",
    "Rav", "Ros", "Sal", "Sev", "Tam", "Tor", "Ul", "Var", "Ves", "Wil", "Yar",
    "Zel", "Ad", "Ber", "Cor", "Dun", "Fen", "Gil", "Hed", "Ik", "Lor", "Nev",
]
_SURNAME_MID = [
    "", "", "", "a", "e", "i", "o", "u", "ar", "en", "il", "or", "um", "an",
    "ev", "ib", "od",
]
_SURNAME_END = [
    "ani", "ard", "berg", "by", "cott", "dra", "eke", "ell", "ema", "enko",
    "ero", "ford", "gard", "ham", "ici", "ilo", "ino", "isson", "ley", "lund",
    "mann", "mere", "ndo", "ney", "nov", "ola", "ore", "ovic", "quist", "rez",
    "ric", "sen", "son", "ston", "tez", "tti", "uba", "vik", "well", "wick",
    "yi", "zak",
]


def surname(rng: random.Random) -> str:
    name = rng.choice(_SURNAME_START) + rng.choice(_SURNAME_MID) + rng.choice(_SURNAME_END)
    return name[0].upper() + name[1:].lower()


def person_name(rng: random.Random, used: set[str]) -> str:
    """Return a unique invented 'First Surname'."""
    for _ in range(200):
        name = f"{rng.choice(FIRST_NAMES)} {surname(rng)}"
        if name not in used:
            used.add(name)
            return name
    raise RuntimeError("Ran out of unique names")


def stadium_name(rng: random.Random, used: set[str]) -> str:
    for _ in range(200):
        name = f"{rng.choice(STADIUM_PREFIXES)} {rng.choice(STADIUM_SUFFIXES)}"
        if name not in used:
            used.add(name)
            return name
    raise RuntimeError("Ran out of stadium names")
