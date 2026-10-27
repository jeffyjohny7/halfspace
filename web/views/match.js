// The live match: scoreboard, the pitch as the stage, graphics, the scout's calls, timeline.
import { S, setClock, saveLens, render } from "../app.js";
import { esc, pct, num, minuteLabel, countUpTo, STATUS_TEXT, KIND_TEXT, LANG_OF, LANG_ORDER, LANG_NAMES, langAttrs,
  crestImg } from "../lib/util.js";
import { pitchMarkings, toScreen } from "../lib/pitch.js";
import { renderTab, tickTab } from "./matchtabs.js";

const TABS = [["live", "Live"], ["lineups", "Line-ups"], ["stats", "Stats"], ["commentary", "Commentary"]];

const SPEEDS = [10, 30, 60];
const LENS_ORDER = ["casual/en", "analyst/en", "club", "player_focus/en", "casual/ml", "casual/hi"];
let ctx = null;   // cached lookups for the current data

export function lensLabel(key) {
  const [profile, lang] = key.split("/");
  const langName = { ml: "മലയാളം", hi: "हिन्दी", ta: "தமிழ்", es: "Español", fr: "Français", pt: "Português", de: "Deutsch", ar: "العربية" }[lang];
  if (profile === "casual") return langName || "Casual";
  if (profile === "analyst") return "Analyst";
  if (profile.startsWith("club:")) return "Supporter";
  if (profile === "player_focus") return langName ? `Player focus, ${langName}` : "Player focus";
  return key;
}

const STYLE_ORDER = ["casual", "analyst", "club", "player_focus"];
const STYLE_NAMES = { casual: "Casual", analyst: "Analyst", club: "Supporter", player_focus: "Player focus" };
const styleOf = (profile) => (profile.startsWith("club:") ? "club" : profile);
const rankIn = (order) => (a, b) => ((order.indexOf(a) + 1 || 99) - (order.indexOf(b) + 1 || 99));

// Language as a menu (five or more languages), style as buttons when the language has more than one.
export function lensPicker(data) {
  const keys = lensKeys(data), [profile, lang] = S.lens.split("/");
  const langs = [...new Set(keys.map((k) => LANG_OF(k)))].sort(rankIn(LANG_ORDER));
  const styles = keys.filter((k) => LANG_OF(k) === lang).map((k) => k.split("/")[0])
    .sort((a, b) => rankIn(STYLE_ORDER)(styleOf(a), styleOf(b)));
  return `<select class="lang-pick" data-lang aria-label="Language">${langs.map((l) =>
      `<option value="${l}" lang="${l}" ${l === lang ? "selected" : ""}>${esc(LANG_NAMES[l] || l)}</option>`).join("")}</select>
    ${styles.length > 1 ? `<div class="styles" role="group" aria-label="Style">${styles.map((p) =>
      `<button class="seg" data-style="${esc(p)}" aria-pressed="${p === profile}">${STYLE_NAMES[styleOf(p)] || esc(p)}</button>`).join("")}</div>` : ""}`;
}

export function bindLensPicker(root, onChange) {
  const keys = lensKeys(S.data);
  root.querySelector("[data-lang]")?.addEventListener("change", (e) => {
    const lang = e.target.value, profile = S.lens.split("/")[0];
    saveLens([`${profile}/${lang}`, `casual/${lang}`].find((k) => keys.includes(k)) || keys.find((k) => LANG_OF(k) === lang));
    onChange();
  });
  root.querySelectorAll("[data-style]").forEach((b) => b.addEventListener("click", () => {
    saveLens(`${b.dataset.style}/${LANG_OF(S.lens)}`);
    onChange();
  }));
}

export function lensKeys(data) {
  const keys = data.viewers.length ? data.viewers : ["casual/en"];
  const rank = (k) => {
    const i = LENS_ORDER.findIndex((o) => k === o || (o === "club" && k.startsWith("club:")));
    return i < 0 ? 99 : i;
  };
  return [...keys].sort((a, b) => rank(a) - rank(b));
}

