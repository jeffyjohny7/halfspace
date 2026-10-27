// Clubs: every club of the season, and a page per club.
import { esc, num } from "../lib/util.js";
import { L, club, crest, kitColour, formChips, clubHref, playerHref, seasonFile, seasonLabel, ordinal,
  divisionName, roundFixtures, dateLabel } from "../lib/league.js";
import { pctBar, spellBars } from "../lib/charts.js";

const PHIL = { possession: "possession football", counter: "counter-attacking", high_press: "high press",
  direct: "direct play", balanced: "balanced" };
const GROUPS = [["GK", "Goalkeepers"], ["DF", "Defenders"], ["MF", "Midfielders"], ["FW", "Forwards"]];
const POS_GROUP = { GK: "GK", CB: "DF", RB: "DF", LB: "DF", DM: "MF", CM: "MF", AM: "MF", RW: "FW", LW: "FW", ST: "FW" };

export function renderClubs(main, S) {
  const season = S.hubSeason;
  const rows = L.data.season[season].tables["1"].rows;
  const ids = rows.map((r) => r.club).sort((a, b) => club(a).name.localeCompare(club(b).name));
  main.innerHTML = `<div class="page">
    <header class="page-head with-img" style="--img:url(assets/hero-stadium.webp)"><div><p class="crumb">Crown League, ${esc(seasonLabel(season))}</p>
      <h1 class="cond">Clubs</h1><p class="lede">Twenty clubs. Open one for its squad, form, results and how it plays.</p></div></header>
    <div class="club-wall">${ids.map((id) => {
      const c = club(id);
      const r = rows.find((x) => x.club === id);
      return `<a class="club-tile" href="${clubHref(id)}" style="--k:${kitColour(id)};--k2:${c.kit[1]}">
        ${crest(id, "tile-crest")}<span class="ct-name cond">${esc(c.name)}</span>
        <span class="ct-sub">${esc(c.stadium)}</span><span class="ct-pos">${ordinal(r.pos)}, ${r.pts} pts</span></a>`;
    }).join("")}</div>
  </div>`;
}

