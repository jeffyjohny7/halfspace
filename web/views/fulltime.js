// Full time: the result, what the scout said against what happened, player of the match.
import { S, setClock } from "../app.js";
import { esc, pct, num, minuteLabel, crestImg, LANG_OF, langAttrs } from "../lib/util.js";
import { variantFor } from "./match.js";
import { ratingAt, ratingBand, fmtRating } from "../lib/rating.js";

function fmt(p, v) {
  if (v == null) return "–";
  if (p.kind === "rate_at_most") return pct(v);
  if (p.measure.includes("xg")) return num(v);
  return Number.isInteger(v) ? String(v) : Number(v).toFixed(1);
}

const WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];
const word = (n) => (n >= 0 && n < WORDS.length ? WORDS[n] : String(n));
const cap = (t) => t.charAt(0).toUpperCase() + t.slice(1);
const surname = (n) => n.split(" ").slice(-1)[0];

// Plain-language recap for when no AI recap is available (offline runs): the goals in order, then the balance of play.
function storyRecap(d, last) {
  const { home, away } = d.match, team = [home, away];
  const goals = d.moments.filter((m) => m.type === "goal").sort((a, b) => a.clock - b.clock);
  const [h, a] = last.s, seen = new Set(), score = [0, 0];
  const sentences = goals.map((g, i) => {
    const t = g.team, f = g.facts, other = 1 - t;
    const who = seen.has(f.scorer) ? surname(f.scorer) : f.scorer; seen.add(f.scorer);
    const before = [...score]; score[t] += 1;
    const min = `${g.minute}`;
    if (f.own_goal) return `An own goal by ${who} counted for ${team[t].name} on ${min} minutes.`;
    if (i === 0) return `${who} put ${team[t].name} ahead on ${min} minutes.`;
    if (before[t] === before[other] - 1) return `${who} levelled on ${min}.`;
    if (before[t] === before[other]) return `${who} gave ${team[t].name} the lead on ${min}.`;
    if (before[t] > before[other]) return `${who} made it ${score[0]}–${score[1]} on ${min}.`;
    return `${who} pulled one back for ${team[t].name} on ${min}.`;
  });
  const lastGoal = goals[goals.length - 1];
  let headline;
  if (!goals.length) headline = `No way through at ${d.match.stadium}`;
  else if (h === a) headline = lastGoal.minute >= 80 && lastGoal.facts.context === "equaliser"
    ? `${surname(lastGoal.facts.scorer)} rescues a point for ${team[lastGoal.team].name}` : `Honours even at ${d.match.stadium}`;
  else {
    const w = h > a ? 0 : 1, wonLate = lastGoal.team === w && lastGoal.minute >= 80 && Math.abs(h - a) === 1;
    headline = wonLate ? `${surname(lastGoal.facts.scorer)} wins it late for ${team[w].name}` : `${team[w].name} beat ${team[1 - w].name}`;
  }
  const more = last.sh[0] === last.sh[1] ? null : last.sh[0] > last.sh[1] ? 0 : 1;
  let balance = "";
  if (more != null) {
    balance = `${team[more].name} had ${last.sh[more]} shots to ${last.sh[1 - more]}`;
    const xgMore = last.xg[0] >= last.xg[1] ? 0 : 1;
    balance += Math.abs(last.xg[0] - last.xg[1]) >= 0.5
      ? (xgMore === more ? ` and made the better chances (${num(last.xg[more])} xG to ${num(last.xg[1 - more])}).`
        : `, but ${team[xgMore].name} made the better chances (${num(last.xg[xgMore])} xG to ${num(last.xg[1 - xgMore])}).`)
      : ".";
  }
  return { headline, body: [...sentences, balance].filter(Boolean).join(" ") };
}