// The variant to show for a viewer, with the language of its headline (hl) and body (bl):
// a safe template has a translated headline over the English fact line.
export function variantFor(cue, lens) {
  const v = cue.variants, lang = LANG_OF(lens);
  const key = [lens, `casual/${lang}`, "casual/en"].find((k) => v[k]) || Object.keys(v)[0];
  const hl = LANG_OF(key);
  return { ...v[key], hl, bl: v[key].source === "template" ? "en" : hl };
}

function build(data) {
  const ev = data.events;
  const byId = new Map(ev.map((e) => [e[11], e]));
  const shots = ev.filter((e) => e[4] === "shot" || e[4] === "own_goal");
  const located = ev.filter((e) => e[6] != null && !["substitution", "injury", "card"].includes(e[4]));
  const goals = data.moments.filter((m) => m.type === "goal").sort((a, b) => a.clock - b.clock);
  const live = data.cues.filter((c) => c.phase === "live").sort((a, b) => a.clock - b.clock);
  const post = data.cues.filter((c) => c.phase === "postmatch");
  return { data, byId, shots, located, goals, live, post, lastShotCount: -1, lastMinute: -1, lastCueCount: -1, lastScore: "" };
}

function scoreAt(clock) {
  let h = 0, a = 0;
  for (const g of ctx.goals) {
    if (g.clock > clock) break;
    const [x, y] = g.facts.score_after.split("-").map(Number);
    h = x; a = y;
  }
  return [h, a];
}

function stateAt(clock) {
  const tl = ctx.data.timeline;
  const i = countUpTo(tl, clock, (e) => e.c);
  return i ? tl[i - 1] : null;
}

function periodAt(clock) {
  const p1 = ctx.data.match.periods[0];
  return clock > p1.end ? 2 : 1;
}

function clockText(clock) {
  if (clock <= 0) return "Kick-off";
  const end = ctx.data.match.end;
  if (clock >= end) return "Full time";
  const p1 = ctx.data.match.periods[0];
  if (clock >= p1.end && clock < ctx.data.match.periods[1].start) return "Half-time";
  const n = countUpTo(ctx.data.events, clock, (e) => e[0]);
  const minute = n ? ctx.data.events[n - 1][1] : 0;
  return minuteLabel(minute, periodAt(clock));
}

// ------------------------------------------------------------------ render

