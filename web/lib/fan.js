// The fan: a profile on the Halfspace server (My Halfspace) and personal alerts during the match.
// The browser keeps only a random id; the server keeps what the fan chose to share, and the fan can
// see and delete all of it. Alerts are released only when the fan's replay reaches their moment.
import { esc } from "./util.js";

const KEY = "halfspace.fan";
export const F = {
  id: null,
  profile: null,       // the server's copy; null until loaded or if there is none
  server: null,        // true: the Halfspace server answers; false: a static copy of the app
  alerts: [],          // received, oldest first
  seen: new Set(),
  unread: 0,
  lastClock: -1,
  listeners: new Set(),
};

function newId() {
  try { return crypto.randomUUID(); } catch { return `fan-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`; }
}

export function fanId() {
  if (F.id) return F.id;
  try { F.id = localStorage.getItem(KEY); } catch { F.id = null; }
  if (!F.id || !/^[A-Za-z0-9_-]{8,64}$/.test(F.id)) {
    F.id = newId();
    try { localStorage.setItem(KEY, F.id); } catch { /* private mode: a fresh id each visit */ }
  }
  return F.id;
}

const changed = () => F.listeners.forEach((fn) => { try { fn(); } catch { /* a view went away */ } });
export const onFanChange = (fn) => { F.listeners.add(fn); return () => F.listeners.delete(fn); };

async function call(path, body) {
  const res = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  if (!(res.headers.get("content-type") || "").includes("application/json")) throw new Error("offline");
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `${res.status}`);
  return data;
}

export async function loadFan() {
  try {
    const d = await call(`api/fan?id=${encodeURIComponent(fanId())}`);
    F.server = true;
    F.profile = d.profile;
  } catch {
    F.server = false;
    F.profile = null;
  }
  changed();
  return F.profile;
}

export async function saveFan(patch) {
  const d = await call("api/fan", { fan_id: fanId(), ...patch });
  F.profile = d.profile;
  F.lastClock = -1;              // a new club or player: look again for alerts
  changed();
  return F.profile;
}

export async function forget(factId) {
  const d = await call("api/fan/forget", { fan_id: fanId(), fact_id: factId });
  F.profile = d.profile;
  changed();
}

export async function forgetEverything() {
  await call("api/fan/forget", { fan_id: fanId(), everything: true });
  F.profile = null;
  F.alerts = []; F.seen.clear(); F.unread = 0;
  try { localStorage.removeItem(KEY); } catch { /* ignore */ }
  F.id = null;
  changed();
}

// Merge what Ask learned into the local copy (the server already saved it).
export async function refreshAfterAsk(remembered) {
  if (remembered?.length) await loadFan();
}

// ------------------------------------------------------------------ alerts

let polling = false;
export async function pollAlerts(S) {
  if (polling || !F.server || !F.profile?.alerts || !S.data) return;
  const clock = Math.floor(S.clock);
  if (clock === F.lastClock) return;
  polling = true;
  try {
    const d = await call("api/alerts", { fan_id: fanId(), clock_s: clock });
    F.lastClock = clock;
    const fresh = (d.alerts || []).filter((a) => !F.seen.has(a.id));
    for (const a of fresh) {
      F.seen.add(a.id);
      F.alerts.push(a);
      F.unread += 1;
    }
    // A jump in the replay can release several at once: show the latest and say how many more are in the tray.
    if (fresh.length > 2) announce(fresh[fresh.length - 1], fresh.length - 1);
    else fresh.forEach((a) => announce(a));
    if (fresh.length) changed();
  } catch { /* the server went away: try again on the next tick */ }
  polling = false;
}

export function markRead() { F.unread = 0; changed(); }

function announce(a, more = 0) {
  toast(a, more);
  try {
    if (document.hidden && "Notification" in window && Notification.permission === "granted") {
      new Notification(a.title, { body: a.body, tag: a.id, lang: a.lang || "en" });
    }
  } catch { /* not allowed here */ }
}

export async function askPermission() {
  if (!("Notification" in window)) return "unsupported";
  try { return await Notification.requestPermission(); } catch { return "denied"; }
}

function toast(a, more = 0) {
  let box = document.getElementById("toasts");
  if (!box) {
    box = document.createElement("div");
    box.id = "toasts";
    box.className = "toasts";
    box.setAttribute("aria-live", "polite");
    document.body.appendChild(box);
  }
  const el = document.createElement("a");
  el.className = `toast ${a.tone || "neutral"}`;
  el.href = more ? "#alerts" : "#/match/live";
  el.innerHTML = `<span class="t-min cond">${a.minute ? `${a.minute}′` : "Now"}</span>
    <span class="t-txt"><b lang="${esc(a.lang || "en")}">${esc(a.title)}</b><span lang="${esc(a.lang || "en")}">${esc(a.body)}</span>
    ${more ? `<small class="t-more">${more} earlier ${more === 1 ? "alert" : "alerts"} in the bell</small>` : ""}</span>`;
  if (more) el.addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); el.remove(); document.getElementById("bell")?.click(); });
  box.appendChild(el);
  while (box.children.length > 3) box.firstElementChild.remove();
  setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 400); }, 9000);
}
