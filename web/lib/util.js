// Small shared helpers: escaping, numbers, minutes, team colours.

export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[c]));

export const pct = (v, d = 0) => (v == null ? "–" : `${(v * 100).toFixed(d)}%`);
export const num = (v, d = 2) => (v == null ? "–" : Number(v).toFixed(d));
export const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

export function minuteLabel(minute, period) {
  if (period === 1 && minute > 45) return `45+${minute - 45}′`;
  if (period === 2 && minute > 90) return `90+${minute - 90}′`;
  return `${minute}′`;
}

// Binary search: number of items whose key <= x (items sorted by key).
export function countUpTo(items, x, key) {
  let lo = 0, hi = items.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (key(items[mid]) <= x) lo = mid + 1; else hi = mid;
  }
  return lo;
}

// Lighter tint of a hex colour, for text in team colour on the dark pitch.
export function tint(hex, amount = 0.4) {
  const h = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  const mix = (c) => Math.round(c + (255 - c) * amount);
  return `#${[mix(r), mix(g), mix(b)].map((c) => c.toString(16).padStart(2, "0")).join("")}`;
}

export const LANG_OF = (viewerKey) => (viewerKey || "").split("/")[1] || "en";

export const LANG_ORDER = ["en", "es", "ar", "hi", "ml", "ta", "fr", "pt", "de"];
export const LANG_NAMES = { en: "English", es: "Español", ar: "العربية", hi: "हिन्दी", ml: "മലയാളം", ta: "தமிழ்",
  fr: "Français", pt: "Português", de: "Deutsch" };
const RTL = new Set(["ar", "he", "fa", "ur"]);
// lang (and dir for right-to-left scripts) for an element holding text in that language.
export const langAttrs = (lang) => `lang="${lang}"${RTL.has(lang) ? ' dir="rtl"' : ""}`;

export const STATUS_TEXT = {
  "too early": "Too early to tell",
  "on track": "On track",
  "behind pace": "Behind pace",
  confirmed: "Confirmed",
  "did not happen": "Didn't happen",
  "not happening": "Not happening",
  "waiting for a sample": "Waiting for enough duels",
  "not yet": "Not yet",
};

export const KIND_TEXT = {
  goal: "Goal", red_card: "Red card", big_chance: "Big chance", penalty_missed: "Penalty missed",
  momentum: "Momentum", pressure_spell: "Pressure", tempo: "Tempo", stats: "Match numbers",
  half_time: "Half-time", full_time: "Full time", prediction_confirmed: "Scouting call confirmed",
  player_focus: "Player focus", injury: "Injury", storyline: "Before kick-off", brief_intro: "Before kick-off",
  recap: "Full time",
};

export function shirtSVG(colour, trim, number, crossed = false) {
  return `<svg viewBox="0 0 64 64" aria-hidden="true">
    <path d="M22 6 L12 10 L4 22 L12 27 L16 22 L16 58 L48 58 L48 22 L52 27 L60 22 L52 10 L42 6 Q32 14 22 6 Z"
      fill="${colour}" stroke="${trim}" stroke-width="2" stroke-linejoin="round"/>
    <text x="32" y="44" text-anchor="middle" font-family="Anek, sans-serif" font-weight="700"
      font-size="20" fill="${trim}" style="font-variation-settings:'wdth' 75">${number ?? ""}</text>
    ${crossed ? '<path class="x" d="M14 14 L50 52 M50 14 L14 52" fill="none" stroke-linecap="round"/>' : ""}
  </svg>`;
}

export function crestFallback(club) {
  const [p, s] = club.kit;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><path d="M32 3 L57 11 L57 32 C57 47 46 56 32 61 C18 56 7 47 7 32 L7 11 Z" fill="${p}" stroke="${s}" stroke-width="3"/><text x="32" y="40" text-anchor="middle" font-family="sans-serif" font-weight="700" font-size="17" fill="${s}">${club.short}</text></svg>`;
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

export function crestImg(club, cls = "crest") {
  const fb = crestFallback(club);
  return `<img class="${cls}" src="assets/crests/crest-${club.id}.webp" alt="${esc(club.name)} crest"
    onerror="this.onerror=null;this.src='${fb}'">`;
}
