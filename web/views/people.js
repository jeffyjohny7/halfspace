// Players: the season's players (search, filter, sort) and a season page per player.
// Live match ratings live in the match centre (#/match/ratings), not here.
import { esc, num, shirtSVG } from "../lib/util.js";
import { L, club, crest, kitColour, clubHref, playerHref, seasonFile, seasonLabel, ordinal } from "../lib/league.js";
import { pctBar } from "../lib/charts.js";
import { rtBand } from "./fixtures.js";

const GROUPS = [["", "All"], ["GK", "Goalkeepers"], ["DF", "Defenders"], ["MF", "Midfielders"], ["FW", "Forwards"]];
const SORTS = {
  rating: ["Rating", (p) => p.rating ?? 0], goals: ["Goals", (p) => p.goals], assists: ["Assists", (p) => p.assists],
  minutes: ["Minutes", (p) => p.minutes], xg: ["xG", (p) => p.xg], key_passes: ["Chances created", (p) => p.key_passes],
};
const PCT_LABEL = { goals_p90: "Goals", xg_p90: "xG", assists_p90: "Assists", key_passes_p90: "Chances created",
  prog_p90: "Progressive passes", dribbles_p90: "Dribbles won", def_p90: "Tackles + interceptions",
  aerial_pct: "Aerial duels won", pass_pct: "Pass completion" };
const P90 = { goals_p90: "goals", xg_p90: "xg", assists_p90: "assists", key_passes_p90: "key_passes", prog_p90: "prog",
  dribbles_p90: "dribbles", def_p90: null };

const F = { q: "", group: "", club: "", sort: "rating", shown: 40 };

export async function renderPeople(main, S) {
  const season = S.hubSeason;
  const analyst = S.style === "analyst";
  const clubs = L.data.season[season].tables["1"].rows.map((r) => r.club).sort((a, b) => club(a).name.localeCompare(club(b).name));
  main.innerHTML = `<div class="page">
    <header class="page-head"><div><p class="crumb">Crown League, ${esc(seasonLabel(season))}</p>
      <h1 class="cond">Players</h1><p class="lede">Every player's season. For live ratings in today's match, open the <a href="#/match/ratings">match centre</a>.</p></div></header>
    <form class="filters" id="filters" role="search">
      <input type="search" id="fq" placeholder="Search players" value="${esc(F.q)}" aria-label="Search players">
      <div class="segs" role="group" aria-label="Position">${GROUPS.map(([g, label]) => `<button type="button" class="seg" data-g="${g}" aria-pressed="${F.group === g}">${label}</button>`).join("")}</div>
      <select id="fclub" aria-label="Club"><option value="">All clubs</option>${clubs.map((c) => `<option value="${c}" ${F.club === c ? "selected" : ""}>${esc(club(c).name)}</option>`).join("")}</select>
      <select id="fsort" aria-label="Sort by">${Object.entries(SORTS).filter(([k]) => analyst || !["xg", "key_passes"].includes(k))
        .map(([k, [label]]) => `<option value="${k}" ${F.sort === k ? "selected" : ""}>Sort: ${label}</option>`).join("")}</select>
    </form>
    <div id="plist"><p class="loading-s">Loading…</p></div>
  </div>`;
  const players = await seasonFile(season, "players").catch(() => ({}));
  const draw = () => {
    const q = F.q.trim().toLowerCase();
    const key = SORTS[F.sort] ? F.sort : "rating";
    const list = Object.entries(players)
      .filter(([, p]) => p.minutes > 0 && (!F.group || p.group === F.group) && (!F.club || p.club === F.club)
        && (!q || p.name.toLowerCase().includes(q)))
      .sort((a, b) => SORTS[key][1](b[1]) - SORTS[key][1](a[1]) || b[1].minutes - a[1].minutes);
    const el = main.querySelector("#plist");
    el.innerHTML = `<div class="tbl-wrap"><table class="tbl players">
      <thead><tr><th>Player</th><th class="hide-s">Club</th><th>Pos</th><th title="Appearances">Apps</th><th>Goals</th><th>Assists</th>
        ${analyst ? `<th class="hide-s">xG</th><th class="hide-s" title="Chances created">Chances</th>` : ""}<th>Rating</th></tr></thead>
      <tbody>${list.slice(0, F.shown).map(([pid, p]) => `<tr style="--k:${kitColour(p.club)}">
        <td class="pl"><a href="${playerHref(pid)}">${p.photo ? `<img src="${esc(p.photo)}" alt="">` : `<span class="pl-blank">${crest(p.club, "c")}</span>`}<span>${esc(p.name)}</span></a></td>
        <td class="hide-s"><a class="clublink" href="${clubHref(p.club)}">${crest(p.club, "c")}${esc(club(p.club).code)}</a></td>
        <td>${esc(p.pos)}</td><td>${p.apps}</td><td>${p.goals}</td><td>${p.assists}</td>
        ${analyst ? `<td class="hide-s">${num(p.xg, 1)}</td><td class="hide-s">${p.key_passes}</td>` : ""}
        <td>${p.rating ? `<span class="rt-chip ${rtBand(p.rating)}">${num(p.rating, 2)}</span>` : "–"}</td></tr>`).join("")}</tbody></table></div>
      <p class="muted small">${list.length} players${list.length > F.shown ? `. <button class="linkbtn" id="more">Show more</button>` : ""}</p>`;
    el.querySelector("#more")?.addEventListener("click", () => { F.shown += 60; draw(); });
  };
  draw();
  const form = main.querySelector("#filters");
  form.addEventListener("submit", (e) => e.preventDefault());
  main.querySelector("#fq").addEventListener("input", (e) => { F.q = e.target.value; F.shown = 40; draw(); });
  main.querySelector("#fclub").addEventListener("change", (e) => { F.club = e.target.value; F.shown = 40; draw(); });
  main.querySelector("#fsort").addEventListener("change", (e) => { F.sort = e.target.value; draw(); });
  main.querySelectorAll("[data-g]").forEach((b) => b.addEventListener("click", () => {
    F.group = b.dataset.g; F.shown = 40;
    main.querySelectorAll("[data-g]").forEach((x) => x.setAttribute("aria-pressed", x === b));
    draw();
  }));
}