export function renderMatch(main, S) {
  const d = S.data;
  if (!ctx || ctx.data !== d) ctx = build(d);
  ctx.lastShotCount = -1; ctx.lastMinute = -1; ctx.lastCueCount = -1; ctx.lastScore = "";
  const { home, away } = d.match;
  main.innerHTML = `
    <section class="scoreboard" aria-label="Score">
      <div class="side home">${crestImg(home)}<div><div class="name">${esc(home.name)}</div>
        <div class="sub">${esc(home.formation || "")}${home.position ? `, ${ordinal(home.position)} in the table` : ""}</div></div></div>
      <div class="score" id="score" aria-live="polite"></div>
      <div class="side away">${crestImg(away)}<div><div class="name">${esc(away.name)}</div>
        <div class="sub">${esc(away.formation || "")}${away.position ? `, ${ordinal(away.position)} in the table` : ""}</div></div></div>
    </section>
    <div class="match">
      <div class="stage">
      <nav class="mtabs" role="tablist" aria-label="Match centre">
        ${TABS.map(([k, label]) => `<button role="tab" data-mtab="${k}" aria-selected="${S.matchTab === k}">${label}</button>`).join("")}
      </nav>
      <div class="tab-pane" id="tabpane" ${S.matchTab === "live" ? "hidden" : ""}></div>
      <div class="stage-inner" id="livepane" ${S.matchTab === "live" ? "" : "hidden"}>
        <div class="pitch-wrap">
          <svg class="pitch" viewBox="-2 -1.5 109 71" role="img" aria-label="Pitch with shots so far. ${esc(home.name)} attack to the right.">
            ${pitchMarkings()}
            <text class="dir" x="1.6" y="3.4">${esc(home.short)} attack →</text>
            <text class="dir" x="103.4" y="3.4" text-anchor="end">← ${esc(away.short)} attack</text>
            <g id="shots"></g>
            <polyline id="trail" class="trail" points=""/>
            <circle id="ball" class="ball" r="0.85" cx="52.5" cy="34"/>
            <g id="rings"></g>
          </svg>
        </div>
        <div class="graphic-slot" id="gslot"></div>
        <div class="legend">
          <span><i style="background:var(--home)"></i>${esc(home.short)} shot</span>
          <span><i style="background:var(--away)"></i>${esc(away.short)} shot</span>
          <span><i class="hollow" style="color:var(--chalk)"></i>Goal (ringed)</span>
          <span>Bigger dot, better chance</span>
        </div>
      </div></div>
      <aside class="rail">
        <section><h2>The scout's calls <small>checked live</small></h2><ul class="calls" id="calls"></ul></section>
        <section><h2>Match numbers</h2><div class="bars" id="bars"></div></section>
        <section><h2>Shown so far <small>tap to see again</small></h2><ul class="feed" id="feed"></ul></section>
      </aside>
    </div>
    <div class="controls">
      <div class="controls-row">
        <button class="play" id="play" aria-label="Play"></button>
        <div class="speed" role="group" aria-label="Replay speed">
          ${SPEEDS.map((s) => `<button class="seg" data-speed="${s}" aria-pressed="${S.speed === s}">${s}×</button>`).join("")}
        </div>
        <div class="timeline" id="timeline"></div>
        <div class="viewas"><span>View as</span><span class="lens" id="lens">${lensPicker(d)}</span></div>
      </div>
    </div>`;

  main.querySelector("#play").addEventListener("click", () => {
    if (S.clock >= d.match.end) setClock(0);
    S.playing = !S.playing;
    drawPlay(main);
  });
  main.querySelectorAll("[data-speed]").forEach((b) => b.addEventListener("click", () => {
    S.speed = Number(b.dataset.speed);
    main.querySelectorAll("[data-speed]").forEach((x) => x.setAttribute("aria-pressed", x === b));
  }));
  const lensEl = main.querySelector("#lens");
  const onLens = () => {
    lensEl.innerHTML = lensPicker(d);
    bindLensPicker(lensEl, onLens);
    ctx.lastCueCount = -1;
    drawGraphic(main, true);
    drawFeed(main);
  };
  bindLensPicker(lensEl, onLens);
  main.querySelectorAll("[data-mtab]").forEach((b) => b.addEventListener("click", () => {
    S.matchTab = b.dataset.mtab;
    main.querySelectorAll("[data-mtab]").forEach((x) => x.setAttribute("aria-selected", x === b));
    main.querySelector("#livepane").hidden = S.matchTab !== "live";
    const pane = main.querySelector("#tabpane");
    pane.hidden = S.matchTab === "live";
    if (S.matchTab === "live") { ctx.lastShotCount = -1; ctx.lastCueCount = -1; tickMatch(main, S); }
    else renderTab(S.matchTab, pane, variantFor);
  }));
  if (S.matchTab !== "live") renderTab(S.matchTab, main.querySelector("#tabpane"), variantFor);
  drawTimeline(main);
  drawPlay(main);
  S.shownCue = null;
  tickMatch(main, S);
}

