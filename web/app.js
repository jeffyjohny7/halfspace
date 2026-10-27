// Halfspace: the Crown League hub, with the live match (data/match.json) replayed inside it.
import { tint, esc } from "./lib/util.js";
import { L, loadLeague, crest, seasonLabel } from "./lib/league.js";
import { liveState } from "./lib/live.js";
import { renderMatch, tickMatch } from "./views/match.js";
import { renderBefore } from "./views/before.js";
import { renderPlayers, tickPlayers } from "./views/players.js";
import { renderFullTime } from "./views/fulltime.js";
import { renderAsk } from "./views/ask.js";
import { closePlayerCard, tickPlayerCard } from "./views/playercard.js";
import { renderHome } from "./views/home.js";
import { renderMatches, renderFixture, renderResult } from "./views/fixtures.js";
import { renderTable } from "./views/table.js";
import { renderStats } from "./views/stats.js";
import { renderClubs, renderClub } from "./views/clubs.js";
import { renderPeople, renderPerson } from "./views/people.js";
import { renderMe } from "./views/me.js";
import { F, loadFan, pollAlerts, onFanChange, markRead } from "./lib/fan.js";

export const S = {
  data: null,        // the live match (data/match.json)
  clock: 0,          // seconds of play since kick-off
  playing: false,
  speed: 30,         // match seconds per real second
  lens: "casual/en", // the live match's viewer: style/language
  style: "casual",   // casual | analyst, for the whole app
  hubSeason: null,   // the season the league pages show
  view: "home",
  arg: null,
  matchTab: "live",  // live | lineups | stats | commentary (inside the live view)
  keyOnly: false,
  shownCue: null,
  pinnedCue: null,
  pinnedLatest: null,
  why: false,
  playerId: null,
  season: null,      // the player card's season
  thread: [],
};

// view: { render, tick?, nav, season? (shows the season menu), match? (needs the live match) }
const VIEWS = {
  home: { render: renderHome, nav: "home", tick: tickHome },
  matches: { render: renderMatches, nav: "matches", season: true },
  fixture: { render: renderFixture, nav: "matches" },
  result: { render: renderResult, nav: "matches" },
  table: { render: renderTable, nav: "table", season: true },
  stats: { render: renderStats, nav: "stats", season: true },
  clubs: { render: renderClubs, nav: "clubs", season: true },
  club: { render: renderClub, nav: "clubs", season: true },
  players: { render: renderPeople, nav: "players", season: true },
  player: { render: renderPerson, nav: "players" },
  ask: { render: renderAsk, nav: "ask", match: true },
  me: { render: renderMe, nav: "me" },
  "match/before": { render: renderBefore, nav: "matches", match: true },
  "match/live": { render: renderMatch, tick: tickMatch, nav: "matches", match: true },
  "match/ratings": { render: renderPlayers, tick: tickPlayers, nav: "matches", match: true },
  "match/full-time": { render: renderFullTime, nav: "matches", match: true, rerender: true },
};
const MATCH_TABS = [["before", "Before kick-off"], ["live", "Live"], ["ratings", "Ratings"], ["full-time", "Full time"]];

const main = document.getElementById("main");
const bar = document.getElementById("matchbar");

function parse() {
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  let [view = "home", a, b] = parts;
  if (view === "before" || view === "full-time") return ["match/" + view, null];   // old links
  if (view === "match") {
    const tab = MATCH_TABS.some(([k]) => k === a) ? a : "live";
    return [`match/${tab}`, tab === "ratings" ? b || null : null];
  }
  return [VIEWS[view] ? view : "home", a || null];
}

function route() {
  const [view, arg] = parse();
  S.view = view;
  S.arg = arg;
  if (view === "match/ratings") S.playerId = arg;
  else { S.playerId = null; closePlayerCard(); }
  document.querySelectorAll(".tabs a, #melink").forEach((a) =>
    a.setAttribute("aria-current", a.dataset.tab === VIEWS[view].nav ? "page" : "false"));
  document.getElementById("seasonpick").hidden = !VIEWS[view].season;
  render();
  window.scrollTo(0, 0);
}

export function render() {
  const v = VIEWS[S.view];
  if (!L.data || (v.match && !S.data)) {
    main.innerHTML = `<p class="loading">${!L.data ? "Couldn't load the league data (data/league.json). Run <code>uv run scripts/export_league.py</code>, then reload."
      : "Couldn't load the match (data/match.json). Run <code>uv run scripts/export_web.py</code>, then reload."}</p>`;
    return;
  }
  drawMatchBar();
  v.render(main, S, S.arg);
}