export async function renderPerson(main, S, pid) {
  const d = L.data;
  const analyst = S.style === "analyst";
  const all = await Promise.all(d.seasons.map((s) => seasonFile(s, "players").then((x) => [s, x[pid]]).catch(() => [s, null])));
  const have = all.filter(([, p]) => p);
  if (!have.length) { main.innerHTML = `<div class="page"><p class="lede">No league games for this player. <a href="#/players">All players</a>.</p></div>`; return; }
  const season = have.find(([s]) => s === S.hubSeason) ? S.hubSeason : have[have.length - 1][0];
  const p = have.find(([s]) => s === season)[1];
  const k = kitColour(p.club);
  const c = club(p.club);
  const gk = p.group === "GK";
  const nums = gk
    ? [["Apps", p.apps], ["Clean sheets", p.clean_sheets], ["Saves", p.saves], ["Conceded", p.conceded], ["Pass completion", `${num(p.pass_pct, 0)}%`], ["Rating", num(p.rating, 2)]]
    : [["Apps", `${p.apps}${p.apps !== p.starts ? ` (${p.starts})` : ""}`], ["Goals", p.goals], ["Assists", p.assists], ["Shots", p.shots],
       ["Chances created", p.key_passes], ["Rating", num(p.rating, 2)]];
  const adv = analyst && !gk ? [["xG", num(p.xg, 1)], ["xA", num(p.xa, 1)], ["Goals − xG", `${p.goals - p.xg >= 0 ? "+" : ""}${num(p.goals - p.xg, 1)}`],
    ["Pass completion", `${num(p.pass_pct, 0)}%`], ["Dribbles won", p.dribbles], ["Tackles + interceptions", p.tackles + p.interceptions]] : [];
  const m90 = p.minutes / 90;
  const pcts = Object.entries(p.pct || {}).filter(([m]) => PCT_LABEL[m] && !(gk && m !== "pass_pct" && m !== "aerial_pct"));
  const best = [...pcts].sort((a, b) => b[1] - a[1]).slice(0, 3).filter(([, v]) => v >= 70);
  const groupName = { GK: "goalkeepers", DF: "defenders", MF: "midfielders", FW: "forwards" }[p.group] || "players";

  main.innerHTML = `<div class="page">
    <header class="player-head" style="--k:${k};--k2:${c.kit[1]}">
      <div class="ph-photo">${p.photo ? `<img src="${esc(p.photo)}" alt="${esc(p.name)}">` : shirtSVG(c.kit[0], c.kit[1], "")}</div>
      <div class="ph-txt">
        <p class="crumb"><a href="#/players">Players</a>, ${esc(seasonLabel(season))}</p>
        <h1 class="cond">${esc(p.name)}</h1>
        <p class="ph-sub"><a href="${clubHref(p.club)}">${crest(p.club, "c")}${esc(c.name)}</a>, ${esc(p.pos)}${p.age ? `, ${p.age}` : ""}</p>
        ${have.length > 1 ? `<div class="segs" role="group" aria-label="Season">${have.map(([s]) => `<button class="seg" data-season="${s}" aria-pressed="${s === season}">${esc(seasonLabel(s))}</button>`).join("")}</div>` : ""}
      </div>
    </header>
    <section class="sec"><h2>${esc(seasonLabel(season))} season</h2>
      <div class="bignums">${nums.map(([l, v]) => `<div><b class="cond">${v ?? "–"}</b><span>${esc(l)}</span></div>`).join("")}</div>
      ${adv.length ? `<div class="bignums small">${adv.map(([l, v]) => `<div><b class="cond">${v}</b><span>${esc(l)}</span></div>`).join("")}</div>` : ""}
      <p class="muted small">${p.minutes} minutes${p.yellow || p.red ? `, ${p.yellow} yellow and ${p.red} red cards` : ""}.</p>
    </section>
    <div class="cols-2">
      <section class="sec"><h2>Recent ratings</h2>
        ${p.ratings?.length ? `<div class="rt-bars">${p.ratings.map(([mid, r]) => `<a href="#/result/${mid}" title="Matchday ${Number(mid.split("-R")[1]?.slice(0, 2))}: ${num(r, 1)}">
          <span class="${rtBand(r)}" style="height:${Math.max(6, ((r - 3) / 7) * 100)}%"></span><em>${num(r, 1)}</em></a>`).join("")}</div>
          <p class="note">His last ${p.ratings.length} league games, oldest first. Open one for the match.</p>` : `<p class="muted">No rated games yet.</p>`}
      </section>
      <section class="sec"><h2>${analyst ? `Against other ${groupName}` : "What he does best"}</h2>
        ${analyst ? `<ul class="metrics">${pcts.map(([m, v]) => `<li><span class="ml">${esc(PCT_LABEL[m])}${P90[m] ? " per 90" : ""}</span>${pctBar(v, { colour: k })}
          <b>${m.endsWith("_pct") ? `${num(p[m], 0)}%` : P90[m] ? num(p[P90[m]] / m90, 2) : num((p.tackles + p.interceptions) / m90, 1)}</b><span class="muted md">${ordPct(v)}</span></li>`).join("")}</ul>
          <p class="note">Percentile among ${groupName} with at least 270 minutes this season.</p>`
        : best.length ? `<ul class="best-list">${best.map(([m, v]) => `<li><b>${esc(PCT_LABEL[m])}</b>: better than ${v}% of ${groupName}.</li>`).join("")}</ul>`
          : `<p class="muted">Not enough minutes yet to compare him with other ${groupName}.</p>`}
      </section>
    </div>
  </div>`;
  main.querySelectorAll("[data-season]").forEach((b) => b.addEventListener("click", () => {
    S.hubSeason = b.dataset.season;
    renderPerson(main, S, pid);
    document.dispatchEvent(new CustomEvent("halfspace:season"));
  }));
}

const ordPct = (v) => `${ordinal(v)} percentile`;
