// The player card: a chalk-paper sheet that opens over any screen (squads, line-ups) and closes with the
// cross, Escape or a click outside.
import { S } from "../app.js";
import { esc, crestImg, shirtSVG } from "../lib/util.js";
import { ratingAt, ratingBand, fmtRating, fmtChange } from "../lib/rating.js";
import { drawHeat, gridPoints, heatPitchSVG } from "../lib/heat.js";

export const POS = { GK: "Goalkeeper", CB: "Centre-back", RB: "Right-back", LB: "Left-back", DM: "Defensive midfielder",
  CM: "Central midfielder", AM: "Attacking midfielder", RW: "Right winger", LW: "Left winger", ST: "Striker" };
const PEERS = { GK: "goalkeepers", CB: "centre-backs", RB: "full-backs", LB: "full-backs", DM: "defensive midfielders",
  CM: "central midfielders", AM: "attacking midfielders", RW: "wingers", LW: "wingers", ST: "strikers" };
const ON_BALL = new Set(["pass", "carry", "take_on", "shot", "dispossessed", "tackle", "interception", "clearance",
  "aerial_duel", "ball_recovery", "block", "gk_save"]);

let dlg = null, current = null, onCloseCb = null, heatMode = "match", lastMinute = -1;

export function openPlayerCard(pid, { onClose } = {}) {
  if (!S.data.players[pid]) return;
  if (!dlg) {
    dlg = document.createElement("dialog");
    dlg.className = "pcard";
    dlg.setAttribute("aria-labelledby", "pc-name");
    document.body.appendChild(dlg);
    dlg.addEventListener("click", (e) => { if (e.target === dlg) closePlayerCard(); });   // outside the card
    dlg.addEventListener("close", () => {
      const cb = onCloseCb; onCloseCb = null; current = null;
      document.documentElement.classList.remove("modal-open");
      if (cb) cb();
    });
  }
  current = pid; onCloseCb = onClose || null;
  heatMode = ratingAt(pid) ? "match" : "season";
  draw();
  if (!dlg.open) { dlg.showModal(); document.documentElement.classList.add("modal-open"); }
  dlg.querySelector(".pc-scroll").scrollTop = 0;
  dlg.querySelector(".pc-close").focus();
}

export function closePlayerCard() { if (dlg?.open) dlg.close(); }

export function tickPlayerCard() {
  if (!dlg?.open || !current) return;
  const m = Math.floor(S.clock / 60);
  if (m === lastMinute) return;
  lastMinute = m;
  const keep = dlg.querySelector(".pc-scroll").scrollTop;
  draw();
  dlg.querySelector(".pc-scroll").scrollTop = keep;
}

// Pieces

function seasonOf(p) {
  const all = Object.keys(p.season_stats || {}).sort();
  return all.includes(S.season) ? S.season : all[all.length - 1];
}

const n1 = (v) => (v == null ? "–" : String(Math.round(v * 100) / 100));
const pctTxt = (v) => (v == null ? "" : ` (${Math.round(v * 100)}%)`);

function roleRows(p, s) {
  const g = p.pos;
  if (g === "GK") return [["Saves per game", n1(s.saves_pg)], ["Pass accuracy", s.pass_rate == null ? "–" : `${Math.round(s.pass_rate * 100)}%`],
    ["Ball recoveries per game", n1(s.recoveries_pg)]];
  if (g === "CB") return [["Tackles and interceptions per game", n1(s.tackles_int_pg)],
    ["Headers won per game", `${n1(s.headers_won_pg)}${pctTxt(s.header_rate)}`], ["Clearances per game", n1(s.clearances_pg)]];
  if (g === "RB" || g === "LB") return [["Tackles and interceptions per game", n1(s.tackles_int_pg)],
    ["Key passes per game", n1(s.key_passes_pg)], ["Ball recoveries per game", n1(s.recoveries_pg)]];
  if (g === "DM" || g === "CM") return [["Touches per game", n1(s.touches_pg)], ["Ball recoveries per game", n1(s.recoveries_pg)],
    ["Pass accuracy", s.pass_rate == null ? "–" : `${Math.round(s.pass_rate * 100)}%`]];
  if (g === "AM" || g === "RW" || g === "LW") return [["Key passes per game", n1(s.key_passes_pg)],
    ["Dribbles per game", `${n1(s.dribbles_pg)}${pctTxt(s.dribble_rate)}`], ["Shots per game", n1(s.shots_pg)]];
  return [["Shots per game", n1(s.shots_pg)], ["Chance quality per game (xG)", n1(s.xg_pg)],
    ["Headers won per game", `${n1(s.headers_won_pg)}${pctTxt(s.header_rate)}`]];
}

function matchPoints(pid) {
  const d = S.data, idx = d.players_order.indexOf(pid), out = [];
  if (idx < 0) return out;
  for (const e of d.events) {
    if (e[0] > S.clock) break;
    if (e[3] === idx && e[6] != null && ON_BALL.has(e[4])) out.push([e[6], e[7], 1]);
  }
  return out;
}

