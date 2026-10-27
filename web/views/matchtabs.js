// Match centre tabs beside the live pitch: Line-ups, Stats and Commentary. Each one follows the
// replay clock. Player tokens and rows open the player card.
import { S } from "../app.js";
import { esc, num, pct, minuteLabel, countUpTo, KIND_TEXT, langAttrs } from "../lib/util.js";
import { pitchMarkings } from "../lib/pitch.js";
import { ratingAt, ratingBand, fmtRating } from "../lib/rating.js";
import { openPlayerCard } from "./playercard.js";

// Where each line-up slot stands: depth along the pitch (% of its length from its own goal)
// and lateral position (% from its left touchline to its right).
const SLOT = {
  GK: [5, 50], RB: [17, 85], RWB: [22, 88], RCB: [14, 63], CB: [14, 50], LCB: [14, 37], LB: [17, 15], LWB: [22, 12],
  DM: [24, 50], RDM: [24, 62], LDM: [24, 38], RCM: [31, 66], CM: [31, 50], LCM: [31, 34], RM: [36, 86], LM: [36, 14],
  AM: [37, 50], RAM: [37, 66], LAM: [37, 34], RW: [39, 84], LW: [39, 16], ST: [43, 50], RS: [43, 62], LS: [43, 38],
};

const surname = (n) => n.split(" ").slice(-1)[0];
const periodOf = (clock) => (clock > S.data.match.periods[0].end ? 2 : 1);
const minLabel = (m) => minuteLabel(m.minute, periodOf(m.clock));

function playerIdByName(name) {
  for (const side of ["home", "away"]) {
    const p = S.data.lineups[side].find((x) => x.name === name);
    if (p) return p.id;
  }
  return null;
}

// Goals, cards and substitutions per player up to the clock.
function marksUpTo(clock) {
  const m = {};
  const add = (pid, k, v) => { if (!pid) return; (m[pid] ||= { goals: 0, yellow: 0, red: false })[k] = v(m[pid][k]); };
  for (const x of S.data.moments) {
    if (x.clock > clock) continue;
    if (x.type === "goal" && !x.facts.own_goal) add(playerIdByName(x.facts.scorer), "goals", (v) => v + 1);
    if (x.type === "yellow_card") add(playerIdByName(x.facts.player), "yellow", (v) => v + 1);
    if (x.type === "red_card") add(playerIdByName(x.facts.player), "red", () => true);
    if (x.type === "substitution") {
      add(playerIdByName(x.facts.off), "off", () => minLabel(x));
      add(playerIdByName(x.facts.on), "on", () => minLabel(x));
    }
  }
  return m;
}

const ball = '<svg class="ic" viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="5" fill="#fff" stroke="#111" stroke-width="1"/><path d="M6 3.2 L8.4 5 L7.5 7.8 L4.5 7.8 L3.6 5 Z" fill="#111"/></svg>';
const card = (red) => `<span class="ic card ${red ? "red" : "yellow"}" aria-label="${red ? "red" : "yellow"} card"></span>`;

function token(p, side, mk) {
  const [depth, lat] = SLOT[p.slot] || SLOT[p.pos] || [30, 50];
  // Wide screens: home attacks to the right. Phones: the pitch stands up and home attacks upwards.
  const x = side === "home" ? depth : 100 - depth, y = side === "home" ? lat : 100 - lat;
  const vx = side === "home" ? lat : 100 - lat, vy = side === "home" ? 100 - depth : depth;
  const sheet = S.data.players[p.id];
  const rt = ratingAt(p.id);
  const m = mk[p.id] || {};
  return `<button class="tok ${side}" data-pid="${p.id}" style="--x:${x}%;--y:${y}%;--vx:${vx}%;--vy:${vy}%" aria-label="${esc(p.name)}, open player card">
    <span class="face">${sheet?.photo ? `<img src="${esc(sheet.photo)}" alt="" loading="lazy">` : `<b>${sheet?.num ?? ""}</b>`}
      ${rt ? `<span class="rt ${ratingBand(rt.value)}">${fmtRating(rt.value)}</span>` : ""}
      ${m.goals ? `<span class="goals">${ball}${m.goals > 1 ? `<i>${m.goals}</i>` : ""}</span>` : ""}
      ${m.red ? card(true) : m.yellow ? card(false) : ""}</span>
    <span class="lbl"><i>${sheet?.num ?? ""}</i> ${esc(surname(p.name))}</span>
    ${m.off ? `<span class="sub off">▼ ${m.off}</span>` : ""}
  </button>`;
}

