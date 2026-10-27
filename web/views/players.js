// Ratings (match centre): every player who has played so far, with his rating at the replay clock.
// Pick a player for his card: the rating's reasons, his numbers in this match and his heat map.
// Substitutes appear only once they have come on, so the list never gives away what happens later.
import { S } from "../app.js";
import { esc, crestImg, shirtSVG } from "../lib/util.js";
import { ratingAt, ratingBand, fmtRating } from "../lib/rating.js";
import { openPlayerCard, tickPlayerCard, POS } from "./playercard.js";

function onPitch(side) {
  return S.data.lineups[side].filter((p) => p.start || p.on_clock <= S.clock);
}

function row(p, side) {
  const sheet = S.data.players[p.id];
  const club = S.data.match[side];
  const rt = ratingAt(p.id);
  return `<li><button class="rrow" data-pid="${p.id}" aria-label="${esc(p.name)}: ${rt ? `rating ${fmtRating(rt.value)}` : "no rating yet"}. Open his card">
    <span class="ph">${sheet?.photo ? `<img src="${esc(sheet.photo)}" alt="" loading="lazy">` : shirtSVG(club.kit[0], club.kit[1], sheet?.num)}</span>
    <span class="nm"><b>${esc(p.name)}</b><small>${sheet?.num ?? ""} ${esc(POS[p.pos] || p.pos || "")}${p.start ? "" : ", came on"}</small></span>
    <span class="rt ${rt ? ratingBand(rt.value) : "none"}">${rt ? fmtRating(rt.value) : "–"}</span>
  </button></li>`;
}

function draw(main) {
  const d = S.data;
  const all = ["home", "away"].flatMap((side) => onPitch(side).map((p) => ({ p, side, rt: ratingAt(p.id) })))
    .filter((x) => x.rt).sort((a, b) => b.rt.value - a.rt.value);
  const top = all.slice(0, 3);
  main.querySelector("#best").innerHTML = S.clock <= 0
    ? `<p class="muted">Ratings start at kick-off. Press play in the match bar above.</p>`
    : top.map(({ p, side, rt }, i) => `<button class="best-card" data-pid="${p.id}" style="--team:var(--${side})">
        <span class="bc-rank cond">${i + 1}</span><span class="bc-name">${esc(p.name)}<small>${esc(d.match[side].name)}</small></span>
        <span class="rt ${ratingBand(rt.value)}">${fmtRating(rt.value)}</span></button>`).join("");
  for (const side of ["home", "away"]) {
    main.querySelector(`#r-${side}`).innerHTML = onPitch(side).map((p) => row(p, side)).join("");
  }
  main.querySelectorAll("[data-pid]").forEach((b) => b.addEventListener("click", () => {
    location.hash = `#/match/ratings/${b.dataset.pid}`;
  }));
}

export function renderPlayers(main) {
  const d = S.data;
  main.innerHTML = `<div class="ratings-page">
    <header class="rp-head"><h1 class="cond">Player ratings</h1>
      <p class="lede">Live, at the minute you're watching. Every player starts at 6.0 and every action moves him up or down. Pick a player to see why.</p></header>
    <section class="best" aria-label="Best rated so far"><h2>Best so far</h2><div id="best" class="best-row"></div></section>
    <div class="rcols">${["home", "away"].map((side) => `<section style="--team:var(--${side})">
      <h2>${crestImg(d.match[side], "crest")}<span>${esc(d.match[side].name)}</span></h2><ul class="rlist" id="r-${side}"></ul></section>`).join("")}</div>
  </div>`;
  tickPlayers.m = Math.floor(S.clock / 60);
  draw(main);
  if (S.playerId) {
    openPlayerCard(S.playerId, {
      onClose: () => { S.playerId = null; if (location.hash.startsWith("#/match/ratings/")) location.hash = "#/match/ratings"; },
    });
  }
}

export function tickPlayers(main) {
  // Ratings move about once a match minute.
  const m = Math.floor(S.clock / 60);
  if (m !== tickPlayers.m) {
    tickPlayers.m = m;
    draw(main);
  }
  tickPlayerCard();
}
