// The table: any season, either division. Analyst view adds xG columns and the points race.
import { esc, num } from "../lib/util.js";
import { L, club, crest, kitColour, formChips, clubHref, zoneClass, pointsByRound, seasonLabel,
  divisionName } from "../lib/league.js";
import { raceChart, bindRace } from "../lib/charts.js";

const ZONES = [
  ["z-cup", "Continental Cup"], ["z-shield", "Continental Shield"], ["z-up", "Promotion"],
  ["z-po", "Play-offs"], ["z-down", "Relegation"],
];

export function renderTable(main, S, arg) {
  const d = L.data;
  const season = S.hubSeason;
  const tables = d.season[season].tables;
  const div = tables[arg] ? arg : "1";
  const t = tables[div];
  const analyst = S.style === "analyst";
  const done = div === "1" ? t.after_round >= 38 : t.after_round >= 46;
  const usedZones = new Set(t.rows.map((r) => zoneClass(r.zone)).filter(Boolean));
  const champ = done ? t.rows[0] : null;

  main.innerHTML = `<div class="page">
    <header class="page-head with-img gold" style="--img:url(assets/hero-trophy.webp)">
      <div><p class="crumb">${esc(seasonLabel(season))}</p>
      <h1 class="cond">${esc(divisionName(div))} table</h1>
      <p class="lede">${done ? (champ ? `Final table. ${esc(club(champ.club).name)} are champions with ${champ.pts} points.` : "Final table.")
        : `After ${t.after_round} of ${div === "1" ? 38 : 46} rounds.`}</p></div>
    </header>
    <div class="seg-row">
      <div class="segs" role="group" aria-label="Division">
        ${Object.keys(tables).map((k) => `<a class="seg" href="#/table/${k}" aria-pressed="${k === div}">${esc(divisionName(k))}</a>`).join("")}
      </div>
      ${Object.keys(tables).length < 2 ? `<span class="muted small">Crown League Two is shown for completed seasons.</span>` : ""}
    </div>
    <div class="tbl-wrap"><table class="tbl full">
      <thead><tr><th class="pos">#</th><th>Club</th><th title="Played">P</th><th class="hide-s" title="Won">W</th><th class="hide-s" title="Drawn">D</th><th class="hide-s" title="Lost">L</th>
        <th class="hide-s" title="Goals for">GF</th><th class="hide-s" title="Goals against">GA</th><th title="Goal difference">GD</th>
        ${analyst ? `<th title="Expected goals for">xGF</th><th title="Expected goals against">xGA</th><th title="xG difference">xGD</th>` : ""}
        <th>Pts</th><th class="hide-m">Last 5</th></tr></thead>
      <tbody>${t.rows.map((r) => {
        const xgd = r.xgf != null ? r.xgf - r.xga : null;
        return `<tr class="${zoneClass(r.zone)}" style="--k:${kitColour(r.club)}">
          <td class="pos">${r.pos}</td>
          <td class="club"><span class="cl">${crest(r.club, "c")}<a href="${clubHref(r.club)}">${esc(club(r.club).name)}</a>${champ && r === champ ? `<span class="champ-tag">Champions</span>` : ""}</span></td>
          <td>${r.p}</td><td class="hide-s">${r.w}</td><td class="hide-s">${r.d}</td><td class="hide-s">${r.l}</td>
          <td class="hide-s">${r.gf}</td><td class="hide-s">${r.ga}</td><td>${r.gd > 0 ? "+" : ""}${r.gd}</td>
          ${analyst ? `<td>${num(r.xgf, 1)}</td><td>${num(r.xga, 1)}</td><td class="${xgd > 0 ? "pos-v" : "neg-v"}">${xgd != null ? `${xgd > 0 ? "+" : ""}${num(xgd, 1)}` : "–"}</td>` : ""}
          <td class="pts">${r.pts}</td><td class="hide-m">${formChips(r.form, true)}</td></tr>`;
      }).join("")}</tbody></table></div>
    <ul class="zone-key">${ZONES.filter(([c]) => usedZones.has(c)).map(([c, label]) => `<li class="${c}"><i></i>${esc(label)}</li>`).join("")}</ul>
    ${analyst && div === "1" ? `<section class="sec"><h2>The points race</h2>
      <p class="note">Points after every round. Point at a line to follow a club; click it to open the club.</p>
      <div id="race"></div></section>
      <section class="sec"><h2>Results against chances</h2>
      <p class="note">Goal difference against xG difference. Clubs above the line have done better than their chances suggest; below it, worse.</p>
      <div id="luck"></div></section>` : ""}
  </div>`;

  if (analyst && div === "1") {
    const { pts } = pointsByRound(season);
    const top = t.rows.slice(0, 4).map((r) => r.club);
    const series = t.rows.map((r) => ({ id: r.club, label: club(r.club).code, colour: kitColour(r.club), values: pts[r.club] }));
    const race = main.querySelector("#race");
    race.innerHTML = raceChart(series, { highlight: top });
    bindRace(race, series, (id) => { location.hash = clubHref(id); });
    drawLuck(main.querySelector("#luck"), t.rows);
  }
}