function benchRow(p, mk) {
  const sheet = S.data.players[p.id], rt = ratingAt(p.id), m = mk[p.id] || {};
  return `<button class="brow" data-pid="${p.id}">
    <span class="face sm">${sheet?.photo ? `<img src="${esc(sheet.photo)}" alt="" loading="lazy">` : ""}</span>
    <span class="who"><b>${esc(p.name)}</b><small>${sheet?.num ?? ""} ${esc(p.pos || "")}</small></span>
    <span class="when">${m.on ? `<span class="sub on">▲ ${m.on}</span>` : `<span class="muted">Not on yet</span>`}</span>
    <span class="rt ${rt ? ratingBand(rt.value) : "none"}">${rt ? fmtRating(rt.value) : ""}</span>
  </button>`;
}

function lineupsHTML() {
  const d = S.data, mk = marksUpTo(S.clock);
  const { home, away } = d.match;
  const xi = (side) => d.lineups[side].filter((p) => p.start).map((p) => token(p, side, mk)).join("");
  const bench = (side) => d.lineups[side].filter((p) => !p.start).map((p) => benchRow(p, mk)).join("");
  return `<div class="lu-head">
      <span><b style="color:var(--home-ink)">${esc(home.name)}</b> ${esc(home.formation || "")}</span>
      <span><b style="color:var(--away-ink)">${esc(away.name)}</b> ${esc(away.formation || "")}</span></div>
    <div class="lu-pitch"><svg class="pitch wide" viewBox="0 0 105 68" preserveAspectRatio="none" aria-hidden="true">${pitchMarkings()}</svg>
      <svg class="pitch tall" viewBox="0 0 68 105" preserveAspectRatio="none" aria-hidden="true"><g transform="translate(68 0) rotate(90)">${pitchMarkings()}</g></svg>
      ${xi("home")}${xi("away")}</div>
    <div class="lu-bench"><div><h3>${esc(home.short)} substitutes</h3>${bench("home") || '<p class="muted">None used.</p>'}
      <p class="mgr">Manager: ${esc(home.manager || "")}</p></div>
      <div><h3>${esc(away.short)} substitutes</h3>${bench("away") || '<p class="muted">None used.</p>'}
      <p class="mgr">Manager: ${esc(away.manager || "")}</p></div></div>`;
}

// Stats

function stateAt(clock) {
  const tl = S.data.timeline, i = countUpTo(tl, clock, (e) => e.c);
  return i ? tl[i - 1] : null;
}

function momentumSVG() {
  const d = S.data, end = d.match.end, nowMin = (stateAt(S.clock) || { m: 0 }).m;
  const pts = d.momentum.filter((m) => m.m <= nowMin);
  const maxM = Math.max(95, ...d.momentum.map((m) => m.m + 5));
  const peak = Math.max(0.3, ...d.momentum.map((m) => Math.abs(m.net)));
  const X = (m) => (m / maxM) * 1000, Y = (v) => 60 - (v / peak) * 48;
  let path = "";
  if (pts.length > 1) {
    const p = pts.map((m) => [X(m.m + 2.5), Y(m.net)]);
    path = `M ${X(0)} 60 L ${p[0][0]} ${p[0][1]}`;
    for (let i = 1; i < p.length; i++) {
      const [x0, y0] = p[i - 1], [x1, y1] = p[i], cx = (x0 + x1) / 2;
      path += ` C ${cx} ${y0}, ${cx} ${y1}, ${x1} ${y1}`;
    }
    path += ` L ${p[p.length - 1][0]} 60 Z`;
  }
  const htMin = d.match.periods[0].end_minute;
  const goals = d.moments.filter((m) => m.type === "goal" && m.clock <= S.clock).map((m) =>
    `<g transform="translate(${X(m.minute)}, ${m.team === 0 ? 6 : 114})">${ball.replace('class="ic"', 'width="14" height="14" x="-7" y="-7"')}</g>`).join("");
  return `<svg class="mom" viewBox="0 0 1000 120" aria-label="Momentum: above the line ${esc(d.match.home.name)}, below ${esc(d.match.away.name)}">
    <defs><clipPath id="up"><rect x="0" y="0" width="1000" height="60"/></clipPath><clipPath id="dn"><rect x="0" y="60" width="1000" height="60"/></clipPath></defs>
    ${path ? `<path d="${path}" fill="var(--home)" clip-path="url(#up)" opacity="0.9"/><path d="${path}" fill="var(--away)" clip-path="url(#dn)" opacity="0.9"/>` : ""}
    <line x1="0" y1="60" x2="1000" y2="60" stroke="var(--line)"/>
    <line x1="${X(htMin)}" y1="10" x2="${X(htMin)}" y2="110" stroke="var(--chalk-3)" stroke-dasharray="3 3"/>
    ${goals}</svg>
    <div class="mom-axis"><span>Kick-off</span><span style="left:${(htMin / maxM) * 100}%">Half-time</span><span class="end">Full time</span></div>`;
}