function potmReason(raw) {
  const m = /(\d+) goals?, (\d+) assists?, (\d+) shots? \(([\d.]+) xG\), (\d+) key pass(?:es)?.*?(\d+)% of passes completed/.exec(raw || "");
  if (!m) return raw || "";
  const [, g, as, sh, xg, kp, pc] = m.map((x, i) => (i === 4 ? x : +x));
  const parts = [];
  if (g) parts.push(`${cap(word(g))} goal${g > 1 ? "s" : ""}${sh ? ` from ${word(sh)} shot${sh > 1 ? "s" : ""} (${xg} xG)` : ""}`);
  else if (sh) parts.push(`${cap(word(sh))} shot${sh > 1 ? "s" : ""} worth ${xg} xG`);
  if (as) parts.push(`${word(as)} assist${as > 1 ? "s" : ""}`);
  if (kp >= 2) parts.push(`${word(kp)} passes that set up a shot`);
  parts.push(`${pc}% of passes completed`);
  const text = parts.length > 1 ? `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}.` : `${parts[0]}.`;
  return cap(text);
}

function callTitle(p) { return p.subject_type === "team" ? `${p.subject}: ${p.label}` : p.label; }

// Best three match ratings on each side, linked to the player sheets.
function topRated(d, end) {
  const side = (s) => d.lineups[s].map((p) => ({ p, rt: ratingAt(p.id, end) })).filter((x) => x.rt)
    .sort((a, b) => b.rt.value - a.rt.value).slice(0, 3);
  const col = (s) => `<div><h3 class="section-title" style="color:var(--${s}-ink)">${esc(d.match[s].name)}</h3>
    <ol class="rated">${side(s).map(({ p, rt }) => `<li><a href="#/match/ratings/${p.id}">${esc(p.name)}</a>
      <span class="why-top">${esc(rt.reasons[0]?.label || "")}${rt.reasons[0]?.count > 1 ? ` ×${rt.reasons[0].count}` : ""}</span>
      <span class="rt ${ratingBand(rt.value)}">${fmtRating(rt.value)}</span></li>`).join("")}</ol></div>`;
  return `<section class="chapter"><div><h2>Best rated</h2><p class="lede">Everyone starts at 6.0. Each action adds or takes away a set amount.</p></div>
    <div class="rated-pair">${col("home")}${col("away")}</div></section>`;
}

