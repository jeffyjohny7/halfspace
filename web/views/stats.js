// Stats: the season's leaders. Analyst view adds the advanced boards and goals against xG.
import { esc, num } from "../lib/util.js";
import { L, club, crest, kitColour, playerHref, seasonFile, seasonLabel } from "../lib/league.js";
import { scatter, bindScatter } from "../lib/charts.js";

const CASUAL = ["goals", "assists", "key_passes", "clean_sheets", "rating"];
const ANALYST = ["goals", "assists", "xg", "key_passes", "def", "clean_sheets", "rating"];
const FMT = { xg: (v) => num(v, 1), rating: (v) => num(v, 2) };

export async function renderStats(main, S) {
  const season = S.hubSeason;
  const analyst = S.style === "analyst";
  const leaders = L.data.season[season].leaders;
  main.innerHTML = `<div class="page">
    <header class="page-head"><div><p class="crumb">Crown League, ${esc(seasonLabel(season))}</p>
      <h1 class="cond">Player stats</h1>
      <p class="lede">${analyst ? "The leaders, the underlying numbers, and who is finishing above or below their chances." : "Who's scoring, who's creating and who's keeping clean sheets."}</p></div></header>
    <div class="boards${analyst ? " analyst" : ""}" id="boards"><p class="loading-s">Loading…</p></div>
    ${analyst ? `<section class="sec"><h2>Goals against chances</h2>
      <p class="note">Every player with at least 3 xG. Above the line, finishing better than the chances suggest; below, worse. Point at a dot for the numbers; click to open the player.</p>
      <div id="gx"></div></section>` : ""}
  </div>`;
  const players = await seasonFile(season, "players").catch(() => ({}));
  const keys = (analyst ? ANALYST : CASUAL).filter((k) => leaders[k]);
  main.querySelector("#boards").innerHTML = keys.map((k, i) => board(k, leaders[k], players, i === 0)).join("");
  if (analyst) {
    const pts = Object.entries(players).filter(([, p]) => p.xg >= 3).map(([pid, p]) => ({
      id: pid, x: p.xg, y: p.goals, r: 4 + Math.min(6, p.shots / 25), colour: kitColour(p.club),
      label: `${p.name} (${club(p.club).code})`, sub: `${p.goals} goals from ${num(p.xg, 1)} xG, ${p.shots} shots`,
    }));
    const top = new Set([...pts].sort((a, b) => b.y - a.y).slice(0, 4).map((p) => p.id)
      .concat([...pts].sort((a, b) => (b.y - b.x) - (a.y - a.x)).slice(0, 2).map((p) => p.id))
      .concat([...pts].sort((a, b) => (a.y - a.x) - (b.y - b.x)).slice(0, 2).map((p) => p.id)));
    pts.forEach((p) => { if (top.has(p.id)) p.tag = players[p.id].name.split(" ").slice(-1)[0]; });
    const el = main.querySelector("#gx");
    el.innerHTML = scatter(pts, { xLabel: "Expected goals (xG)", yLabel: "Goals", diagonal: true, href: (p) => playerHref(p.id) });
    bindScatter(el);
  }
}

function board(key, b, players, wide) {
  const fmt = FMT[key] || String;
  const [first, ...rest] = b.rows;
  const p = players[first.player] || {};
  return `<article class="board${wide ? " wide" : ""}" style="--k:${kitColour(first.club)}">
    <h2>${esc(b.label)}</h2>
    <a class="board-top" href="${playerHref(first.player)}">
      <span class="bt-txt"><span class="bt-rank">1</span><span class="bt-name cond">${esc(p.name || first.player)}</span>
        <span class="bt-club">${crest(first.club, "c")}${esc(club(first.club).name)}</span>
        <span class="bt-num cond">${fmt(first.value)}</span></span>
      ${p.photo ? `<img class="bt-photo" src="${esc(p.photo)}" alt="">` : `<span class="bt-crest">${crest(first.club, "big")}</span>`}
    </a>
    <ol class="board-list" start="2">${rest.slice(0, wide ? 9 : 4).map((r) => `<li><a href="${playerHref(r.player)}">
      <span class="r"></span>${crest(r.club, "c")}<span class="n">${esc(players[r.player]?.name || r.player)}</span>
      <span class="cl">${esc(club(r.club).code)}</span><b>${fmt(r.value)}</b></a></li>`).join("")}</ol>
  </article>`;
}
