// My Halfspace: what Halfspace remembers about the fan, all of it visible and deletable, plus alerts.
import { esc } from "../lib/util.js";
import { L, club, crest, seasonFile } from "../lib/league.js";
import { F, fanId, loadFan, saveFan, forget, forgetEverything, askPermission } from "../lib/fan.js";

const LANGS = [["en", "English"], ["es", "Español"], ["ar", "العربية"], ["hi", "हिन्दी"], ["ml", "മലയാളം"]];
const INTERESTS = [["tactics", "Tactics"], ["set_pieces", "Set pieces"], ["stats", "Stats and xG"],
  ["goalkeepers", "Goalkeepers"], ["young_players", "Young players"], ["team_news", "Injuries and team news"]];
const KIND = { club: "Club", player: "Player", style: "Style", interest: "Topic" };

export async function renderMe(main) {
  if (F.server === null) await loadFan();
  if (!F.server) {
    main.innerHTML = `<div class="page"><header class="page-head"><div><h1 class="cond">My Halfspace</h1>
      <p class="lede">Your club, your players and your alerts live on the Halfspace server. This copy of the app is the
      replay only. Run <code>uv run scripts/serve_web.py</code> and open <code>http://localhost:8080/#/me</code>.</p></div></header></div>`;
    return;
  }
  const p = F.profile || { name: "", memory: false, alerts: true, language: "en", facts: [], players: [], interests: [] };
  const season = L.data.current_season;
  const clubs = L.data.season[season].tables["1"].rows.map((r) => r.club).sort((a, b) => club(a).name.localeCompare(club(b).name));
  const players = await seasonFile(season, "players").catch(() => ({}));
  const perm = "Notification" in window ? Notification.permission : "unsupported";

  main.innerHTML = `<div class="page me">
    <header class="page-head"><div><p class="crumb">Your profile</p>
      <h1 class="cond">${p.name ? `${esc(p.name)}’s Halfspace` : "My Halfspace"}</h1>
      <p class="lede">Follow a club and a few players to get alerts during the match and answers in Ask that start from them.
        Halfspace keeps only what you put here or tell it, and you can delete any of it.</p></div></header>

    <div class="me-grid">
      <section class="me-card">
        <h2>You</h2>
        <label class="fld"><span>First name</span><input id="name" maxlength="24" autocomplete="given-name" value="${esc(p.name || "")}" placeholder="What should we call you?"></label>
        <label class="fld"><span>Alerts and answers in</span><select id="lang">${LANGS.map(([k, n]) => `<option value="${k}" lang="${k}" ${p.language === k ? "selected" : ""}>${n}</option>`).join("")}</select></label>
        <div class="fld"><span>Style</span><div class="segs" role="group" aria-label="Style">
          ${[["", "No preference"], ["casual", "Simple words"], ["analyst", "Detailed stats"]].map(([k, n]) => `<button type="button" class="seg" data-style="${k}" aria-pressed="${(p.style || "") === k}">${n}</button>`).join("")}</div></div>
      </section>

      <section class="me-card">
        <h2>Your club and players</h2>
        <label class="fld"><span>Club</span><select id="club"><option value="">No club yet</option>
          ${clubs.map((c) => `<option value="${c}" ${p.club === c ? "selected" : ""}>${esc(club(c).name)}</option>`).join("")}</select></label>
        <div class="fld"><span>Players (up to 5)</span>
          <ul class="chips" id="players">${(p.players || []).map((x) => `<li><span>${esc(x.name)}</span><button type="button" data-unfollow="${x.id}" aria-label="Stop following ${esc(x.name)}">×</button></li>`).join("") || `<li class="muted">None yet</li>`}</ul>
          <div class="add-player"><input id="padd" list="plist" placeholder="Add a player" autocomplete="off">
          <datalist id="plist">${Object.entries(players).filter(([, x]) => x.minutes > 0).map(([, x]) => `<option value="${esc(x.name)}">${esc(club(x.club).name)}</option>`).join("")}</datalist>
          <button type="button" class="btn sm" id="padd-btn">Follow</button></div></div>
        <div class="fld"><span>Topics you enjoy</span><div class="tags">${INTERESTS.map(([k, n]) => `<button type="button" class="tag-btn" data-int="${k}" aria-pressed="${(p.interests || []).includes(k)}">${n}</button>`).join("")}</div></div>
      </section>

      <section class="me-card">
        <h2>Alerts</h2>
        <label class="switch"><input type="checkbox" id="alerts" ${p.alerts !== false ? "checked" : ""}><span>Alerts during today's match</span></label>
        <p class="note">Goals, injuries, cards and the result for your club and players, written for you, when your replay reaches them. Never more than eight in a match.</p>
        ${perm === "granted" ? `<p class="note">Phone-style notifications are on for this browser when the app is in the background.</p>`
          : perm === "unsupported" ? "" : `<button type="button" class="btn ghost sm" id="perm">Also show them as system notifications</button>`}
      </section>

      <section class="me-card">
        <h2>Learning from Ask</h2>
        <label class="switch"><input type="checkbox" id="memory" ${p.memory ? "checked" : ""}><span>Remember the football preferences I mention in Ask</span></label>
        <p class="note">A small agent reads your questions for your club, your players, the style you like and topics you enjoy. Nothing else is kept: not your health, family, work, location or anything personal.</p>
      </section>
    </div>

    <section class="sec"><h2>What Halfspace remembers</h2>
      ${p.facts?.length ? `<ul class="facts">${p.facts.map((f) => `<li>
        <span class="f-kind">${esc(KIND[f.kind] || f.kind)}</span>
        <span class="f-txt"><b>${esc(f.label)}</b><small>${f.said === "Set in My Halfspace" ? "You set this here" : `From Ask: “${esc(f.said)}”`}</small></span>
        <button type="button" class="btn ghost sm" data-forget="${esc(f.id)}">Delete</button></li>`).join("")}</ul>`
        : `<p class="muted">Nothing yet.${p.name ? ` Only your first name, ${esc(p.name)}.` : ""}</p>`}
      ${F.profile ? `<div class="cta-row"><button type="button" class="btn ghost sm danger" id="wipe">Forget everything and start again</button></div>` : ""}
      <p class="note">Stored on this Halfspace server under a random id kept in your browser (${esc(fanId().slice(0, 8))}…), never sent anywhere else.</p>
    </section>
  </div>`;

  const save = async (patch) => {
    try { await saveFan(patch); } catch (e) { flash(main, `Couldn't save (${e.message}).`); return; }
    renderMe(main);
  };
  main.querySelector("#name").addEventListener("change", (e) => save({ name: e.target.value }));
  main.querySelector("#lang").addEventListener("change", (e) => save({ language: e.target.value }));
  main.querySelector("#club").addEventListener("change", (e) => save({ club: e.target.value || null }));
  main.querySelector("#alerts").addEventListener("change", (e) => save({ alerts: e.target.checked }));
  main.querySelector("#memory").addEventListener("change", (e) => save({ memory: e.target.checked }));
  main.querySelectorAll("[data-style]").forEach((b) => b.addEventListener("click", () => save({ style: b.dataset.style || null })));
  main.querySelectorAll("[data-int]").forEach((b) => b.addEventListener("click", () => {
    const now = new Set(p.interests || []);
    if (now.has(b.dataset.int)) now.delete(b.dataset.int); else now.add(b.dataset.int);
    save({ interests: [...now] });
  }));
  const ids = (p.players || []).map((x) => x.id);
  main.querySelectorAll("[data-unfollow]").forEach((b) => b.addEventListener("click", () =>
    save({ players: ids.filter((x) => x !== b.dataset.unfollow) })));
  const addPlayer = () => {
    const name = main.querySelector("#padd").value.trim();
    const hit = Object.entries(players).find(([, x]) => x.name.toLowerCase() === name.toLowerCase());
    if (!hit) { flash(main, "Pick a player from the list."); return; }
    if (ids.length >= 5) { flash(main, "You can follow up to five players."); return; }
    save({ players: [...ids, hit[0]] });
  };
  main.querySelector("#padd-btn").addEventListener("click", addPlayer);
  main.querySelector("#padd").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); addPlayer(); } });
  main.querySelectorAll("[data-forget]").forEach((b) => b.addEventListener("click", async () => {
    await forget(b.dataset.forget); renderMe(main);
  }));
  main.querySelector("#perm")?.addEventListener("click", async () => { await askPermission(); renderMe(main); });
  const wipe = main.querySelector("#wipe");
  wipe?.addEventListener("click", async () => {
    if (wipe.dataset.sure !== "1") { wipe.dataset.sure = "1"; wipe.textContent = "Click again to delete it all"; return; }
    await forgetEverything(); await loadFan(); renderMe(main);
  });
}

function flash(main, text) {
  let el = main.querySelector(".me-flash");
  if (!el) { el = document.createElement("p"); el.className = "me-flash"; el.setAttribute("role", "status"); main.querySelector(".me-grid").before(el); }
  el.textContent = text;
}

// A short "for you" line for other pages (home, ask).
export function forYou() {
  const p = F.profile;
  if (!p || (!p.name && !p.club)) return "";
  const fx = p.club ? L.data.fixtures.find((f) => f.home === p.club || f.away === p.club) : null;
  const live = fx && fx.id === L.data.showcase;
  return `<a class="for-you" href="#/me">
    ${p.club ? crest(p.club, "c") : ""}<span>${p.name ? `<b>${esc(p.name)}</b>, ` : ""}${p.club
      ? `${esc(club(p.club).name)} ${fx ? `${live ? "play live" : "play"} ${fx.home === p.club ? "at home to" : "away at"} ${esc(club(fx.home === p.club ? fx.away : fx.home).name)}, ${esc(fx.ko)}` : "aren't playing this round"}.${p.alerts ? " Alerts are on." : ""}`
      : "follow a club to get alerts."}</span><span class="fy-edit">My Halfspace</span></a>`;
}