export function renderFullTime(main) {
  const d = S.data, end = d.match.end, { home, away } = d.match;
  if (S.clock < end) {
    main.innerHTML = `<div class="ft"><h1 class="fixture" style="font-size:clamp(34px,6vw,64px)">Full time isn't here yet</h1>
      <p class="fixture-meta">${S.clock > 0 ? "The match is still going." : "The match hasn't started yet."} Watch it through, or jump to the end to see how the scout's calls turned out.</p>
      <div class="cta-row"><a class="btn" href="#/match/live">Back to the match</a><button class="btn ghost" id="skip">Skip to full time</button></div></div>`;
    main.querySelector("#skip").addEventListener("click", () => { S.playing = false; setClock(end); });
    return;
  }
  const last = d.timeline[d.timeline.length - 1];
  const goals = d.moments.filter((m) => m.type === "goal");
  const scorers = (team) => goals.filter((g) => g.team === team).map((g) =>
    `${esc(g.facts.scorer)} ${minuteLabel(g.minute, g.clock > d.match.periods[0].end ? 2 : 1)}`).join(", ") || "";
  const post = d.cues.find((c) => c.phase === "postmatch");
  const pv = post ? variantFor(post, S.lens) : null;
  const lang = pv && pv.source !== "template" ? pv.hl : "en";
  const recap = d.recap || {};
  const story = storyRecap(d, last);
  const useAI = pv && pv.source !== "template";
  const potm = Object.values(d.players).find((p) => p.name === recap.player_of_the_match);
  const finals = d.predictions.map((p) => ({ p, row: p.timeline[p.timeline.length - 1] || [0, null, "did not happen"] }));
  const hits = finals.filter((f) => f.row[2] === "confirmed").length;
  main.innerHTML = `<div class="ft">
    <section class="ft-score" aria-label="Final score">
      <div class="team">${crestImg(home)}<div>${esc(home.name)}</div><div class="scorers">${scorers(0)}</div></div>
      <div class="goals">${last.s[0]} – ${last.s[1]}</div>
      <div class="team away">${crestImg(away)}<div>${esc(away.name)}</div><div class="scorers">${scorers(1)}</div></div>
    </section>
    <section class="chapter"><div><h2 ${langAttrs(lang)}>${esc(useAI ? pv.headline : story.headline)}</h2></div>
      <div><p class="lede" ${langAttrs(lang)} style="max-width:62ch;color:var(--chalk)">${esc(useAI ? pv.body : story.body)}</p></div></section>
    <section class="chapter">
      <div><h2>What the scout said</h2><p class="lede">${hits} of ${finals.length} pre-match calls came true.</p></div>
      <ul class="verdicts">${finals.map(({ p, row }) => {
        const yes = row[2] === "confirmed";
        return `<li class="verdict"><svg class="tick" viewBox="0 0 26 26" aria-label="${yes ? "Came true" : "Didn't happen"}">
          <circle cx="13" cy="13" r="11" fill="${yes ? "var(--chalk)" : "none"}" stroke="${yes ? "var(--chalk)" : "var(--chalk-3)"}" stroke-width="1.6"/>
          ${yes ? '<path d="M7.5 13.4 L11.3 17 L18.5 9.2" fill="none" stroke="var(--turf-0)" stroke-width="2.2"/>' : '<path d="M8.5 17.5 L17.5 8.5" stroke="var(--chalk-3)" stroke-width="1.6"/>'}
        </svg><div><p>${esc(callTitle(p))}</p><div class="res">${yes ? "Came true" : "Didn't happen"}. Expected about ${fmt(p, p.expected)}, average ${fmt(p, p.average)}, finished at ${fmt(p, row[1])}.</div></div></li>`;
      }).join("")}</ul>
    </section>
    ${potm ? `<section class="chapter"><div><h2>Player of the match</h2></div>
      <div class="potm">${potm.photo ? `<a class="potm-photo" href="#/match/ratings/${potm.id}" style="--team:${potm.side === "home" ? "var(--home)" : "var(--away)"}"><img src="${esc(potm.photo)}" alt="${esc(potm.name)}"><span>${potm.num ?? ""}</span></a>`
        : `<div class="big-num" style="--team:${potm.side === "home" ? "var(--home)" : "var(--away)"}">${potm.num ?? ""}</div>`}
      <div><h3 style="margin:0;font-size:30px;font-variation-settings:'wdth' 78"><a href="#/match/ratings/${potm.id}">${esc(potm.name)}</a>
        ${(() => { const rt = ratingAt(potm.id, end); return rt ? `<span class="rt ${ratingBand(rt.value)}" style="display:inline-block;width:46px;margin-left:10px;vertical-align:6px;font-size:18px">${fmtRating(rt.value)}</span>` : ""; })()}</h3>
      <p class="lede" style="max-width:56ch">${esc(potmReason(recap.player_reason))}</p></div></div></section>` : ""}
    ${topRated(d, end)}
    <section class="chapter"><div><h2>The numbers</h2></div>
      <div class="bars" style="max-width:520px">
        ${[["Possession", last.pos, pct], ["Chance quality (xG)", last.xg, (v) => num(v)], ["Shots", last.sh, (v) => v],
           ["Shots on target", last.sot, (v) => v], ["Corners", last.corners, (v) => v], ["Fouls", last.fouls, (v) => v]].map(([label, v, f]) => {
          const tot = (v[0] + v[1]) || 1;
          return `<div class="bar-row"><div class="label">${label}</div><div class="v" style="color:var(--home-ink)">${f(v[0])}</div>
            <div class="split"><span style="flex-grow:${v[0] / tot};background:var(--home)"></span><span style="flex-grow:${v[1] / tot};background:var(--away)"></span></div>
            <div class="v r" style="color:var(--away-ink)">${f(v[1])}</div></div>`;
        }).join("")}
      </div></section>
    <div class="cta-row"><button class="btn ghost" id="again">Watch it again</button><a class="btn" href="#/ask/match">Ask about this match</a></div>
  </div>`;
  main.querySelector("#again").addEventListener("click", () => { setClock(0); S.playing = true; location.hash = "#/match/live"; });
}
