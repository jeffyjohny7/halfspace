// Home: the live match up front, the rest of the matchday, the table, the leaders, the last results.
import { esc } from "../lib/util.js";
import { L, club, crest, kitColour, teamVars, probBar, roundFixtures, resultsOfRound, dateLabel, formChips, clubHref,
  playerHref, seasonFile, zoneClass } from "../lib/league.js";
import { liveState } from "../lib/live.js";
import { forYou } from "./me.js";

export function liveBadge(st) {
  if (st.status === "pre") return `<span class="badge soon"><i></i>About to kick off</span>`;
  if (st.status === "ft") return `<span class="badge done">Full time</span>`;
  return `<span class="badge live"><i></i>Live ${esc(st.label)}</span>`;
}

export function renderHome(main, S) {
  const d = L.data;
  const season = d.current_season;
  const fx = roundFixtures();
  const show = fx.find((f) => f.id === d.showcase) || fx[0];
  const others = fx.filter((f) => f !== show);
  const st = liveState(S);
  const h = club(show.home), a = club(show.away);
  const mid = st.status === "pre"
    ? `<div class="hero-ko cond">${esc(show.ko)}</div>`
    : `<div class="hero-score cond">${st.score[0]}<span>–</span>${st.score[1]}</div>`;
  const table = d.season[season].tables["1"].rows;
  const keep = new Set([...table.slice(0, 6).map((r) => r.club), show.home, show.away]);
  const rows = table.filter((r) => keep.has(r.club));
  const last = resultsOfRound(season, d.season[season].rounds_played);

  main.innerHTML = `
  <section class="home-hero" style="${teamVars(show.home, show.away)}">
    <div class="hero-bg" style="background-image:url(assets/hero-night.webp)"></div>
    <div class="hero-in">
      <p class="hero-kicker">Matchday ${d.current_round}, ${esc(dateLabel(show.date))}</p>
      <div class="hero-match">
        <a class="hero-club" href="${clubHref(h.id)}">${crest(h.id, "hero-crest")}<span class="cond">${esc(h.name)}</span></a>
        <div class="hero-mid">${liveBadge(st)}${mid}<div class="hero-venue">${esc(h.stadium)}</div></div>
        <a class="hero-club away" href="${clubHref(a.id)}">${crest(a.id, "hero-crest")}<span class="cond">${esc(a.name)}</span></a>
      </div>
      <div class="hero-prob">${probBar(show)}</div>
      <div class="hero-cta">
        <a class="btn live" href="#/match/${st.status === "pre" ? "before" : st.status === "ft" ? "full-time" : "live"}">${st.status === "pre" ? "Watch live" : st.status === "ft" ? "See full time" : "Back to the match"}</a>
        <a class="btn ghost" href="#/fixture/${show.id}">Match preview</a>
      </div>
    </div>
  </section>

  ${forYou() ? `<div class="home-strip">${forYou()}</div>` : ""}
  <section class="home-strip" aria-label="Also on matchday ${d.current_round}">
    <h2 class="strip-title">Also on matchday ${d.current_round}</h2>
    <div class="strip">${others.map((f) => `
      <a class="mini-fx" href="#/fixture/${f.id}" style="${teamVars(f.home, f.away)}">
        <span class="when">${esc(dateLabel(f.date, { weekday: "short" }))} ${esc(f.ko)}</span>
        <span class="t">${crest(f.home, "c")}<b>${esc(club(f.home).code)}</b></span>
        <span class="t">${crest(f.away, "c")}<b>${esc(club(f.away).code)}</b></span>
        <span class="mini-prob"><i style="flex:${f.outlook.home_win};background:var(--h)"></i><i class="d" style="flex:${f.outlook.draw}"></i><i style="flex:${f.outlook.away_win};background:var(--a)"></i></span>
      </a>`).join("")}</div>
  </section>

  <section class="home-grid">
    <div class="panel">
      <div class="panel-head"><h2>Crown League table</h2><a href="#/table">Full table</a></div>
      <table class="tbl mini"><thead><tr><th class="pos">#</th><th>Club</th><th>GD</th><th>Pts</th><th class="hide-s">Form</th></tr></thead>
      <tbody>${rows.map((r, i) => {
        const gap = i > 0 && r.pos - rows[i - 1].pos > 1 ? `<tr class="gap"><td colspan="5">…</td></tr>` : "";
        return `${gap}<tr class="${zoneClass(r.zone)}${r.club === show.home || r.club === show.away ? " hl" : ""}">
          <td class="pos">${r.pos}</td><td class="club"><span class="cl">${crest(r.club, "c")}<a href="${clubHref(r.club)}">${esc(club(r.club).name)}</a></span></td>
          <td>${r.gd > 0 ? "+" : ""}${r.gd}</td><td class="pts">${r.pts}</td><td class="hide-s">${formChips(r.form, true)}</td></tr>`;
      }).join("")}</tbody></table>
    </div>
    <div class="panel" id="home-leaders">
      <div class="panel-head"><h2>Top scorers</h2><a href="#/stats">All stats</a></div>
      <div class="loading-s">Loading…</div>
    </div>
    <div class="panel">
      <div class="panel-head"><h2>Matchday ${d.season[season].rounds_played} results</h2><a href="#/matches/${d.season[season].rounds_played}">All results</a></div>
      <ul class="results">${last.map((r) => `<li><a href="#/result/${r.id}">
        <span class="rtm h">${esc(club(r.home).name)}${crest(r.home, "c")}</span>
        <span class="rs cond">${r.hg}–${r.ag}</span>
        <span class="rtm a">${crest(r.away, "c")}${esc(club(r.away).name)}</span></a></li>`).join("")}</ul>
    </div>
  </section>`;

  drawLeaders(main.querySelector("#home-leaders"), season);
}

async function drawLeaders(el, season) {
  const players = await seasonFile(season, "players").catch(() => ({}));
  const goals = L.data.season[season].leaders.goals.rows.slice(0, 5);
  const assists = L.data.season[season].leaders.assists.rows.slice(0, 3);
  const top = goals[0];
  const p = players[top.player] || {};
  el.querySelector(".loading-s").outerHTML = `
    <a class="leader-hero" href="${playerHref(top.player)}" style="--k:${kitColour(top.club)}">
      ${p.photo ? `<img src="${esc(p.photo)}" alt="">` : `<span class="no-photo">${crest(top.club, "c")}</span>`}
      <span class="lh-txt"><span class="lh-name cond">${esc(p.name || top.player)}</span><span class="lh-club">${esc(club(top.club).name)}</span></span>
      <span class="lh-num cond">${top.value}</span>
    </a>
    <ol class="lead-list" start="2">${goals.slice(1).map((r) => `<li><a href="${playerHref(r.player)}">${crest(r.club, "c")}<span>${esc(players[r.player]?.name || r.player)}</span><b>${r.value}</b></a></li>`).join("")}</ol>
    <h3 class="sub-h">Most assists</h3>
    <ol class="lead-list">${assists.map((r) => `<li><a href="${playerHref(r.player)}">${crest(r.club, "c")}<span>${esc(players[r.player]?.name || r.player)}</span><b>${r.value}</b></a></li>`).join("")}</ol>`;
}
