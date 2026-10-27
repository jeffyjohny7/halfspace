// Before kick-off: the scout's brief as a scrolling story.
import { S, setClock, saveLens, render } from "../app.js";
import { esc, pct, num, shirtSVG, LANG_OF, langAttrs, crestImg } from "../lib/util.js";
import { lensPicker, bindLensPicker, variantFor } from "./match.js";

const STATUS = { injured: "Injured", suspended: "Suspended", doubtful: "Doubtful" };

function longDate(iso) {
  const d = new Date(`${iso}T15:00:00`);
  return d.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
}

function absentees(side) {
  const d = S.data, club = d.match[side];
  const out = d.team_news[side].out;
  if (!out.length) return `<p class="lede">Full squad available.</p>`;
  return `<div class="absent">${out.map((x) => {
    const p = d.players[x.id];
    const back = x.expected_return ? `back around ${new Date(x.expected_return).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}`
      : x.matches_remaining ? `${x.matches_remaining} match${x.matches_remaining > 1 ? "es" : ""} to serve` : "";
    return `<div class="shirt ${x.status === "doubtful" ? "" : "out"}">
      ${shirtSVG(club.kit[0], club.kit[1], p?.num, x.status !== "doubtful")}
      <div class="n">${esc(x.name)}</div>
      <div class="r">${esc(STATUS[x.status] || x.status)}: ${esc(x.reason)}${back ? `, ${esc(back)}` : ""}${x.regular ? ". Regular starter" : ""}</div>
    </div>`;
  }).join("")}</div>`;
}

function storyItems() {
  const d = S.data;
  const pre = d.cues.filter((c) => c.phase === "prematch");
  const intro = pre.find((c) => c.kind === "brief_intro");
  const lines = pre.filter((c) => c.kind === "storyline");
  if (lines.length) return { intro, lines: lines.map((c) => ({ cue: c, conf: c.overlay?.data?.confidence })) };
  return { intro: null, lines: (d.brief?.storylines || []).map((s) => ({ text: s, conf: s.confidence })) };
}

function compare(p) {
  const rate = p.kind === "rate_at_most";
  const fmt = (v) => (v == null ? "–" : rate ? pct(v) : p.measure.includes("xg") ? num(v) : Number(v).toFixed(1));
  const max = Math.max(p.expected || 0, p.average || 0, p.confirm_at || 0) * 1.15 || 1;
  const colour = p.subject === S.data.match.home.name || S.data.lineups.home.some((x) => x.name === p.subject) ? "var(--home)" : "var(--away)";
  const row = (label, v, c) => `<span>${label}</span><div class="track"><span style="width:${(v / max) * 100}%;background:${c}"></span></div><b>${fmt(v)}</b>`;
  return `<div class="compare">${row(esc(p.subject), p.expected || 0, colour)}${row(rate ? "Average player" : "League average", p.average || 0, "var(--chalk-3)")}</div>`;
}