function drawLuck(el, rows) {
  const W = 960, H = 380, m = { l: 48, r: 18, t: 14, b: 42 };
  const xs = rows.map((r) => r.xgf - r.xga), ys = rows.map((r) => r.gd);
  const lim = Math.ceil(Math.max(5, ...xs.map(Math.abs), ...ys.map(Math.abs)) / 10) * 10;
  const x = (v) => m.l + ((v + lim) / (2 * lim)) * (W - m.l - m.r);
  const y = (v) => H - m.b - ((v + lim) / (2 * lim)) * (H - m.t - m.b);
  const ticks = [];
  for (let v = -lim; v <= lim; v += lim / 2) {
    ticks.push(`<line class="g" x1="${m.l}" x2="${W - m.r}" y1="${y(v)}" y2="${y(v)}"/><text class="t" x="${m.l - 8}" y="${y(v) + 4}" text-anchor="end">${v > 0 ? "+" : ""}${v}</text>`);
    ticks.push(`<text class="t" x="${x(v)}" y="${H - m.b + 18}" text-anchor="middle">${v > 0 ? "+" : ""}${v}</text>`);
  }
  el.innerHTML = `<figure class="chart scatter"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Goal difference against xG difference for every club">
    ${ticks.join("")}
    <line class="diag" x1="${x(-lim)}" y1="${y(-lim)}" x2="${x(lim)}" y2="${y(lim)}"/>
    <text class="t axis" x="${(m.l + W - m.r) / 2}" y="${H - 6}" text-anchor="middle">xG difference</text>
    <text class="t axis" transform="translate(14 ${(m.t + H - m.b) / 2}) rotate(-90)" text-anchor="middle">Goal difference</text>
    ${rows.map((r) => `<a class="dot crest-dot" href="${clubHref(r.club)}" data-label="${esc(club(r.club).name)}" data-sub="Goal difference ${r.gd > 0 ? "+" : ""}${r.gd}, xG difference ${(r.xgf - r.xga) > 0 ? "+" : ""}${num(r.xgf - r.xga, 1)}">
      <image href="${esc(club(r.club).crest || "")}" x="${x(r.xgf - r.xga) - 11}" y="${y(r.gd) - 11}" width="22" height="22"/>
      <circle cx="${x(r.xgf - r.xga)}" cy="${y(r.gd)}" r="12" class="halo"/></a>`).join("")}
  </svg><figcaption class="chart-tip" hidden></figcaption></figure>`;
  const fig = el.querySelector("figure"), tip = el.querySelector(".chart-tip");
  el.querySelectorAll(".dot").forEach((d) => {
    const show = () => {
      tip.hidden = false;
      tip.innerHTML = `<b>${esc(d.dataset.label)}</b><br>${esc(d.dataset.sub)}`;
      const r = fig.getBoundingClientRect(), c = d.querySelector("circle").getBoundingClientRect();
      tip.style.left = `${c.left - r.left + 18}px`; tip.style.top = `${c.top - r.top - 40}px`;
    };
    d.addEventListener("pointerenter", show); d.addEventListener("focus", show);
    d.addEventListener("pointerleave", () => { tip.hidden = true; }); d.addEventListener("blur", () => { tip.hidden = true; });
  });
}
