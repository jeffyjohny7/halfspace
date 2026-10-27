// Ask: fans' questions about players, line-ups, injuries, fixtures and form.
import { S } from "../app.js";
import { esc, langAttrs, LANG_NAMES } from "../lib/util.js";
import { F, fanId, refreshAfterAsk } from "../lib/fan.js";

const LANGS = ["en", "es", "ar", "hi", "ml"].map((k) => [k, LANG_NAMES[k]]);

const possessive = (name) => (name.endsWith("s") ? `${name}’` : `${name}’s`);

function matchSuggestions() {
  const { home, away } = S.data.match;
  const done = S.clock >= S.data.match.end;
  return [
    done ? "Who was the best player in today's match?" : "What has happened in today's match so far?",
    `How did ${away.name} score their goals today?`,
    // The player of the match only once the match is over: before that it would give the game away.
    `How ${done ? "did" : "is"} ${(done && S.data.recap?.player_of_the_match)
      || (S.data.lineups.home.find((p) => p.start && p.pos === "ST") || S.data.lineups.home[0]).name} ${done ? "play" : "playing"} today?`,
    `Why couldn't ${home.name} turn their chances into goals?`,
  ];
}

function suggestions(about) {
  if (about === "match" && S.clock > 0) return matchSuggestions();
  const { home, away } = S.data.match;
  const star = Object.values(S.data.players).find((p) => p.side === "away" && p.pos === "ST")
    || Object.values(S.data.players)[0];
  return [
    `Who is injured or suspended for ${away.name}?`,
    `What line-up did ${home.name} use in their last match?`,
    `How has ${star.name} played this season?`,
    `How do ${away.name} usually concede goals?`,
    `Who are ${possessive(home.name)} most dangerous players?`,
  ];
}

function drawThread(main) {
  const t = main.querySelector("#thread");
  t.innerHTML = S.thread.map((m) => m.q
    ? `<div class="msg q" ${langAttrs(m.lang)}>${esc(m.q)}</div>`
    : `<div class="msg a${m.error ? " err" : ""}" ${langAttrs(m.lang || "en")}>${esc(m.a).replace(/\n/g, "<br>")}
        ${m.sources?.length ? `<div class="src">From: ${esc(m.sources.join(", "))}${m.checked ? ". Numbers checked against the data." : ""}</div>` : ""}
        ${m.blocked ? `<div class="src" lang="en" dir="ltr">Stopped by the Foundry guardrail: ${esc(m.blocked)}.</div>` : ""}
        ${m.heldBack ? `<div class="src" lang="en" dir="ltr">Held back by the Verifier: a number in the draft didn't match the data.</div>` : ""}
        ${m.remembered?.length ? `<div class="src remembered" lang="en" dir="ltr">Remembered: ${esc(m.remembered.join("; "))}. <a href="#/me">See or delete it in My Halfspace</a>.</div>` : ""}</div>`).join("");
  t.lastElementChild?.scrollIntoView({ block: "end", behavior: "smooth" });
}

// The last few verified exchanges, so follow-up questions ("and his goals?") make sense.
function history() {
  const out = [];
  S.thread.forEach((m, i) => {
    const r = S.thread[i + 1];
    if (m.q && r && r.a && !r.error && !r.pending) out.push({ q: m.q, a: r.a });
  });
  return out.slice(-3);
}

async function ask(main, question, lang) {
  const past = history();
  S.thread.push({ q: question, lang });
  S.thread.push({ a: "Looking it up…", lang: "en", pending: true });
  drawThread(main);
  let reply;
  try {
    const res = await fetch("api/ask", { method: "POST", headers: { "Content-Type": "application/json" },
      // How far the fan has watched: Ask can talk about today's match up to here, never beyond.
      body: JSON.stringify({ question, language: lang, history: past, clock_s: S.clock, fan_id: F.server ? fanId() : null }) });
    // Only the Halfspace server answers with JSON; a static host (or nothing) means Ask isn't running.
    if (!(res.headers.get("content-type") || "").includes("application/json")) throw new Error("offline");
    reply = await res.json();
  } catch (e) {
    reply = { error: true, answer: e.message === "offline" || e instanceof TypeError
      ? "Ask runs on the Halfspace server, where the AI agent looks answers up in the league data. This copy of the app is the match replay only. To ask questions, run uv run scripts/serve_web.py and open http://localhost:8080/#/ask."
      : `The question couldn't be answered (${e.message}). Try again in a moment.` };
  }
  S.thread.pop();
  S.thread.push({ a: reply.answer, lang: reply.lang || (reply.error ? "en" : lang), sources: reply.sources,
    checked: reply.checked, error: reply.error, blocked: reply.blocked, heldBack: reply.held_back,
    remembered: reply.remembered });
  drawThread(main);
  refreshAfterAsk(reply.remembered);
}

export function renderAsk(main, _S, about) {
  const m = about === "match" && S.clock > 0;
  main.innerHTML = `<div class="ask">
      <h1>${F.profile?.name ? `${esc(F.profile.name)}, ask` : "Ask"} ${m ? "about today's match" : "about the league"}</h1>
      ${F.profile?.memory ? `<p class="mem-note">Learning from what you say is on: only your club, players, style and topics. <a href="#/me">Manage</a></p>` : ""}
      <p class="lede">${m ? `You've watched up to ${S.clock >= S.data.match.end ? "full time" : "this minute"}. Ask about the goals, the players or the numbers; answers stop where you stopped watching.`
        : "Players, line-ups, injuries, fixtures, form, and today's match up to the minute you've watched, never beyond."} Answers come from the league's data and every number is checked before you see it.</p>
      <div class="suggest">${suggestions(about).map((q) => `<button class="chip">${esc(q)}</button>`).join("")}</div>
      <div class="thread" id="thread" aria-live="polite"></div>
    </div>
    <div class="composer"><form id="form">
      <label class="sr-only" for="q" style="position:absolute;left:-999px">Your question</label>
      <input id="q" name="q" dir="auto" autocomplete="off" placeholder="Ask a question" required>
      <select id="lang" aria-label="Answer language">${LANGS.map(([k, n]) => `<option value="${k}" ${S.lens.endsWith(`/${k}`) ? "selected" : ""}>${n}</option>`).join("")}</select>
      <button class="btn" type="submit">Ask</button>
    </form></div>`;
  drawThread(main);
  const input = main.querySelector("#q"), lang = main.querySelector("#lang");
  main.querySelectorAll(".chip").forEach((c) => c.addEventListener("click", () => ask(main, c.textContent, lang.value)));
  main.querySelector("#form").addEventListener("submit", (e) => {
    e.preventDefault();
    const q = input.value.trim();
    if (q) { input.value = ""; ask(main, q, lang.value); }
  });
}