function statRow(label, v, fmt = (x) => x) {
  const [h, a] = v, lead = h === a ? -1 : h > a ? 0 : 1;
  return `<div class="srow"><b class="${lead === 0 ? "lead home" : ""}">${fmt(h)}</b><span>${label}</span><b class="${lead === 1 ? "lead away" : ""}">${fmt(a)}</b></div>`;
}

function statsHTML() {
  const st = stateAt(S.clock);
  if (!st) return `<p class="muted pad">Stats appear once the match starts.</p>`;
  const top = (side) => S.data.lineups[side].map((p) => ({ p, rt: ratingAt(p.id) })).filter((x) => x.rt)
    .sort((a, b) => b.rt.value - a.rt.value).slice(0, 3);
  const rated = (side) => top(side).map(({ p, rt }) => `<button class="brow" data-pid="${p.id}">
      <span class="face sm">${S.data.players[p.id]?.photo ? `<img src="${esc(S.data.players[p.id].photo)}" alt="">` : ""}</span>
      <span class="who"><b>${esc(p.name)}</b><small>${esc(rt.reasons[0]?.label || "")}${rt.reasons[0]?.count > 1 ? ` ×${rt.reasons[0].count}` : ""}</small></span>
      <span></span><span class="rt ${ratingBand(rt.value)}">${fmtRating(rt.value)}</span></button>`).join("");
  return `<section class="sbox"><h3>Momentum</h3>${momentumSVG()}</section>
    <section class="sbox"><h3>Top stats</h3>
      <div class="poss"><span style="flex-grow:${st.pos[0]};background:var(--home)">${pct(st.pos[0])}</span>
        <span style="flex-grow:${st.pos[1]};background:var(--away)">${pct(st.pos[1])}</span></div>
      <p class="muted cap">Possession</p>
      ${statRow("Chance quality (xG)", st.xg, (x) => num(x))}${statRow("Shots", st.sh)}${statRow("Shots on target", st.sot)}
      ${statRow("Corners", st.corners)}${statRow("Passes", st.pass)}${statRow("Play in the final third", st.tilt, (x) => pct(x))}
      ${statRow("Fouls", st.fouls)}${statRow("Cards", st.cards)}</section>
    <section class="sbox"><h3>Best rated so far</h3><div class="rated2"><div>${rated("home")}</div><div>${rated("away")}</div></div></section>`;
}

// Commentary

const SHOT = { saved: "Attempt saved", off_target: "Attempt missed", blocked: "Attempt blocked" };