// ------------------------------------------------------------------ the match bar (match pages)

function drawMatchBar() {
  const on = S.view.startsWith("match/") && S.data;
  bar.hidden = !on;
  if (!on) return;
  const { home, away } = S.data.match;
  const tab = S.view.split("/")[1];
  bar.innerHTML = `<div class="mbar">
    <a class="mbar-back" href="#/matches">Matchday ${S.data.match.round}</a>
    <div class="mbar-score">
      <span class="mb-team">${crest(home.id, "c")}<b>${esc(home.short)}</b></span>
      <span class="mb-num cond" id="mbscore"></span>
      <span class="mb-team">${crest(away.id, "c")}<b>${esc(away.short)}</b></span>
      <span class="mb-status" id="mbstatus"></span>
      ${tab !== "live" ? `<button class="mb-play" id="mbplay" aria-label="Play"></button>` : ""}
    </div>
    <nav class="mbar-tabs" aria-label="Match">${MATCH_TABS.map(([k, label]) =>
      `<a href="#/match/${k}" aria-current="${k === tab ? "page" : "false"}">${label}</a>`).join("")}</nav>
  </div>`;
  bar.querySelector("#mbplay")?.addEventListener("click", () => {
    if (S.clock >= S.data.match.end) setClock(0);
    S.playing = !S.playing;
    tickBar();
  });
  tickBar();
}

function tickBar() {
  if (!S.data) return;
  const st = liveState(S);
  const dot = document.getElementById("navlive");
  if (dot) dot.hidden = !(st.status === "live" || st.status === "ht");
  if (bar.hidden) return;
  const sc = bar.querySelector("#mbscore");
  if (sc) sc.textContent = `${st.score[0]}–${st.score[1]}`;
  const ss = bar.querySelector("#mbstatus");
  if (ss) { ss.textContent = st.status === "pre" ? "Kick-off 12:30" : st.label; ss.dataset.state = st.status; }
  const pb = bar.querySelector("#mbplay");
  if (pb) { pb.classList.toggle("on", S.playing); pb.setAttribute("aria-label", S.playing ? "Pause" : "Play"); }
}

function tickHome() {
  const st = liveState(S);
  const key = `${st.status}|${st.score}|${st.label}`;
  if (key !== tickHome.k) { tickHome.k = key; renderHome(main, S); }
}

// ------------------------------------------------------------------ clock

export function setClock(c) {
  S.clock = Math.max(0, Math.min(S.data.match.end, c));
  if (S.clock >= S.data.match.end) S.playing = false;
  const v = VIEWS[S.view];
  if (v.tick) v.tick(main, S);
  else if (v.rerender) v.render(main, S, S.arg);
  if (S.view !== "match/ratings") tickPlayerCard();   // a card opened from the line-ups keeps up with the replay
  tickBar();
}

let last = null, lastPoll = 0;
function loop(t) {
  if (last != null && S.playing && S.data) setClock(S.clock + ((t - last) / 1000) * S.speed);
  last = t;
  if (t - lastPoll > 2000) { lastPoll = t; pollAlerts(S); }   // personal alerts, released at the fan's clock
  requestAnimationFrame(loop);
}

// ------------------------------------------------------------------ the fan: name, bell and alert tray

function drawFan() {
  const p = F.profile;
  const init = document.getElementById("meinit");
  if (init) init.textContent = p?.name ? p.name.slice(0, 1).toUpperCase() : "Me";
  const bell = document.getElementById("bell");
  if (bell) bell.hidden = !(F.server && p?.alerts && (p.club || p.players?.length));
  const n = document.getElementById("belln");
  if (n) { n.hidden = !F.unread; n.textContent = F.unread > 9 ? "9+" : String(F.unread); }
  const tray = document.getElementById("tray");
  if (tray && !tray.hidden) drawTray();
}

function drawTray() {
  const tray = document.getElementById("tray");
  const list = [...F.alerts].reverse();
  tray.innerHTML = `<div class="tray-head"><b>Your alerts</b><a href="#/me">My Halfspace</a></div>
    ${list.length ? `<ul>${list.map((a) => `<li class="${esc(a.tone || "neutral")}"><span class="t-min cond">${a.minute ? `${a.minute}′` : "Pre"}</span>
      <span><b lang="${esc(a.lang || "en")}">${esc(a.title)}</b><small lang="${esc(a.lang || "en")}">${esc(a.body)}</small></span></li>`).join("")}</ul>`
      : `<p class="muted">Nothing yet. Alerts arrive as your replay reaches each moment.</p>`}`;
}