function wheelSVG(items, number) {
  const cx = 230, cy = 215, r0 = 58, r1 = 170, n = items.length;
  if (!n) return "";
  const gap = 0.035, span = (Math.PI * 2) / n;
  const pt = (a, r) => [cx + r * Math.sin(a), cy - r * Math.cos(a)];
  const sector = (a0, a1, ra, rb) => {
    const [x0, y0] = pt(a0, rb), [x1, y1] = pt(a1, rb), [x2, y2] = pt(a1, ra), [x3, y3] = pt(a0, ra);
    const large = a1 - a0 > Math.PI ? 1 : 0;
    return `M${x0} ${y0} A${rb} ${rb} 0 ${large} 1 ${x1} ${y1} L${x2} ${y2} A${ra} ${ra} 0 ${large} 0 ${x3} ${y3} Z`;
  };
  const rings = [0.25, 0.5, 0.75, 1].map((f) =>
    `<circle class="ring${f === 0.5 ? " mid" : ""}" cx="${cx}" cy="${cy}" r="${r0 + (r1 - r0) * f}"/>`).join("");
  const segs = items.map((it, i) => {
    const a0 = i * span + gap, a1 = (i + 1) * span - gap;
    const r = r0 + (r1 - r0) * Math.max(0.03, it.pct / 100);
    const mid = (a0 + a1) / 2;
    const [lx, ly] = pt(mid, r1 + 26);
    const [px, py] = pt(mid, Math.max(r0 + 22, r - 16));
    const anchor = Math.abs(Math.sin(mid)) < 0.2 ? "middle" : Math.sin(mid) > 0 ? "start" : "end";
    return `<path class="seg-bg" d="${sector(a0, a1, r0, r1)}"/>
      <path class="seg" d="${sector(a0, a1, r0, r)}"><title>${esc(it.full_label)}: ${it.value} (better than ${it.pct}% of peers)</title></path>
      <text class="pct" x="${px}" y="${py + 6}" text-anchor="middle">${it.pct}</text>
      <text class="lbl" x="${lx}" y="${ly + 4}" text-anchor="${anchor}">${esc(it.label)}</text>`;
  }).join("");
  return `<svg viewBox="-80 0 620 430" role="img" aria-label="Percentile wheel">${rings}${segs}
    <circle class="hub" cx="${cx}" cy="${cy}" r="${r0 - 6}"/>
    <text x="${cx}" y="${cy + 14}" text-anchor="middle" class="pct hubnum">${number ?? ""}</text></svg>`;
}

// "This match": why the rating is what it is, and the counts behind it.
function matchWhy(rt) {
  if (!rt) return `<p class="pc-note">${S.clock <= 0 ? "The match hasn't started yet." : "He hasn't played yet."}</p>`;
  return `<div class="pc-why">${rt.reasons.slice(0, 6).map((x) => `<div class="row"><span>${esc(x.label)}${x.count > 1 ? ` ×${x.count}` : ""}</span>
      <b class="${x.change >= 0 ? "up" : "down"}">${fmtChange(x.change)}</b></div>`).join("")}
      <div class="row base"><span>Everyone starts at 6.0</span><b>${fmtRating(rt.value)}</b></div></div>`;
}

function matchTiles(p, rt) {
  if (!rt) return "";
  const st = rt.stats, gk = p.pos === "GK";
  const tiles = [["Goals", st.goals], ["Assists", st.assists], ["Key passes", st.key_passes],
    ["Accurate passes", `${st.accurate}/${st.passes}`], ["Misplaced passes", st.misplaced], ["Touches", st.touches],
    gk ? ["Saves", st.saves] : ["Shots on target", `${st.on_target}/${st.shots}`], ["Tackles", st.tackles],
    ["Interceptions", st.interceptions], gk ? ["Clearances", st.clearances] : ["Dribbles", `${st.dribbles}/${st.dribbles_tried}`],
    ["Headers won", `${st.headers_won}/${st.headers}`], ["Ball recoveries", st.recoveries]];
  return `<div class="pc-tiles">${tiles.map(([k, v]) => `<div><b>${v}</b><span>${k}</span></div>`).join("")}</div>`;
}