function commentaryItems() {
  const d = S.data, items = [], names = d.players_order.map((id) => d.players[id]?.name ||
    [...d.lineups.home, ...d.lineups.away].find((x) => x.id === id)?.name || "A player");
  const team = (t) => d.match[t === 0 ? "home" : "away"].name;
  const goalClocks = new Set(d.moments.filter((m) => m.type === "goal").map((m) => Math.round(m.clock)));
  const n = countUpTo(d.events, S.clock, (e) => e[0]);
  for (let i = 0; i < n; i++) {
    const e = d.events[i], who = names[e[3]] || "", tm = team(e[2]);
    const at = { clock: e[0], minute: e[1] };
    if (e[4] === "shot" && e[5] !== "goal" && !goalClocks.has(Math.round(e[0]))) {
      const big = (e[10] || 0) >= 0.3;
      items.push({ ...at, key: big, title: SHOT[e[5]] || "Attempt", text: `${who} (${tm}) ${e[5] === "saved" ? "has his shot saved" : e[5] === "blocked" ? "has his shot blocked" : "shoots wide"}${big ? `: a big chance, ${num(e[10])} xG` : ""}.` });
    } else if (e[4] === "foul") items.push({ ...at, key: false, text: `Foul by ${who} (${tm}).` });
    else if (e[4] === "offside") items.push({ ...at, key: false, text: `Offside, ${tm}. ${who} is caught offside.` });
  }
  for (const m of d.moments) {
    if (m.clock > S.clock) continue;
    const tm = team(m.team), f = m.facts;
    if (m.type === "goal") {
      const how = { left_foot: "left-footed shot", right_foot: "right-footed shot", head: "header" }[f.body_part] || "shot";
      items.push({ clock: m.clock, minute: m.minute, key: true, cls: "goal", title: `Goal! ${f.score_after.replace("-", " – ")}`,
        text: `${f.scorer} (${tm}) scores with a ${how}${f.assist ? `, set up by ${f.assist}` : ""}.${f.context ? ` ${f.context[0].toUpperCase() + f.context.slice(1)}.` : ""}` });
    } else if (m.type === "yellow_card" || m.type === "red_card") {
      items.push({ clock: m.clock, minute: m.minute, key: true, cls: m.type, title: m.type === "red_card" ? "Red card" : "Yellow card",
        text: `${f.player} (${tm}) is shown the ${m.type === "red_card" ? "red" : "yellow"} card.` });
    } else if (m.type === "substitution") {
      items.push({ clock: m.clock, minute: m.minute, key: true, cls: "sub", title: `Substitution, ${tm}`, text: `${f.on} replaces ${f.off}.` });
    } else if (m.type === "injury") {
      items.push({ clock: m.clock, minute: m.minute, key: true, title: "Injury", text: `${f.player} (${tm}) is hurt${f.replaced_by ? ` and is replaced by ${f.replaced_by}` : ""}.` });
    }
  }
  // Corners: from the running count in the timeline.
  const tl = d.timeline;
  for (let i = 1; i < tl.length && tl[i].c <= S.clock; i++) {
    for (const t of [0, 1]) if (tl[i].corners[t] > tl[i - 1].corners[t]) items.push({ clock: tl[i].c - 1, minute: tl[i].m, key: false, text: `Corner, ${team(t)}.` });
  }
  // The broadcast team's graphics, as shown to this viewer.
  for (const c of d.cues) {
    if (c.phase !== "live" || c.clock > S.clock) continue;
    items.push({ clock: c.clock + 0.5, minute: c.minute, key: ["goal", "red_card", "prediction_confirmed", "half_time", "full_time"].includes(c.kind), cue: c });
  }
  const p1 = d.match.periods[0];
  if (S.clock > 0) items.push({ clock: 0, minute: 0, key: true, title: "Kick-off", text: `${d.match.home.name} against ${d.match.away.name} is under way.` });
  if (S.clock >= p1.end) items.push({ clock: p1.end, minute: p1.end_minute, key: true, title: "Half-time", text: "End of the first half." });
  if (S.clock >= d.match.end) items.push({ clock: d.match.end, minute: d.match.periods[1].end_minute, key: true, title: "Full time", text: "The final whistle." });
  return items.sort((a, b) => b.clock - a.clock);
}

function commentaryHTML(variantFor) {
  const all = commentaryItems().filter((x) => !S.keyOnly || x.key);
  if (!all.length) return `<p class="muted pad">Commentary starts at kick-off.</p>`;
  return `<ol class="comm">${all.map((x) => {
    const ml = minuteLabel(x.minute, periodOf(x.clock));
    if (x.cue) {
      const v = variantFor(x.cue, S.lens);
      return `<li class="gfx"><span class="m">${ml}</span><div><div class="t">${esc(KIND_TEXT[x.cue.kind] || "Graphic")}<span class="chk">Checked graphic</span></div>
        <b ${langAttrs(v.hl)}>${esc(v.headline)}</b><p ${langAttrs(v.bl)}>${esc(v.body)}</p></div></li>`;
    }
    return `<li class="${x.cls || ""}${x.key ? " key" : ""}"><span class="m">${ml}</span><div>${x.title ? `<b>${esc(x.title)}</b>` : ""}<p>${esc(x.text)}</p></div></li>`;
  }).join("")}</ol>`;
}

// Entry points

let lastKey = "";

export function renderTab(tab, el, variantFor) {
  lastKey = "";
  if (tab === "lineups") el.innerHTML = `<div class="lu">${lineupsHTML()}</div>`;
  else if (tab === "stats") el.innerHTML = `<div class="stats">${statsHTML()}</div>`;
  else if (tab === "commentary") {
    el.innerHTML = `<div class="comm-head"><label class="switch"><input type="checkbox" id="keyonly" ${S.keyOnly ? "checked" : ""}>
      <span>Key events only</span></label></div><div id="commlist">${commentaryHTML(variantFor)}</div>`;
    el.querySelector("#keyonly").addEventListener("change", (e) => { S.keyOnly = e.target.checked; tickTab(tab, el, variantFor, true); });
  }
  bindCards(el);
}

export function tickTab(tab, el, variantFor, force = false) {
  const key = `${tab}:${Math.floor(S.clock / 60)}:${S.lens}`;
  if (!force && key === lastKey) return;
  lastKey = key;
  if (tab === "commentary") { const l = el.querySelector("#commlist"); if (l) l.innerHTML = commentaryHTML(variantFor); return; }
  renderTab(tab, el, variantFor);
  lastKey = key;
}

function bindCards(el) {
  el.querySelectorAll("[data-pid]").forEach((b) => b.addEventListener("click", () => openPlayerCard(b.dataset.pid)));
}