function ordinal(n) {
  const s = ["th", "st", "nd", "rd"], v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

function drawPlay(main) {
  const b = main.querySelector("#play");
  if (!b) return;
  b.innerHTML = S.playing
    ? '<svg viewBox="0 0 16 16"><rect x="3" y="2" width="3.5" height="12"/><rect x="9.5" y="2" width="3.5" height="12"/></svg>'
    : '<svg viewBox="0 0 16 16"><path d="M4 2 L14 8 L4 14 Z"/></svg>';
  b.setAttribute("aria-label", S.playing ? "Pause" : "Play");
}

// ------------------------------------------------------------------ tick

export function tickMatch(main, S) {
  if (!ctx) return;
  const d = S.data, clock = S.clock;
  const st = stateAt(clock);
  const [h, a] = scoreAt(clock);
  const scoreEl = main.querySelector("#score");
  if (!scoreEl) return;
  const key = `${h}-${a}`;
  const xg = st ? st.xg : [0, 0];
  scoreEl.innerHTML = `<div class="goals cond"><span>${h}</span><span class="dash">–</span><span>${a}</span></div>
    <div class="clock"><b>${clockText(clock)}</b></div>
    <div class="xg">xG ${num(xg[0])} – ${num(xg[1])}</div>`;
  if (ctx.lastScore && key !== ctx.lastScore) {
    scoreEl.classList.remove("goal-flash"); void scoreEl.offsetWidth; scoreEl.classList.add("goal-flash");
  }
  ctx.lastScore = key;

  if (S.matchTab === "live") { drawPitch(main, clock); drawGraphic(main, false); }
  else tickTab(S.matchTab, main.querySelector("#tabpane"), variantFor);
  const minute = st ? st.m : 0;
  if (minute !== ctx.lastMinute) { drawCalls(main, minute); drawBars(main, st); ctx.lastMinute = minute; }
  drawFeed(main);
  drawHead(main);
  drawPlay(main);
}

function drawPitch(main, clock) {
  const shots = ctx.shots.slice(0, countUpTo(ctx.shots, clock, (e) => e[0]));
  if (shots.length !== ctx.lastShotCount) {
    ctx.lastShotCount = shots.length;
    main.querySelector("#shots").innerHTML = shots.map((e) => {
      const team = e[4] === "own_goal" ? 1 - e[2] : e[2];
      const p = e[4] === "own_goal" ? toScreen(e[2], 105 - e[6], 68 - e[7]) : toScreen(e[2], e[6], e[7]);
      if (!p) return "";
      const goal = e[5] === "goal" || e[4] === "own_goal";
      const r = 0.7 + Math.sqrt(e[10] || 0.05) * 2.4;
      const col = team === 0 ? "var(--home)" : "var(--away)";
      return `<circle class="shot${goal ? " goal" : ""}" cx="${p[0]}" cy="${p[1]}" r="${r.toFixed(2)}"
        fill="${goal ? col : "none"}" stroke="${goal ? "var(--chalk)" : col}" ${goal ? "" : 'fill-opacity="0"'}>
        <title>${e[1]}′ ${goal ? "goal" : e[5] || "shot"}, ${num(e[10])} xG</title></circle>`;
    }).join("");
  }
  const n = countUpTo(ctx.located, clock, (e) => e[0]);
  const recent = ctx.located.slice(Math.max(0, n - 7), n);
  const pts = recent.map((e) => toScreen(e[2], e[6], e[7])).filter(Boolean);
  main.querySelector("#trail").setAttribute("points", pts.map((p) => p.join(",")).join(" "));
  const ball = main.querySelector("#ball");
  const lastP = pts[pts.length - 1];
  if (lastP) { ball.setAttribute("cx", lastP[0]); ball.setAttribute("cy", lastP[1]); }
  ball.style.opacity = clock > 0 && clock < S.data.match.end ? 1 : 0;
}

function currentCue(clock) {
  const n = countUpTo(ctx.live, clock, (c) => c.clock);
  if (clock >= S.data.match.end && ctx.post.length) return ctx.post[0];
  return n ? ctx.live[n - 1] : null;
}

function drawGraphic(main, force) {
  const slot = main.querySelector("#gslot");
  const latest = currentCue(S.clock);
  if (S.pinnedCue && latest !== S.pinnedLatest) S.pinnedCue = null;   // a newer graphic arrived
  const cue = S.pinnedCue || latest;
  if (!force && cue === S.shownCue && slot.childElementCount) return;
  const isNew = cue !== S.shownCue;
  S.shownCue = cue;
  if (isNew) S.why = false;
  if (!cue) {
    slot.innerHTML = S.clock <= 0
      ? `<div class="graphic-empty">Press play to start the match. The scout's calls on the right are checked as it happens.</div>`
      : `<div class="graphic-empty">Nothing worth interrupting the match for yet.</div>`;
    return;
  }
  const v = variantFor(cue, S.lens);
  const team = cue.overlay?.data?.team;
  const teamVar = team === S.data.match.home.name ? "var(--home)" : team === S.data.match.away.name ? "var(--away)" : "var(--turf-0)";
  const when = cue.phase === "postmatch" ? "Full time" : `${minuteLabel(cue.minute, cue.clock > S.data.match.periods[0].end ? 2 : 1)}`;
  const kind = KIND_TEXT[cue.kind] || "Update";
  const rejected = cue.checked.rejected;
  slot.innerHTML = `<article class="graphic" style="--team:${teamVar}" ${isNew ? "" : 'data-still="1"'}>
      <div class="kicker"><span>${esc(when)}</span><span>${esc(kind)}</span>
        <button class="checked" id="why" aria-expanded="${S.why}">
          <svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M4.5 8.2 L7 10.5 L11.5 5.5" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>
          Checked</button></div>
      <h3 ${langAttrs(v.hl)}>${esc(v.headline)}</h3>
      <p ${langAttrs(v.bl)}>${esc(v.body)}</p>
      ${S.why ? `<div class="why">Written from the match data below; every number and name on this graphic was checked against it${
        rejected ? `, and ${rejected} draft${rejected > 1 ? "s were" : " was"} sent back before this one` : ""}${v.source === "template" ? ". This is the plain version, used when a written one didn't pass" : ""}.
        <ul>${cue.facts.map((f) => `<li>${esc(f)}</li>`).join("")}</ul></div>` : ""}
    </article>
    ${S.clock >= S.data.match.end ? `<div class="cta-row"><a class="btn" href="#/match/full-time">See full time</a></div>` : ""}`;
  if (!isNew) slot.querySelector(".graphic").style.animation = "none";
  slot.querySelector("#why").addEventListener("click", () => { S.why = !S.why; drawGraphic(main, true); });
  if (isNew) drawRing(main, cue);
}

function drawRing(main, cue) {
  const g = main.querySelector("#rings");
  g.innerHTML = "";
  const e = (cue.refs || []).map((id) => ctx.byId.get(id)).find((x) => x && x[6] != null);
  if (!e) return;
  const p = e[4] === "own_goal" ? toScreen(e[2], 105 - e[6], 68 - e[7]) : toScreen(e[2], e[6], e[7]);
  g.innerHTML = `<circle class="ring" cx="${p[0]}" cy="${p[1]}" r="4.2"/>`;
}

function predictionNow(p, minute) {
  let cur = null;
  for (const row of p.timeline) { if (row[0] > minute) break; cur = row; }
  return cur || [0, 0, "too early"];
}

function fmtValue(p, v) {
  if (v == null) return "–";
  if (p.kind === "rate_at_most") return pct(v);
  if (p.measure.includes("xg")) return num(v);
  return String(Math.round(v));
}

function callTitle(p) {
  return p.subject_type === "player" ? p.label : `${p.subject}: ${p.label}`;
}

function drawCalls(main, minute) {
  const list = main.querySelector("#calls");
  const preds = S.data.predictions;
  if (!preds.length) { list.innerHTML = `<li class="call"><span></span><div class="what">No live checks for this match.</div></li>`; return; }
  list.innerHTML = preds.map((p) => {
    const [, value, status] = predictionNow(p, minute);
    const cls = status === "confirmed" ? "yes" : ["did not happen", "not happening"].includes(status) ? "no" : status === "on track" ? "on" : "";
    const expected = p.kind === "rate_at_most"
      ? `Expected ${pct(p.expected)} against ${pct(p.average)} for an average player. Confirmed at ${pct(p.confirm_at)} or lower.`
      : `Expected ${fmtValue(p, p.expected)} against a league average of ${fmtValue(p, p.average)}. Confirmed at ${fmtValue(p, p.confirm_at)}.`;
    let meter = "";
    if (p.kind !== "rate_at_most" && p.confirm_at) {
      const scale = Math.max(p.confirm_at * 1.3, value || 0);
      meter = `<div class="meter" aria-hidden="true"><span style="width:${Math.min(100, ((value || 0) / scale) * 100)}%"></span>
        <i style="left:${(p.confirm_at / scale) * 100}%"></i></div>`;
    }
    const mark = cls === "yes"
      ? `<svg class="mark" viewBox="0 0 22 22"><circle cx="11" cy="11" r="9"/><path d="M6.5 11.3 L9.6 14.2 L15.5 7.8"/></svg>`
      : cls === "no" ? `<svg class="mark" viewBox="0 0 22 22"><circle cx="11" cy="11" r="9"/><path d="M7 15 L15 7"/></svg>`
      : `<svg class="mark" viewBox="0 0 22 22"><circle cx="11" cy="11" r="9"/></svg>`;
    return `<li class="call ${cls}">${mark}<div>
      <div class="what">${esc(callTitle(p))}</div>
      <div class="status">${minute ? `Now ${fmtValue(p, value)}. ` : ""}${esc(STATUS_TEXT[status] || status)}</div>
      ${meter}
      <details><summary class="status">What the scout expected</summary><div class="status">${esc(expected)}</div></details>
    </div></li>`;
  }).join("");
}

function drawBars(main, st) {
  const el = main.querySelector("#bars");
  const z = st || { pos: [0.5, 0.5], sh: [0, 0], sot: [0, 0], xg: [0, 0], corners: [0, 0], t10: [0.5, 0.5] };
  const row = (label, hv, av, hText, aText) => {
    const tot = hv + av || 1;
    return `<div class="bar-row"><div class="label">${label}</div>
      <div class="v" style="color:var(--home-ink)">${hText}</div>
      <div class="split"><span style="flex-grow:${hv / tot};background:var(--home)"></span><span style="flex-grow:${av / tot};background:var(--away)"></span></div>
      <div class="v r" style="color:var(--away-ink)">${aText}</div></div>`;
  };
  el.innerHTML = [
    row("Possession", z.pos[0], z.pos[1], pct(z.pos[0]), pct(z.pos[1])),
    row("Chance quality (xG)", z.xg[0], z.xg[1], num(z.xg[0]), num(z.xg[1])),
    row("Shots (on target)", z.sh[0], z.sh[1], `${z.sh[0]} (${z.sot[0]})`, `${z.sh[1]} (${z.sot[1]})`),
    row("Play in the final third, last 10 min", z.t10[0], z.t10[1], pct(z.t10[0]), pct(z.t10[1])),
    row("Corners", z.corners[0], z.corners[1], z.corners[0], z.corners[1]),
  ].join("");
}

function drawFeed(main) {
  const el = main.querySelector("#feed");
  const n = countUpTo(ctx.live, S.clock, (c) => c.clock);
  if (n === ctx.lastCueCount) return;
  ctx.lastCueCount = n;
  const items = ctx.live.slice(0, n).reverse();
  el.innerHTML = items.length ? items.map((c) => {
    const v = variantFor(c, S.lens);
    return `<li><span class="min">${minuteLabel(c.minute, c.clock > S.data.match.periods[0].end ? 2 : 1)}</span>
      <button data-cue="${esc(c.id)}"><div class="h" ${langAttrs(v.hl)}>${esc(v.headline)}</div><div class="b" ${langAttrs(v.bl)}>${esc(v.body)}</div></button></li>`;
  }).join("") : `<li><span></span><span class="b">Graphics appear here as the match goes on.</span></li>`;
  el.querySelectorAll("[data-cue]").forEach((b) => b.addEventListener("click", () => {
    pinCue(main, ctx.live.find((c) => c.id === b.dataset.cue));
  }));
}

function pinCue(main, cue) {
  if (S.matchTab !== "live") main.querySelector('[data-mtab="live"]')?.click();   // graphics live on the pitch
  S.pinnedCue = cue;
  S.pinnedLatest = currentCue(S.clock);
  S.shownCue = null;                     // so it animates in again
  drawGraphic(main, true);
  main.querySelector("#gslot").scrollIntoView({ block: "nearest", behavior: "smooth" });
}

// ------------------------------------------------------------------ timeline

function drawTimeline(main) {
  const d = S.data, end = d.match.end, el = main.querySelector("#timeline");
  const x = (c) => (c / end) * 1000;
  const p1 = d.match.periods[0];
  const maxNet = Math.max(0.05, ...d.momentum.map((m) => Math.abs(m.net)));
  // Momentum blocks are 5 minutes of play; place them by their start clock.
  const blocks = d.momentum.map((m, i) => {
    const c0 = i * 300, w = Math.min(300, end - c0);
    const hgt = (Math.abs(m.net) / maxNet) * 14;
    const y = m.net >= 0 ? 22 - hgt : 22;
    return `<rect class="${m.net >= 0 ? "mom-h" : "mom-a"}" x="${x(c0) + 1}" y="${y}" width="${Math.max(1, x(w) - 2)}" height="${hgt}"
      fill="${m.net >= 0 ? "var(--home)" : "var(--away)"}"/>`;
  }).join("");
  const marks = d.moments.filter((m) => ["goal", "red_card", "injury"].includes(m.type)).map((m) => {
    const cx = x(m.clock);
    const col = m.team === 0 ? "var(--home)" : "var(--away)";
    if (m.type === "goal") return `<circle cx="${cx}" cy="44" r="4.5" fill="${col}" stroke="var(--chalk)" stroke-width="1.2"><title>${m.minute}′ goal, ${esc(m.facts.scorer)}</title></circle>`;
    if (m.type === "red_card") return `<rect x="${cx - 2.5}" y="39" width="5" height="8" fill="#E5484D"><title>${m.minute}′ red card</title></rect>`;
    return `<path d="M${cx - 3} 44 h6 M${cx} 41 v6" stroke="${col}" stroke-width="1.6"><title>${m.minute}′ injury, ${esc(m.facts.player)}</title></path>`;
  }).join("");
  el.innerHTML = `<svg viewBox="0 0 1000 54" preserveAspectRatio="none" aria-hidden="true">
      ${blocks}
      <line class="base" x1="0" y1="22" x2="1000" y2="22"/>
      <line class="played" id="played" x1="0" y1="22" x2="0" y2="22"/>
      <line class="ht" x1="${x(p1.end)}" y1="4" x2="${x(p1.end)}" y2="50"/>
      ${marks}
      <rect class="head" id="head" x="0" y="2" width="2.5" height="40"/>
    </svg>
    <input type="range" min="0" max="${end}" step="1" value="${S.clock}" aria-label="Match time">`;
  const input = el.querySelector("input");
  input.addEventListener("input", () => { S.pinnedCue = null; setClock(Number(input.value)); });
}

function drawHead(main) {
  const el = main.querySelector("#timeline");
  if (!el) return;
  const xx = (S.clock / S.data.match.end) * 1000;
  el.querySelector("#head")?.setAttribute("x", Math.max(0, xx - 1.2));
  el.querySelector("#played")?.setAttribute("x2", xx);
  const input = el.querySelector("input");
  if (input && document.activeElement !== input) input.value = S.clock;
  input?.setAttribute("aria-valuetext", clockText(S.clock));
}

export { render };