function draw() {
  const d = S.data, p = d.players[current];
  const club = d.match[p.side];
  const season = seasonOf(p);
  const st = (p.season_stats || {})[season] || {};
  const avg = p.ratings?.[season];
  const rt = ratingAt(current);
  const [first, ...rest] = p.name.split(" ");
  const wheelSeasons = Object.keys(p.seasons || {}).sort();
  const ws = wheelSeasons.includes(season) ? season : wheelSeasons[wheelSeasons.length - 1];
  const wheel = (p.seasons?.[ws] || {}).wheel || [];
  const badge = rt ? { v: rt.value, k: "this match" } : avg ? { v: avg.average, k: "season average" } : null;
  const rows = [["Age", p.age ?? "–"], ["Matches played", st.matches ?? 0], ["Goals", st.goals ?? 0], ["Assists", st.assists ?? 0],
    ["Average rating", avg ? avg.average.toFixed(2) : "–"], ...roleRows(p, st)];
  const news = p.news;
  const lost = p.lost_ball?.dispossessed;
  const zones = lost && lost.count ? Object.entries(lost.by_zone).sort((a, b) => b[1] - a[1]).slice(0, 3)
    .map(([z, c]) => `${z.replace("_third", " third").replace(":", ", ")} (${c})`).join("; ") : null;
  const hasMatch = !!rt, hasSeason = !!(p.heat || {})[season];
  if (heatMode === "match" && !hasMatch) heatMode = "season";

  dlg.style.setProperty("--team", p.side === "home" ? "var(--home)" : "var(--away)");
  dlg.innerHTML = `<div class="pc">
    <header class="pc-top">
      <div class="pc-meta">${crestImg(club, "pc-crest")}<span>${esc(club.name)}, ${esc(season || "")} season</span></div>
      <button class="pc-close" type="button" aria-label="Close player card">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6 L18 18 M18 6 L6 18"/></svg></button>
    </header>
    <div class="pc-scroll">
      <div class="pc-title">
        <h2 id="pc-name"><span class="first">${esc(first)}</span> ${esc(rest.join(" "))}</h2>
        ${badge ? `<div class="pc-rating"><span class="rt ${ratingBand(badge.v)}">${fmtRating(badge.v)}</span><span class="k">${badge.k}</span></div>` : ""}
      </div>
      <div class="pc-hero">
        <figure class="pc-photo">
          ${p.photo ? `<img src="${esc(p.photo)}" alt="${esc(p.name)}" loading="eager">`
            : `<div class="pc-shirt">${shirtSVG(club.kit[0], club.kit[1], p.num)}</div>`}
          <figcaption><span class="num">${p.num ?? ""}</span><span>${esc(POS[p.pos] || p.pos)}</span></figcaption>
        </figure>
        <div class="pc-side">
          <dl class="pc-table">${rows.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("")}</dl>
        </div>
      </div>
      ${news ? `<p class="pc-flag">${news.status === "suspended" ? "Suspended" : news.status === "doubtful" ? "Doubtful" : "Injured"}: ${esc(news.reason)}${news.expected_return
        ? `, expected back ${new Date(news.expected_return).toLocaleDateString("en-GB", { day: "numeric", month: "long" })}` : ""}.</p>` : ""}
      <section class="pc-sec pc-now">
        <div class="pc-now-heat">
          <div class="pc-heat-head"><h3>Where he played</h3>
            <div class="pc-seg" role="group" aria-label="Heat map period">
              <button type="button" data-heat="match" aria-pressed="${heatMode === "match"}" ${hasMatch ? "" : "disabled"}>This match</button>
              <button type="button" data-heat="season" aria-pressed="${heatMode === "season"}" ${hasSeason ? "" : "disabled"}>Season</button>
            </div></div>
          <div class="heat-box"><canvas aria-label="Heat map"></canvas>${heatPitchSVG()}</div>
          <p class="pc-note">Attacking to the right. Every touch, pass, tackle and header counts.</p>
        </div>
        <div class="pc-now-why"><h3>This match${rt ? `, ${fmtRating(rt.value)}` : ""}</h3>${matchWhy(rt)}</div>
      </section>
      ${matchTiles(p, rt)}
      ${wheel.length ? `<section class="pc-sec"><h3>Against other ${esc(PEERS[p.pos] || "players")}, ${esc(ws)}</h3>
        <div class="pc-wheel">${wheelSVG(wheel, p.num)}</div><p class="pc-note">Further out is better. The number is how many of his peers he beats, out of 100.</p></section>` : ""}
      ${p.findings?.length ? `<section class="pc-sec"><h3>What the scout noticed</h3><ul class="pc-list">
        ${p.findings.map((f) => `<li>${esc(f.summary)}${f.confidence === "medium" ? " One to watch." : ""}</li>`).join("")}</ul></section>` : ""}
      <section class="pc-sec"><h3>Fitness</h3><ul class="pc-list">
        <li>${p.injuries?.injuries ? `${p.injuries.injuries} injur${p.injuries.injuries > 1 ? "ies" : "y"} in the last two seasons${
          p.injuries.latest ? `, most recently a ${esc(p.injuries.latest.injury)} on ${new Date(p.injuries.latest.date).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}` : ""}.` : "No injuries in the last two seasons."}</li>
        ${zones ? `<li>Loses the ball most in: ${esc(zones)}.</li>` : ""}</ul></section>
    </div></div>`;

  dlg.querySelector(".pc-close").addEventListener("click", closePlayerCard);
  dlg.querySelectorAll("[data-heat]").forEach((b) => b.addEventListener("click", () => {
    heatMode = b.dataset.heat;
    dlg.querySelectorAll("[data-heat]").forEach((x) => x.setAttribute("aria-pressed", x === b));
    paintHeat(p, season);
  }));
  requestAnimationFrame(() => paintHeat(p, season));
}

function paintHeat(p, season) {
  const canvas = dlg?.querySelector(".heat-box canvas");
  if (!canvas) return;
  const pts = heatMode === "match" ? matchPoints(current)
    : gridPoints((p.heat || {})[season] || [], S.data.heat_bins || [21, 14]);
  drawHeat(canvas, pts, heatMode === "match" ? 7 : 5.5);
}
