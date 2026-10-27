// Where the live match stands at the replay clock, for the hub (home page, match cards, match bar).
import { minuteLabel, countUpTo } from "./util.js";

export function liveState(S) {
  const d = S.data;
  if (!d) return { status: "pre", score: [0, 0], label: "" };
  const end = d.match.end;
  const clock = S.clock;
  let h = 0, a = 0;
  for (const g of d.moments) {
    if (g.type !== "goal" || g.clock > clock) continue;
    [h, a] = g.facts.score_after.split("-").map(Number);
  }
  if (clock <= 0) return { status: "pre", score: [0, 0], label: "Kick-off 12:30" };
  if (clock >= end) return { status: "ft", score: [h, a], label: "Full time" };
  const p1 = d.match.periods[0];
  if (clock >= p1.end && clock < d.match.periods[1].start) return { status: "ht", score: [h, a], label: "Half-time" };
  const n = countUpTo(d.events, clock, (e) => e[0]);
  const minute = n ? d.events[n - 1][1] : 0;
  return { status: "live", score: [h, a], label: minuteLabel(minute, clock > p1.end ? 2 : 1) };
}