function initFan() {
  onFanChange(drawFan);
  const bell = document.getElementById("bell"), tray = document.getElementById("tray");
  bell.addEventListener("click", (e) => {
    e.stopPropagation();
    tray.hidden = !tray.hidden;
    bell.setAttribute("aria-expanded", String(!tray.hidden));
    if (!tray.hidden) { drawTray(); markRead(); document.getElementById("toasts")?.replaceChildren(); }
  });
  document.addEventListener("click", (e) => {
    if (!tray.hidden && !tray.contains(e.target)) { tray.hidden = true; bell.setAttribute("aria-expanded", "false"); }
  });
  loadFan().then(() => { if (S.view === "home" || S.view === "ask") render(); });
}

// ------------------------------------------------------------------ style and season

export function saveLens(lens) {
  S.lens = lens;
  const profile = lens.split("/")[0];
  if (profile === "casual" || profile === "analyst") setStyle(profile, false);
  try { localStorage.setItem("halfspace.lens", lens); } catch { /* private mode */ }
}

function setStyle(style, rerender = true) {
  S.style = style;
  try { localStorage.setItem("halfspace.style", style); } catch { /* private mode */ }
  document.querySelectorAll("[data-hstyle]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.hstyle === style));
  if (!rerender) return;
  // The live match follows: same language, the chosen style if this language has it.
  if (S.data) {
    const lang = S.lens.split("/")[1] || "en";
    if (S.data.viewers.includes(`${style}/${lang}`)) {
      S.lens = `${style}/${lang}`;
      try { localStorage.setItem("halfspace.lens", S.lens); } catch { /* private mode */ }
    }
  }
  render();
}

function initControls() {
  const sel = document.getElementById("season");
  sel.innerHTML = [...L.data.seasons].reverse().map((s) => `<option value="${s}">${esc(seasonLabel(s))}</option>`).join("");
  sel.value = S.hubSeason;
  sel.addEventListener("change", () => { S.hubSeason = sel.value; render(); });
  document.addEventListener("halfspace:season", () => { sel.value = S.hubSeason; });
  document.querySelectorAll("[data-hstyle]").forEach((b) => b.addEventListener("click", () => setStyle(b.dataset.hstyle)));
  document.querySelectorAll("[data-hstyle]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.hstyle === S.style));
}

// ------------------------------------------------------------------ boot

async function boot() {
  const [league, match] = await Promise.allSettled([
    loadLeague(),
    fetch("data/match.json").then((r) => { if (!r.ok) throw new Error(`${r.status}`); return r.json(); }),
  ]);
  if (league.status !== "fulfilled" && match.status !== "fulfilled") {
    main.innerHTML = `<p class="loading">Couldn't load the data. Run <code>uv run scripts/export_web.py</code> and
      <code>uv run scripts/export_league.py</code>, then reload.</p>`;
    return;
  }
  if (match.status === "fulfilled") {
    S.data = match.value;
    const { home, away } = S.data.match;
    const root = document.documentElement.style;
    root.setProperty("--home", home.colour);
    root.setProperty("--away", away.colour);
    root.setProperty("--home-ink", tint(home.colour, 0.35));
    root.setProperty("--away-ink", tint(away.colour, 0.25));
    S.season = Object.keys(Object.values(S.data.players)[0]?.seasons || {}).sort().pop();
  }
  const saved = (k) => { try { return localStorage.getItem(k); } catch { return null; } };
  if (S.data && saved("halfspace.lens") && S.data.viewers.includes(saved("halfspace.lens"))) S.lens = saved("halfspace.lens");
  S.style = saved("halfspace.style") || (S.lens.startsWith("analyst") ? "analyst" : "casual");
  if (L.data) {
    S.hubSeason = L.data.current_season;
    initControls();
  }
  initFan();
  window.addEventListener("hashchange", route);
  route();
  requestAnimationFrame(loop);
}

// For the demo and for tests: jump the replay (halfspace.setClock(3600)) from the console.
window.halfspace = { S, setClock: (c) => setClock(c) };

boot();
