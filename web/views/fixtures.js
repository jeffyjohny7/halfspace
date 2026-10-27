// Matches: a round's fixtures or results, a fixture preview, a result page.
import { esc, num } from "../lib/util.js";
import { L, club, crest, kitColour, teamVars, kitInk, probBar, roundFixtures, dateLabel, formChips, clubHref, clubLink,
  playerHref, seasonFile, ordinal, seasonLabel } from "../lib/league.js";
import { pctBar } from "../lib/charts.js";
import { liveState } from "../lib/live.js";
import { liveBadge } from "./home.js";

const seasonOfMatch = (id) => `${id.slice(0, 4)}-${id.slice(4, 6)}`;

// ------------------------------------------------------------------ round list

export function renderMatches(main, S, arg) {
  const d = L.data;
  const season = S.hubSeason;
  const cur = season === d.current_season;
  const played = d.season[season].rounds_played;
  const maxRound = cur ? d.current_round : played;
  const round = Math.max(1, Math.min(maxRound, Number(arg) || maxRound));
  const upcoming = cur && round === d.current_round;
  const st = liveState(S);

  let body;
  if (upcoming) {
    const byDay = {};
    for (const f of roundFixtures()) (byDay[f.date] ||= []).push(f);
    body = Object.entries(byDay).map(([day, list]) => `
      <h2 class="day">${esc(dateLabel(day))}</h2>
      <div class="fx-list">${list.map((f) => fixtureRow(f, f.id === d.showcase ? st : null)).join("")}</div>`).join("");
  } else {
    const res = d.season[season].results.filter((r) => r.round === round);
    const byDay = {};
    for (const r of res) (byDay[r.date] ||= []).push(r);
    body = Object.entries(byDay).sort().map(([day, list]) => `
      <h2 class="day">${esc(dateLabel(day))}</h2>
      <div class="fx-list">${list.map((r) => resultRow(r, S)).join("")}</div>`).join("");
  }
  main.innerHTML = `<div class="page">
    <header class="page-head with-img" style="--img:url(assets/hero-tunnel.webp)">
      <div><p class="crumb">Crown League, ${esc(seasonLabel(season))}</p>
      <h1 class="cond">Matchday ${round}</h1>
      <p class="lede">${upcoming ? "Kick-off times, win chances and previews. The 12:30 game is streamed live with checked insights." : "Results. Open a match for the goals, the numbers and every player's rating."}</p></div>
    </header>
    <nav class="rounds" aria-label="Rounds">
      <a class="btn ghost sm" ${round > 1 ? `href="#/matches/${round - 1}"` : 'aria-disabled="true"'}>Matchday ${Math.max(1, round - 1)}</a>
      <select id="round" aria-label="Choose a matchday">${Array.from({ length: maxRound }, (_, i) => i + 1).reverse()
        .map((r) => `<option value="${r}" ${r === round ? "selected" : ""}>Matchday ${r}${cur && r === d.current_round ? " (this weekend)" : ""}</option>`).join("")}</select>
      <a class="btn ghost sm" ${round < maxRound ? `href="#/matches/${round + 1}"` : 'aria-disabled="true"'}>Matchday ${Math.min(maxRound, round + 1)}</a>
    </nav>
    ${body}
  </div>`;
  main.querySelector("#round").addEventListener("change", (e) => { location.hash = `#/matches/${e.target.value}`; });
}