export async function renderClub(main, S, id) {
  const d = L.data;
  if (!d.clubs[id]) { main.innerHTML = `<div class="page"><p class="lede">No club with that id. <a href="#/clubs">All clubs</a>.</p></div>`; return; }
  const season = S.hubSeason;
  const c = club(id);
  const analyst = S.style === "analyst";
  const div = c.div?.[season];
  const t = d.season[season].tables[String(div)];
  const row = t?.rows.find((r) => r.club === id);
  const [clubs, players] = await Promise.all([seasonFile(season, "clubs"), seasonFile(season, "players")]).catch(() => [{}, {}]);
  const info = clubs[id];
  const results = d.season[season].results.filter((r) => r.home === id || r.away === id);
  const next = season === d.current_season ? roundFixtures().find((f) => f.home === id || f.away === id) : null;

  const head = `<header class="club-head" style="--k:${kitColour(id)};--k2:${c.kit[1]}">
    ${crest(id, "club-crest")}
    <div class="ch-txt">
      <p class="crumb"><a href="#/clubs">Clubs</a>, ${esc(seasonLabel(season))}</p>
      <h1 class="cond">${esc(c.name)}</h1>
      <p class="ch-sub">${esc(c.stadium)}, ${esc(c.town)}. Manager: ${esc(c.manager?.[season] || info?.manager || "–")}${info ? `, ${esc(info.formation)}, ${esc(PHIL[info.philosophy] || info.philosophy)}` : ""}.</p>
      ${row ? `<div class="ch-stats"><span><b class="cond">${ordinal(row.pos)}</b>${esc(divisionName(div))}</span><span><b class="cond">${row.pts}</b>points</span>
        <span><b class="cond">${row.w}-${row.d}-${row.l}</b>won, drawn, lost</span><span><b class="cond">${row.gf}:${row.ga}</b>goals</span>${formChips(row.form)}</div>` : ""}
    </div>
  </header>`;

  if (!info) {
    main.innerHTML = `<div class="page">${head}<section class="sec"><p class="lede">${esc(c.name)} played in ${esc(divisionName(div || 2))} in ${esc(seasonLabel(season))}.
      Detailed numbers are kept for the top division.</p></section></div>`;
    return;
  }
  const squad = info.squad.map((s) => ({ ...s, st: players[s.p] }));
  const resList = results.slice(-8).reverse().map((r) => {
    const home = r.home === id;
    const gf = home ? r.hg : r.ag, ga = home ? r.ag : r.hg;
    const res = gf > ga ? "W" : gf < ga ? "L" : "D";
    const opp = home ? r.away : r.home;
    return `<li><a href="#/result/${r.id}"><span class="fr ${res}">${res}</span><span class="muted">${home ? "v" : "at"}</span>
      ${crest(opp, "c")}<span class="o">${esc(club(opp).name)}</span><b class="cond">${gf}–${ga}</b><span class="muted r">MD ${r.round}</span></a></li>`;
  }).join("");
  const by = info.goals_for_by, against = info.goals_against_by;
  const setp = (o) => (o.corner || 0) + (o.free_kick || 0) + (o.direct_free_kick || 0) + (o.throw_in || 0);
  const scoreWays = [["Open play", by.open_play + (by.counter || 0)], ["Set pieces", setp(by)], ["Penalties", by.penalty || 0], ["Own goals", by.own_goal || 0]];
  const metricGroups = ["attack", "defence", "style"].map((g) => [g, info.metrics.filter((m) => m.group === g)]).filter(([, ms]) => ms.length);

  main.innerHTML = `<div class="page">${head}
    <div class="cols-2">
      <section class="sec"><h2>Results</h2>
        ${next ? `<a class="next-fx" href="${next.id === d.showcase ? "#/match/before" : `#/fixture/${next.id}`}">Next: ${next.home === id ? "v" : "at"} ${esc(club(next.home === id ? next.away : next.home).name)},
          ${esc(dateLabel(next.date, { weekday: "long" }))} ${esc(next.ko)}${next.id === d.showcase ? ", streamed live" : ""}</a>` : ""}
        <ul class="club-results">${resList || `<li class="muted">No league games yet.</li>`}</ul>
        <p class="muted small">Home ${info.record.home.join("-")}, away ${info.record.away.join("-")} (won-drawn-lost).</p>
      </section>
      <section class="sec"><h2>How they score</h2>
        <ul class="ways">${scoreWays.map(([k, v]) => `<li><span>${esc(k)}</span><span class="way-bar"><i style="width:${(v / Math.max(1, row?.gf || 1)) * 100}%"></i></span><b>${v}</b></li>`).join("")}</ul>
        <p class="muted small">Conceded: ${against.open_play + (against.counter || 0)} from open play, ${setp(against)} from set pieces, ${against.penalty || 0} penalties.</p>
        ${analyst ? `<h3 class="sub-h">When the goals come</h3>${spellBars(["0-15", "16-30", "31-45", "46-60", "61-75", "76-90"].map((label, i) => ({
          label, a: info.goals_for_time[i] || 0, b: info.goals_against_time[i] || 0 })), { a: "Scored", b: "Conceded", ca: kitColour(id) })}` : ""}
      </section>
    </div>
    <section class="sec"><h2>Key players</h2><div class="key-players">${info.top.slice(0, 5).map((pid) => playerTile(pid, players[pid], id)).join("")}</div></section>
    ${analyst ? `<section class="sec"><h2>The numbers, against the league</h2>
      <p class="note">Where ${esc(c.name)} rank among the twenty clubs. A full bar is the best in the league; the tick is the median.</p>
      <div class="metric-groups">${metricGroups.map(([g, ms]) => `<div><h3 class="sub-h">${g === "attack" ? "Attack" : g === "defence" ? "Defence" : "Style"}</h3>
        <ul class="metrics">${ms.map((m) => `<li><span class="ml">${esc(m.label)}</span>${pctBar(m.better === "low" ? 100 - m.pct : m.pct, { better: m.better ? "high" : null, colour: kitColour(id) })}
          <b>${fmtMetric(m.value)}</b><span class="muted md">median ${fmtMetric(m.median)}</span></li>`).join("")}</ul></div>`).join("")}</div>
    </section>` : ""}
    ${info.notes?.length ? `<section class="sec"><h2>The scout's notes</h2><ul class="scout-notes">${info.notes.map((n) => `<li class="${esc(n.kind)}">
      <span class="tag">${n.kind === "weakness" ? "Weakness" : n.kind === "strength" ? "Strength" : "Pattern"}</span>${esc(n.text)}${analyst ? ` <span class="muted">(${esc(n.confidence)} confidence)</span>` : ""}</li>`).join("")}</ul></section>` : ""}
    <section class="sec"><h2>Squad</h2><div class="squad-list">${GROUPS.map(([g, label]) => {
      const list = squad.filter((s) => POS_GROUP[s.pos] === g);
      return list.length ? `<div><h3 class="sub-h">${label}</h3><ul>${list.map((s) => `<li><a href="${playerHref(s.p)}">
        <span class="sq-num cond">${s.shirt ?? ""}</span><span class="n">${esc(s.st?.name || s.name || s.p)}</span><span class="muted">${esc(s.pos)}</span>
        <span class="sq-st">${s.st ? `${s.st.apps} apps${s.st.goals ? `, ${s.st.goals} goals` : ""}` : "no games yet"}</span></a></li>`).join("")}</ul></div>` : "";
    }).join("")}</div></section>
  </div>`;
}

function fmtMetric(v) {
  if (v == null) return "–";
  if (Math.abs(v) < 1) return num(v, 2);
  if (Math.abs(v) < 10) return num(v, 1);
  return num(v, 0);
}

function playerTile(pid, p, cid) {
  if (!p) return "";
  const line = p.group === "GK" ? `${p.clean_sheets} clean sheets` : `${p.goals} goals, ${p.assists} assists`;
  return `<a class="kp-tile" href="${playerHref(pid)}" style="--k:${kitColour(cid)}">
    ${p.photo ? `<img src="${esc(p.photo)}" alt="">` : `<span class="kp-tile-blank">${crest(cid, "c")}</span>`}
    <span class="pt-name">${esc(p.name)}</span><span class="muted">${esc(p.pos)}, ${line}</span>
    ${p.rating ? `<span class="rt-chip ${p.rating >= 8 ? "great" : p.rating >= 7 ? "good" : p.rating >= 6 ? "ok" : "poor"}">${num(p.rating, 2)}</span>` : ""}</a>`;
}
