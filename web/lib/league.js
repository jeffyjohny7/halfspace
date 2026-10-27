// The league around the live match: clubs, tables, results, fixtures, leaders, players.
// league.json is loaded at start; each season's players / clubs / matches load on first use.
import { esc, tint } from "./util.js";

export const L = { data: null, seasons: {} };

export async function loadLeague() {
  const res = await fetch("data/league.json");
  if (!res.ok) throw new Error(`league.json ${res.status}`);
  L.data = await res.json();
  return L.data;
}

// One season's detail files, cached. kind: players | clubs | matches
export async function seasonFile(season, kind) {
  const key = `${season}/${kind}`;
  if (!L.seasons[key]) {
    L.seasons[key] = fetch(`data/${season}/${kind}.json`).then((r) => {
      if (!r.ok) throw new Error(`${key} ${r.status}`);
      return r.json();
    });
  }
  return L.seasons[key];
}

export const club = (id) => ({ id, ...(L.data.clubs[id] || { name: id, code: id, kit: ["#555", "#ddd"] }) });

// A kit colour that reads on the night background: very dark kits use their second colour.
export function kitColour(id) {
  const [p, s] = club(id).kit;
  return lum(p) < 0.09 ? s : p;
}
export const kitInk = (id) => tint(kitColour(id), 0.35);

// The two clubs' colours for one match. When they are too alike (two orange kits), the away
// club switches to its other kit colour, or to chalk if that is no better.
export function pairColours(home, away) {
  const h = kitColour(home);
  let a = kitColour(away);
  if (dist(h, a) < 90) {
    const [p, s] = club(away).kit;
    const other = a.toLowerCase() === p.toLowerCase() ? s : p;
    a = dist(h, other) >= 90 && lum(other) >= 0.09 ? other : "#ECEAE0";
  }
  return [h, a];
}
export const teamVars = (home, away) => { const [h, a] = pairColours(home, away); return `--h:${h};--a:${a}`; };
function dist(x, y) {
  const c = (hex) => [0, 2, 4].map((i) => parseInt(hex.replace("#", "").slice(i, i + 2), 16));
  const [p, q] = [c(x), c(y)];
  return Math.hypot(p[0] - q[0], p[1] - q[1], p[2] - q[2]);
}
function lum(hex) {
  const h = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function crest(id, cls = "crest") {
  const c = club(id);
  const [p, s] = c.kit;
  const fb = `data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><path d="M32 3 L57 11 L57 32 C57 47 46 56 32 61 C18 56 7 47 7 32 L7 11 Z" fill="${p}" stroke="${s}" stroke-width="3"/><text x="32" y="40" text-anchor="middle" font-family="sans-serif" font-weight="700" font-size="17" fill="${s}">${c.code}</text></svg>`)}`;
  return `<img class="${cls}" src="${esc(c.crest || fb)}" alt="" loading="lazy" onerror="this.onerror=null;this.src='${fb}'">`;
}

export const clubHref = (id) => `#/club/${id}`;
export const playerHref = (id) => `#/player/${id}`;
export const clubLink = (id, label) => `<a class="clublink" href="${clubHref(id)}">${esc(label ?? club(id).name)}</a>`;

export function seasonLabel(s) { return s.replace("-", "–"); }

export const ordinal = (n) => {
  const v = n % 100;
  return `${n}${v >= 11 && v <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th")}`;
};

export function dateLabel(iso, opts = { weekday: "long", day: "numeric", month: "long" }) {
  const d = new Date(`${iso}T12:00:00`);
  return d.toLocaleDateString("en-GB", opts);
}

// W / D / L chips, oldest first, each linking to the match.
export function formChips(form, small = false) {
  return `<span class="form${small ? " sm" : ""}">${form.map((f) => {
    const opp = club(f.opp);
    const title = `${f.r === "W" ? "Won" : f.r === "D" ? "Drew" : "Lost"} ${f.score} ${f.venue === "H" ? "v" : "at"} ${opp.name}`;
    return `<a class="fr ${f.r}" href="#/result/${f.match_id}" title="${esc(title)}" aria-label="${esc(title)}">${f.r}</a>`;
  }).join("")}</span>`;
}

// Win / draw / win bar in the two kit colours.
export function probBar(fx, labels = true) {
  const o = fx.outlook;
  const [h, a] = pairColours(fx.home, fx.away);
  return `<div class="prob" role="img" aria-label="Win chances: ${esc(club(fx.home).name)} ${o.home_win}%, draw ${o.draw}%, ${esc(club(fx.away).name)} ${o.away_win}%">
    <div class="prob-bar">
      <span style="flex:${o.home_win};background:${h}"></span><span class="d" style="flex:${o.draw}"></span><span style="flex:${o.away_win};background:${a}"></span>
    </div>
    ${labels ? `<div class="prob-num"><span><b>${o.home_win}%</b> ${esc(club(fx.home).code)} win</span><span>Draw ${o.draw}%</span><span>${esc(club(fx.away).code)} win <b>${o.away_win}%</b></span></div>` : ""}
  </div>`;
}

export const ZONE_CLASS = {
  "Continental Cup": "z-cup", "Continental Shield": "z-shield", Relegation: "z-down",
  Promotion: "z-up", Playoffs: "z-po",
};
export function zoneClass(z) {
  if (!z) return "";
  for (const [k, v] of Object.entries(ZONE_CLASS)) if (z.toLowerCase().includes(k.toLowerCase())) return v;
  return "";
}

// Fixtures of the current round, in kick-off order.
export function roundFixtures() {
  return [...L.data.fixtures].sort((a, b) => (a.date + a.ko).localeCompare(b.date + b.ko) || a.id.localeCompare(b.id));
}

export function resultsOfRound(season, round) {
  return L.data.season[season].results.filter((r) => r.round === round);
}

// Cumulative points per club after each round (for the race chart).
export function pointsByRound(season) {
  const res = L.data.season[season].results;
  const rounds = Math.max(0, ...res.map((r) => r.round));
  const ids = L.data.season[season].tables["1"].rows.map((r) => r.club);
  const pts = Object.fromEntries(ids.map((id) => [id, Array(rounds + 1).fill(0)]));
  for (const r of res) {
    if (!pts[r.home] || !pts[r.away]) continue;
    const [h, a] = r.hg > r.ag ? [3, 0] : r.hg < r.ag ? [0, 3] : [1, 1];
    pts[r.home][r.round] += h;
    pts[r.away][r.round] += a;
  }
  for (const id of ids) for (let i = 1; i <= rounds; i++) pts[id][i] += pts[id][i - 1];
  return { rounds, pts };
}

export function divisionName(div) { return div === "2" || div === 2 ? "Crown League Two" : "Crown League"; }