function fixtureRow(f, st) {
  const h = club(f.home), a = club(f.away);
  const live = !!st;
  const mid = live && st.status !== "pre"
    ? `<span class="fx-score cond">${st.score[0]}–${st.score[1]}</span>`
    : `<span class="fx-ko cond">${esc(f.ko)}</span>`;
  return `<article class="fx${live ? " is-live" : ""}" style="${teamVars(f.home, f.away)}">
    <a class="fx-main" href="${live ? `#/match/${st.status === "pre" ? "before" : st.status === "ft" ? "full-time" : "live"}` : `#/fixture/${f.id}`}">
      <span class="fx-team h"><span class="nm">${esc(h.name)}</span>${crest(f.home, "c")}</span>
      <span class="fx-mid">${mid}${live ? liveBadge(st) : ""}</span>
      <span class="fx-team a">${crest(f.away, "c")}<span class="nm">${esc(a.name)}</span></span>
    </a>
    <div class="fx-foot">
      <div class="fx-prob">${probBar(f)}</div>
      <div class="fx-links">${live ? `<a href="#/match/live">Match centre</a>` : ""}<a href="#/fixture/${f.id}">Preview</a></div>
    </div>
  </article>`;
}

function resultRow(r, S) {
  const h = club(r.home), a = club(r.away);
  const analyst = S.style === "analyst";
  return `<article class="fx res" style="${teamVars(r.home, r.away)}">
    <a class="fx-main" href="#/result/${r.id}">
      <span class="fx-team h"><span class="nm">${esc(h.name)}</span>${crest(r.home, "c")}</span>
      <span class="fx-mid"><span class="fx-score cond">${r.hg}–${r.ag}</span>${analyst ? `<span class="fx-xg">xG ${num(r.hxg, 1)}–${num(r.axg, 1)}</span>` : `<span class="fx-xg">Full time</span>`}</span>
      <span class="fx-team a">${crest(r.away, "c")}<span class="nm">${esc(a.name)}</span></span>
    </a>
  </article>`;
}

// ------------------------------------------------------------------ preview

export async function renderFixture(main, S, id) {
  const d = L.data;
  const f = d.fixtures.find((x) => x.id === id);
  if (!f) { main.innerHTML = `<div class="page"><p class="lede">That fixture isn't in this round. <a href="#/matches">See the matches</a>.</p></div>`; return; }
  const h = club(f.home), a = club(f.away);
  const p = f.preview;
  const isShow = f.id === d.showcase;
  const st = liveState(S);
  const analyst = S.style === "analyst";
  const season = d.current_season;
  const rows = Object.fromEntries(d.season[season].tables["1"].rows.map((r) => [r.club, r]));
  const players = await seasonFile(season, "players").catch(() => ({}));
  const byName = Object.fromEntries(Object.entries(players).map(([pid, x]) => [`${x.name}|${x.club}`, pid]));
  const plink = (txt, cid) => {
    const m = /^(.*?) \(([^)]*)\)$/.exec(txt);
    const name = m ? m[1] : txt;
    const pid = byName[`${name}|${cid}`];
    return `${pid ? `<a href="${playerHref(pid)}">${esc(name)}</a>` : esc(name)}${m ? ` <span class="muted">${esc(m[2])}</span>` : ""}`;
  };
  const stake = (cid) => {
    const s = p.stakes[cid];
    if (!s) return "";
    const win = s.position_if_win === s.position ? `A win would keep them ${ordinal(s.position)}` : `A win would take them to ${ordinal(s.position_if_win)}`;
    const draw = s.position_if_draw !== s.position ? `, a draw to ${ordinal(s.position_if_draw)}` : "";
    return `<li><b>${esc(club(cid).name)}</b> are ${ordinal(s.position)} on ${s.points} points. ${win}${draw}.</li>`;
  };
  const news = (cid) => {
    const n = p.news[cid] || { out: [], doubtful: [] };
    return `<div class="news-col"><h3>${crest(cid, "c")}${esc(club(cid).name)}</h3>
      ${n.out.length ? `<p class="lbl">Out</p><ul>${n.out.map((x) => `<li>${plink(x.replace(/ \(([^,]*), .*\)$/, " ($1)"), cid)}<span class="muted">${esc((/, (.*)\)$/.exec(x) || [])[1] || "")}</span></li>`).join("")}</ul>` : `<p class="muted">No one out.</p>`}
      ${n.doubtful.length ? `<p class="lbl">Doubtful</p><ul>${n.doubtful.map((x) => {
        const m = /^(.*) \(([^:]*): (.*)\)$/.exec(x);
        return `<li>${m ? `${plink(`${m[1]} (${m[2]})`, cid)}<span class="muted">${esc(m[3])}</span>` : esc(x)}</li>`;
      }).join("")}</ul>` : ""}</div>`;
  };
  const lineup = (cid) => {
    const lu = p.lineups[cid];
    if (!lu) return "";
    return `<div class="lu-col" style="--k:${kitColour(cid)}"><h3>${crest(cid, "c")}${esc(club(cid).name)} <span class="muted">${esc(lu.formation)}</span></h3>
      <ol>${lu.players.map((x) => `<li>${plink(x, cid)}</li>`).join("")}</ol></div>`;
  };
  const style = analyst && p.style?.length ? `<section class="sec"><h2>How they play</h2>
    <table class="style-tbl"><thead><tr><th></th><th>${esc(h.code)}</th><th>${esc(a.code)}</th></tr></thead><tbody>
    ${p.style.map((m) => `<tr><th>${esc(m.metric)}</th>
      <td>${pctBar(m[`${h.name} pct`], { better: null, colour: kitColour(f.home) })}<span>${num(m[h.name], m[h.name] < 1 ? 2 : 1)}</span></td>
      <td>${pctBar(m[`${a.name} pct`], { better: null, colour: kitColour(f.away) })}<span>${num(m[a.name], m[a.name] < 1 ? 2 : 1)}</span></td></tr>`).join("")}
    </tbody></table><p class="note">Bars show where each club ranks in the league (the middle is the league median).</p></section>` : "";

  main.innerHTML = `<div class="page">
    <header class="match-head" style="${teamVars(f.home, f.away)}">
      <p class="crumb"><a href="#/matches">Matchday ${f.round}</a>, ${esc(dateLabel(f.date))}, ${esc(h.stadium)}</p>
      <div class="mh-row">
        <a class="mh-club" href="${clubHref(f.home)}">${crest(f.home, "mh-crest")}<span class="cond">${esc(h.name)}</span></a>
        <div class="mh-mid">${isShow ? liveBadge(st) : ""}<span class="cond mh-ko">${isShow && st.status !== "pre" ? `${st.score[0]}–${st.score[1]}` : esc(f.ko)}</span></div>
        <a class="mh-club a" href="${clubHref(f.away)}">${crest(f.away, "mh-crest")}<span class="cond">${esc(a.name)}</span></a>
      </div>
      ${probBar(f)}
      <p class="mh-exp">Expected goals ${num(f.outlook.xg_home, 1)} – ${num(f.outlook.xg_away, 1)}, likeliest score ${esc(f.outlook.likely_score)}</p>
      ${isShow ? `<div class="cta-row"><a class="btn live" href="#/match/${st.status === "pre" ? "before" : "live"}">${st.status === "pre" ? "Watch live" : "Back to the match"}</a></div>` : ""}
    </header>

    <div class="cols-2">
      <section class="sec"><h2>Form</h2>
        <div class="form-rows">
          <div>${crest(f.home, "c")}<span>${esc(h.name)}</span>${rows[f.home] ? formChips(rows[f.home].form) : ""}</div>
          <div>${crest(f.away, "c")}<span>${esc(a.name)}</span>${rows[f.away] ? formChips(rows[f.away].form) : ""}</div>
        </div>
        <ul class="stakes">${stake(f.home)}${stake(f.away)}</ul>
      </section>
      <section class="sec"><h2>Head to head</h2>
        ${p.h2h.length ? `<ul class="h2h">${p.h2h.map((x) => `<li>${esc(analyst ? x : x.replace(/ \(xG [^)]*\)/, ""))}</li>`).join("")}</ul>` : `<p class="muted">They haven't met in the last two seasons.</p>`}
        <p class="muted">Managers: ${Object.entries(p.managers).map(([cn, m]) => `${esc(m.manager)} (${esc(cn)}, ${esc(m.formation)}${m.new_this_season ? ", new this season" : ""})`).join("; ")}.</p>
      </section>
    </div>

    <section class="sec"><h2>Key battles</h2>
      <p class="note">What the stats engine found in both clubs' data. Each one names who it favours.</p>
      <div class="edges">${p.edges.map((e) => `<article class="edge" style="--k:${kitColour(e.for)}">
        <h3>${crest(e.for, "c")}${esc(e.title)}</h3><p>${esc(e.text.replace(/\.;\s*/g, "; "))}</p></article>`).join("")}</div>
      ${p.watch?.length ? `<h3 class="sub-h">What to watch for</h3><ul class="watch">${p.watch.map((w) => `<li>${esc(w.replace(/; confirmed at (\d+)\.?$/, ". Confirmed if it reaches $1."))}</li>`).join("")}</ul>` : ""}
    </section>

    <section class="sec"><h2>Team news</h2><div class="cols-2 tight">${news(f.home)}${news(f.away)}</div></section>
    <section class="sec"><h2>Probable line-ups</h2><div class="cols-2 tight">${lineup(f.home)}${lineup(f.away)}</div></section>
    ${style}
  </div>`;
}

// ------------------------------------------------------------------ result

const STAT_ROWS = [
  ["xg", "Chance quality (xG)", (v) => num(v, 2)],
  ["shots", "Shots", String], ["sot", "On target", String], ["possession", "Possession", (v) => `${Math.round(v)}%`],
  ["pass_pct", "Pass completion", (v) => `${Math.round(v)}%`], ["corners", "Corners", String],
  ["fouls", "Fouls", String], ["yellow", "Yellow cards", String], ["red", "Red cards", String],
];

export async function renderResult(main, S, id) {
  const season = seasonOfMatch(id);
  const res = L.data.season[season]?.results.find((r) => r.id === id);
  const [matches, players] = await Promise.all([seasonFile(season, "matches"), seasonFile(season, "players")]).catch(() => [{}, {}]);
  const m = matches[id];
  if (!res || !m) { main.innerHTML = `<div class="page"><p class="lede">No details for that match. <a href="#/matches">See the matches</a>.</p></div>`; return; }
  const h = club(res.home), a = club(res.away);
  const name = (pid) => players[pid]?.name || pid;
  const analyst = S.style === "analyst";
  const goals = m.goals.map((g) => `<li class="${g.team === res.home ? "h" : "a"}"><span class="min cond">${g.min}′</span>
      <span><a href="${playerHref(g.player)}">${esc(name(g.player))}</a>${g.pen ? " (pen)" : ""}${g.og ? " (own goal)" : ""}${g.assist ? `<span class="muted">, assist ${esc(name(g.assist))}</span>` : ""}</span></li>`).join("");
  const stats = STAT_ROWS.map(([k, label, fmt]) => {
    const x = m.stats.home[k] ?? 0, y = m.stats.away[k] ?? 0;
    const tot = x + y || 1;
    return `<div class="sbar"><div class="sbar-top"><b>${fmt(x)}</b><span>${esc(label)}</span><b>${fmt(y)}</b></div>
      ${x + y > 0 ? `<div class="sbar-bars"><i style="width:${(x / tot) * 100}%;background:var(--h)"></i><i style="width:${(y / tot) * 100}%;background:var(--a)"></i></div>` : ""}</div>`;
  }).join("");
  const potm = [...m.lineups.home, ...m.lineups.away].filter((x) => x.rt != null).sort((p, q) => q.rt - p.rt)[0];
  const side = (list, cid) => `<div class="lu-col rated" style="--k:${kitColour(cid)}"><h3>${crest(cid, "c")}${esc(club(cid).name)}</h3>
    <ol>${list.map((x) => `<li class="${x.start ? "" : "sub"}"><a href="${playerHref(x.p)}">${esc(name(x.p))}</a>
      <span class="muted">${esc(x.pos)}${x.on != null ? `, on ${x.on}′` : ""}${x.off != null ? `, off ${x.off}′` : ""}</span>
      ${x.rt != null ? `<span class="rt-chip ${rtBand(x.rt)}">${num(x.rt, 1)}</span>` : ""}</li>`).join("")}</ol></div>`;
  main.innerHTML = `<div class="page">
    <header class="match-head" style="${teamVars(res.home, res.away)}">
      <p class="crumb"><a href="#/matches/${res.round}">Matchday ${res.round}</a>, ${esc(seasonLabel(season))}, ${esc(dateLabel(res.date))}, ${esc(h.stadium)}</p>
      <div class="mh-row">
        <a class="mh-club" href="${clubHref(res.home)}">${crest(res.home, "mh-crest")}<span class="cond">${esc(h.name)}</span></a>
        <div class="mh-mid"><span class="badge done">Full time</span><span class="cond mh-ko">${res.hg}–${res.ag}</span></div>
        <a class="mh-club a" href="${clubHref(res.away)}">${crest(res.away, "mh-crest")}<span class="cond">${esc(a.name)}</span></a>
      </div>
      ${goals ? `<ul class="goal-list">${goals}</ul>` : ""}
    </header>
    <div class="cols-2">
      <section class="sec" style="${teamVars(res.home, res.away)}"><h2>Match numbers</h2>${stats}</section>
      <section class="sec"><h2>Player of the match</h2>
        ${potm ? `<a class="potm-row" href="${playerHref(potm.p)}">${players[potm.p]?.photo && players[potm.p].club === (m.lineups.home.includes(potm) ? res.home : res.away) ? `<img src="${esc(players[potm.p].photo)}" alt="">` : ""}
          <span class="pr-name"><b class="cond">${esc(name(potm.p))}</b><span class="muted">${esc(potm.pos)}</span></span><span class="rt-chip big ${rtBand(potm.rt)}">${num(potm.rt, 1)}</span></a>` : ""}
        <p class="note">Ratings run from 3 to 10 and start at 6.0. Every action adds or takes away a little: a goal, a key pass, a tackle, a misplaced pass.</p>
      </section>
    </div>
    <section class="sec"><h2>Line-ups and ratings</h2><div class="cols-2 tight">${side(m.lineups.home, res.home)}${side(m.lineups.away, res.away)}</div></section>
  </div>`;
}

export function rtBand(r) { return r >= 8 ? "great" : r >= 7 ? "good" : r >= 6 ? "ok" : "poor"; }
