"""Safe fallback text, built from the facts alone.

Used when the Fan Lens cannot produce text that passes the Verifier (or the model is
unreachable). It is plain but always correct, so the broadcast never shows a wrong
number. Other languages get a translated label with the English fact line, and the
cue is marked as degraded.
"""

from __future__ import annotations

from .state import Candidate, Variant

LABELS = {
    "goal": {"en": "GOAL", "ml": "ഗോൾ", "hi": "गोल", "ta": "கோல்", "es": "GOL", "fr": "BUT", "pt": "GOL", "de": "TOR", "ar": "هدف"},
    "red_card": {"en": "Red card", "ml": "ചുവപ്പ് കാർഡ്", "hi": "लाल कार्ड", "ta": "சிவப்பு அட்டை", "es": "Tarjeta roja",
                 "fr": "Carton rouge", "pt": "Cartão vermelho", "de": "Rote Karte", "ar": "بطاقة حمراء"},
    "half_time": {"en": "Half-time", "ml": "ഹാഫ് ടൈം", "hi": "हाफ़ टाइम", "ta": "இடைவேளை", "es": "Descanso",
                  "fr": "Mi-temps", "pt": "Intervalo", "de": "Halbzeit", "ar": "نهاية الشوط الأول"},
    "full_time": {"en": "Full-time", "ml": "ഫുൾ ടൈം", "hi": "फ़ुल टाइम", "ta": "ஆட்ட முடிவு", "es": "Final",
                  "fr": "Fin du match", "pt": "Fim de jogo", "de": "Abpfiff", "ar": "نهاية المباراة"},
    "prediction_confirmed": {"en": "Scouting call confirmed", "ml": "പ്രവചനം ശരിയായി", "hi": "भविष्यवाणी सही निकली",
                             "ta": "கணிப்பு சரியானது", "es": "Previsión confirmada", "fr": "Prévision confirmée",
                             "pt": "Previsão confirmada", "de": "Prognose bestätigt", "ar": "تأكد التوقع"},
    "injury": {"en": "Injury", "ml": "പരിക്ക്", "hi": "चोट", "ta": "காயம்", "es": "Lesión", "fr": "Blessure",
               "pt": "Lesão", "de": "Verletzung", "ar": "إصابة"},
    "big_chance": {"en": "Big chance", "ml": "വലിയ അവസരം", "hi": "बड़ा मौका", "ta": "பெரிய வாய்ப்பு", "es": "Gran ocasión",
                   "fr": "Grosse occasion", "pt": "Grande chance", "de": "Großchance", "ar": "فرصة كبيرة"},
    "penalty_missed": {"en": "Penalty missed", "ml": "പെനാൽറ്റി പാഴായി", "hi": "पेनल्टी चूकी", "ta": "பெனால்டி தவறியது",
                       "es": "Penalti fallado", "fr": "Penalty manqué", "pt": "Pênalti perdido", "de": "Elfmeter vergeben",
                       "ar": "ركلة جزاء ضائعة"},
    "momentum": {"en": "Momentum", "ml": "മുൻതൂക്കം", "hi": "दबदबा", "ta": "ஆதிக்கம்", "es": "Dominio", "fr": "Temps fort",
                 "pt": "Domínio", "de": "Druckphase", "ar": "سيطرة"},
    "pressure_spell": {"en": "Pressure building", "ml": "സമ്മർദ്ദം", "hi": "दबाव", "ta": "அழுத்தம்", "es": "Presión",
                       "fr": "Pression", "pt": "Pressão", "de": "Druck", "ar": "ضغط"},
    "tempo": {"en": "Tempo", "ml": "കളിയുടെ താളം", "hi": "खेल की रफ़्तार", "ta": "ஆட்டத்தின் வேகம்", "es": "Ritmo",
              "fr": "Rythme", "pt": "Ritmo", "de": "Tempo", "ar": "الإيقاع"},
    "stats": {"en": "Match stats", "ml": "മത്സര കണക്കുകൾ", "hi": "मैच के आंकड़े", "ta": "ஆட்டப் புள்ளிவிவரம்",
              "es": "Estadísticas", "fr": "Statistiques", "pt": "Estatísticas", "de": "Statistik", "ar": "إحصائيات"},
    "player_focus": {"en": "Player focus", "ml": "താരത്തിൽ ശ്രദ്ധ", "hi": "खिलाड़ी पर नज़र", "ta": "வீரர் மீது கவனம்",
                     "es": "Foco en el jugador", "fr": "Focus joueur", "pt": "Foco no jogador", "de": "Spieler im Fokus",
                     "ar": "تركيز على اللاعب"},
    "storyline": {"en": "Pre-match", "ml": "മത്സരത്തിന് മുമ്പ്", "hi": "मैच से पहले", "ta": "ஆட்டத்துக்கு முன்", "es": "Previa",
              "fr": "Avant-match", "pt": "Pré-jogo", "de": "Vorbericht", "ar": "قبل المباراة"},
    "brief_intro": {"en": "Pre-match", "ml": "മത്സരത്തിന് മുമ്പ്", "hi": "मैच से पहले", "ta": "ஆட்டத்துக்கு முன்",
                    "es": "Previa", "fr": "Avant-match", "pt": "Pré-jogo", "de": "Vorbericht", "ar": "قبل المباراة"},
    "recap": {"en": "Match recap", "ml": "മത്സര സംഗ്രഹം", "hi": "मैच सारांश", "ta": "ஆட்டச் சுருக்கம்", "es": "Resumen",
              "fr": "Résumé", "pt": "Resumo", "de": "Zusammenfassung", "ar": "ملخص المباراة"},
}


def _clip(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1].rsplit(" ", 1)[0] + "…"


def headline_en(c: Candidate) -> str:
    d = c.overlay.get("data", {})
    if c.kind == "goal":
        s = d.get("score", {})
        return f"GOAL {d.get('team', '')} {s.get('home', '')}-{s.get('away', '')}: {d.get('scorer', '')}"
    if c.kind == "red_card":
        return f"Red card: {d.get('player', '')}"
    if c.kind == "prediction_confirmed":
        return "Scouting call confirmed"
    if c.kind in ("momentum", "pressure_spell"):
        return f"{d.get('team', '')} on top"
    if c.kind == "injury":
        return f"Injury: {d.get('player', '')}"
    if c.kind == "storyline":
        return d.get("title") or "Pre-match"
    if c.kind == "brief_intro":
        return "Pre-match"
    if c.kind == "recap":
        return "Match recap"
    return LABELS.get(c.kind, {}).get("en", c.kind.replace("_", " ").title())


def fallback(c: Candidate, profile: str, language: str) -> Variant:
    body = " ".join(c.facts[:2]) if profile == "analyst" and c.kind not in ("storyline", "recap") else c.facts[0]
    if c.kind == "brief_intro" and len(c.facts) > 1:
        body = c.facts[1]
    if c.kind == "recap" and len(c.facts) > 1:
        body = c.facts[1]
    if c.kind == "prediction_confirmed" and len(c.facts) > 1:
        body = c.facts[1]
    if language == "en":
        head = headline_en(c)
    else:
        head = LABELS.get(c.kind, {}).get(language) or headline_en(c)
    limit_h, limit_b = (60, 160) if language == "en" else (70, 190)
    return Variant(profile, language, _clip(head, limit_h), _clip(body, limit_b), source="template")
