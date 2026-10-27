// Match ratings in the app: add up a player's rated actions (from analytics/rating.py) up to the replay clock.
import { S } from "../app.js";

const TOUCH = 3;   // index of "counts as a touch" in rating_scale.actions rows

export function playedBy(pid, clock) {
  const lu = [...S.data.lineups.home, ...S.data.lineups.away].find((x) => x.id === pid);
  return !!lu && lu.on_clock != null && lu.on_clock <= clock;
}

// { value, reasons: [{label, count, change}], stats } or null if he hasn't played by then.
export function ratingAt(pid, clock = S.clock) {
  const d = S.data, p = d.players[pid], scale = d.rating_scale;
  if (!p || !p.acts || !scale || clock <= 0 || !playedBy(pid, clock)) return null;
  const n = scale.actions.map(() => 0), ch = scale.actions.map(() => 0);
  let sum = 0;
  for (const [c, k, delta] of p.acts) {
    if (c > clock) break;
    sum += delta; n[k] += 1; ch[k] += delta;
  }
  const value = Math.min(scale.high, Math.max(scale.low, scale.base + sum));
  const reasons = scale.actions.map((a, k) => ({ label: a[1], count: n[k], change: ch[k] }))
    .filter((x) => Math.abs(x.change) >= 0.005).sort((a, b) => Math.abs(b.change) - Math.abs(a.change));
  const c = Object.fromEntries(scale.actions.map((a, k) => [a[0], n[k]]));
  const sumOf = (...ks) => ks.reduce((t, k) => t + (c[k] || 0), 0);
  const stats = {
    goals: sumOf("goal", "pen_goal"), assists: c.assist || 0, key_passes: sumOf("key_pass", "assist"),
    shots: sumOf("goal", "pen_goal", "shot_on", "shot_off", "shot_blk"), on_target: sumOf("goal", "pen_goal", "shot_on"),
    passes: sumOf("pass_ft", "pass_ok", "pass_bad"), accurate: sumOf("pass_ft", "pass_ok"), misplaced: c.pass_bad || 0,
    touches: scale.actions.reduce((t, a, k) => t + (a[TOUCH] ? n[k] : 0), 0),
    dribbles: c.drb_ok || 0, dribbles_tried: sumOf("drb_ok", "drb_bad"), lost: c.lost || 0,
    tackles: c.tackle || 0, interceptions: c.intercept || 0, clearances: c.clear || 0, blocks: c.block || 0,
    recoveries: c.recover || 0, headers_won: c.air_won || 0, headers: sumOf("air_won", "air_lost"),
    saves: c.save || 0, fouls: c.foul || 0, yellow: c.yellow || 0, red: c.red || 0,
  };
  return { value, reasons, stats };
}

export const ratingBand = (v) => (v >= 8 ? "great" : v >= 7 ? "good" : v >= 6 ? "ok" : "poor");
export const fmtRating = (v) => (v == null ? "–" : v.toFixed(1));
export const fmtChange = (x) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(2)}`;