export function renderBefore(main) {
  const d = S.data, { home, away } = d.match;
  const lang = LANG_OF(S.lens);
  const { intro, lines } = storyItems();
  const introV = intro ? variantFor(intro, S.lens) : null;
  const headline = introV ? introV.headline : d.brief?.headline;
  const sub = introV ? introV.body : d.brief?.tactical_preview;
  const euro = Object.entries(d.match.midweek_europe || {}).filter(([, v]) => v).map(([club, v]) =>
    `${club} played in the ${v.competition} ${v.days_before} days ago.`).join(" ");
  main.innerHTML = `
    <div class="story">
      <section class="hero">
        <div class="bg" style="background-image:url('assets/hero-stadium.webp')" id="herobg"></div>
        <div class="hero-inner">
          <h1 class="fixture"><span>${crestImg(home, "fx-crest")}${esc(home.name)}</span><span class="v">against</span><span>${crestImg(away, "fx-crest")}${esc(away.name)}</span></h1>
          <p class="fixture-meta">Round ${d.match.round} of the Crown League, ${esc(longDate(d.match.date))}, ${esc(d.match.stadium)}.
            ${home.position ? `${esc(home.short === home.name ? home.name : home.name.split(" ")[0])} are ${ordinal(home.position)}, ` : ""}${away.position ? `${esc(away.name.split(" ")[0])} ${ordinal(away.position)}.` : ""}
            ${esc(euro)}</p>
          <div class="cta-row">
            <button class="btn live" id="watch">Watch the match</button>
            <div class="viewas"><span class="lens" id="lens">${lensPicker(d)}</span></div>
          </div>
        </div>
      </section>

      <section class="chapter">
        <div><h2 ${langAttrs(introV ? introV.hl : "en")}>${esc(headline || "The scout's view")}</h2>
          ${sub ? `<p class="lede" ${langAttrs(introV ? introV.bl : "en")}>${esc(sub)}</p>` : ""}</div>
        <div class="storylines">
          ${lines.map((l) => {
            if (l.cue) {
              const v = variantFor(l.cue, S.lens);
              return `<article class="storyline"><h3 ${langAttrs(v.hl)}>${esc(v.headline)}</h3><p ${langAttrs(v.bl)}>${esc(v.body)}</p>
                <div class="conf">${l.conf === "high" ? "Strong evidence" : "One to watch"}</div></article>`;
            }
            return `<article class="storyline"><h3>${esc(l.text.title)}</h3><p>${esc(l.text.text)}</p>
              <div class="conf">${l.conf === "high" ? "Strong evidence" : "One to watch"}</div></article>`;
          }).join("") || `<p class="lede">No brief yet. Run the broadcast to write one.</p>`}
        </div>
      </section>

      <section class="chapter">
        <div><h2>Team news</h2><p class="lede">${esc(d.team_news.home.summary ? `${home.name}: ${d.team_news.home.summary}.` : "")} ${esc(d.team_news.away.summary ? `${away.name}: ${d.team_news.away.summary}.` : "")}</p></div>
        <div>
          <h3 class="section-title">${esc(home.name)}</h3>${absentees("home")}
          <h3 class="section-title" style="margin-top:28px">${esc(away.name)}</h3>${absentees("away")}
        </div>
      </section>

      <section class="chapter">
        <div><h2>Checked live during the match</h2>
          <p class="lede">Each of these comes from the scouting data. During the match you'll see whether it happens.</p></div>
        <div class="checks">
          ${d.predictions.map((p) => `<div class="check-card"><p>${esc(p.text)}</p>${compare(p)}</div>`).join("") || `<p class="lede">No live checks for this match.</p>`}
        </div>
      </section>

      <section class="chapter">
        <div><h2>Probable line-ups</h2><p class="lede">From each side's last league match, with injured and suspended players replaced.</p></div>
        <div class="xi-pair">
          ${["home", "away"].map((side) => {
            const xi = d.probable[side] || {}, club = d.match[side];
            return `<div class="xi"><h3>${crestImg(club, "crest")} ${esc(club.name)} <span style="color:var(--chalk-3);font-weight:400">${esc(xi.formation || "")}</span></h3>
              <ol>${(xi.players || []).map((p) => {
                const sheet = d.players[p.player_id];
                return `<li><span class="num">${sheet?.num ?? ""}</span><a href="#/player/${p.player_id}">${esc(p.name)}</a><span class="pos">${esc(p.slot)}${p.doubtful ? ", doubtful" : ""}</span></li>`;
              }).join("")}</ol>
              ${(xi.changes || []).map((c) => `<p class="changes">${esc(c.in)} expected in for ${esc(c.out)} (${esc(c.reason)}).</p>`).join("")}
            </div>`;
          }).join("")}
        </div>
      </section>
    </div>`;
  main.querySelectorAll(".xi h3 .crest").forEach((img) => { img.style.width = "26px"; img.style.height = "26px"; img.style.verticalAlign = "-7px"; });
  const bg = main.querySelector("#herobg");
  const probe = new Image();
  probe.onerror = () => bg.classList.add("fallback");
  probe.src = "assets/hero-stadium.webp";
  main.querySelector("#watch").addEventListener("click", () => {
    if (S.clock >= d.match.end) setClock(0);
    S.playing = true;
    location.hash = "#/match/live";
  });
  bindLensPicker(main.querySelector("#lens"), render);
}

function ordinal(n) {
  const s = ["th", "st", "nd", "rd"], v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}
