// Small interactive SVG charts for the analyst view: a points race and a scatter.
import { esc } from "./util.js";

const nice = (max, steps = 5) => {
  const raw = max / steps;
  const mag = 10 ** Math.floor(Math.log10(raw || 1));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) || raw;
  return { step, top: Math.ceil(max / step) * step };
};

// series: [{ id, label, colour, values: [y at x=0..n] }]; highlight: ids drawn strong at rest.
export function raceChart(series, { highlight = [], xLabel = "Round", yLabel = "Points" } = {}) {
  const W = 960, H = 340, m = { l: 40, r: 120, t: 14, b: 34 };
  const n = Math.max(...series.map((s) => s.values.length)) - 1;
  const ymax = Math.max(1, ...series.flatMap((s) => s.values));
  const { step, top } = nice(ymax);
  const x = (i) => m.l + (i / Math.max(1, n)) * (W - m.l - m.r);
  const y = (v) => H - m.b - (v / top) * (H - m.t - m.b);
  const grid = [];
  for (let v = 0; v <= top; v += step) {
    grid.push(`<line class="g" x1="${m.l}" x2="${W - m.r}" y1="${y(v)}" y2="${y(v)}"/><text class="t" x="${m.l - 8}" y="${y(v) + 4}" text-anchor="end">${v}</text>`);
  }
  const xt = [];
  const every = n > 20 ? 5 : n > 10 ? 2 : 1;
  for (let i = 0; i <= n; i += every) xt.push(`<text class="t" x="${x(i)}" y="${H - m.b + 18}" text-anchor="middle">${i}</text>`);
  // End labels, nudged apart so they don't overlap.
  const ends = series.map((s) => ({ s, yy: y(s.values[s.values.length - 1]) })).sort((a, b) => a.yy - b.yy);
  for (let i = 1; i < ends.length; i++) if (ends[i].yy - ends[i - 1].yy < 12) ends[i].yy = ends[i - 1].yy + 12;
  const lines = series.map((s) => {
    const pts = s.values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
    const on = highlight.includes(s.id);
    return `<g class="series${on ? " on" : ""}" data-id="${esc(s.id)}" style="--c:${s.colour}">
      <polyline points="${pts}"/><polyline class="hit" points="${pts}"/></g>`;
  }).join("");
  const labels = ends.map(({ s, yy }) => `<text class="end${highlight.includes(s.id) ? " on" : ""}" data-id="${esc(s.id)}" x="${W - m.r + 8}" y="${yy + 4}" style="--c:${s.colour}">${esc(s.label)} ${s.values[s.values.length - 1]}</text>`).join("");
  return `<figure class="chart race">
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(yLabel)} by ${esc(xLabel.toLowerCase())} for every club">
      ${grid.join("")}${xt.join("")}
      <text class="t axis" x="${(m.l + W - m.r) / 2}" y="${H - 4}" text-anchor="middle">${esc(xLabel)}</text>
      ${lines}${labels}
      <line class="cursor" x1="0" x2="0" y1="${m.t}" y2="${H - m.b}" hidden/>
    </svg>
    <figcaption class="chart-tip" hidden></figcaption>
  </figure>`;
}

export function bindRace(root, series, onPick) {
  const fig = root.querySelector(".chart.race");
  if (!fig) return;
  const svg = fig.querySelector("svg");
  const tip = fig.querySelector(".chart-tip");
  const set = (id, on) => svg.querySelectorAll(`[data-id="${CSS.escape(id)}"]`).forEach((el) => el.classList.toggle("hover", on));
  svg.querySelectorAll(".series, text.end").forEach((g) => {
    g.addEventListener("pointerenter", () => { svg.classList.add("focus"); set(g.dataset.id, true); });
    g.addEventListener("pointerleave", () => { svg.classList.remove("focus"); set(g.dataset.id, false); tip.hidden = true; });
    g.addEventListener("click", () => onPick?.(g.dataset.id));
    g.addEventListener("pointermove", (e) => {
      const s = series.find((x) => x.id === g.dataset.id);
      const box = svg.getBoundingClientRect();
      const n = s.values.length - 1;
      const px = (e.clientX - box.left) / box.width * 960;
      const i = Math.max(0, Math.min(n, Math.round(((px - 40) / (960 - 160)) * n)));
      tip.hidden = false;
      tip.textContent = `${s.label}: ${s.values[i]} points after round ${i}`;
      tip.style.left = `${e.clientX - fig.getBoundingClientRect().left + 12}px`;
      tip.style.top = `${e.clientY - fig.getBoundingClientRect().top - 30}px`;
    });
  });
}

// points: [{ id, x, y, r?, colour, label, sub }]
export function scatter(points, { xLabel, yLabel, diagonal = false, href } = {}) {
  const W = 960, H = 400, m = { l: 46, r: 20, t: 16, b: 44 };
  const xs = nice(Math.max(1, ...points.map((p) => p.x)));
  const ys = nice(Math.max(1, ...points.map((p) => p.y)));
  const top = diagonal ? Math.max(xs.top, ys.top) : null;
  const X = diagonal ? { step: Math.max(xs.step, ys.step), top } : xs;
  const Y = diagonal ? { step: Math.max(xs.step, ys.step), top } : ys;
  const x = (v) => m.l + (v / X.top) * (W - m.l - m.r);
  const y = (v) => H - m.b - (v / Y.top) * (H - m.t - m.b);
  const g = [];
  for (let v = 0; v <= Y.top + 1e-9; v += Y.step) g.push(`<line class="g" x1="${m.l}" x2="${W - m.r}" y1="${y(v)}" y2="${y(v)}"/><text class="t" x="${m.l - 8}" y="${y(v) + 4}" text-anchor="end">${+v.toFixed(1)}</text>`);
  for (let v = 0; v <= X.top + 1e-9; v += X.step) g.push(`<text class="t" x="${x(v)}" y="${H - m.b + 18}" text-anchor="middle">${+v.toFixed(1)}</text>`);
  const diag = diagonal ? `<line class="diag" x1="${x(0)}" y1="${y(0)}" x2="${x(top)}" y2="${y(top)}"/>
    <text class="t diag-l" x="${x(top * 0.97)}" y="${y(top * 0.97) - 8}" text-anchor="end">scoring exactly the chances</text>` : "";
  const dots = points.map((p) => {
    const tag = href ? "a" : "g";
    return `<${tag} class="dot" ${href ? `href="${href(p)}"` : ""} data-label="${esc(p.label)}" data-sub="${esc(p.sub || "")}" style="--c:${p.colour}">
      <circle cx="${x(p.x).toFixed(1)}" cy="${y(p.y).toFixed(1)}" r="${p.r || 5}"/>
      ${p.tag ? `<text class="tag" x="${(x(p.x) + (p.r || 5) + 4).toFixed(1)}" y="${(y(p.y) + 4).toFixed(1)}">${esc(p.tag)}</text>` : ""}</${tag}>`;
  }).join("");
  return `<figure class="chart scatter">
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(yLabel)} against ${esc(xLabel)}">
      ${g.join("")}${diag}
      <text class="t axis" x="${(m.l + W - m.r) / 2}" y="${H - 6}" text-anchor="middle">${esc(xLabel)}</text>
      <text class="t axis" transform="translate(14 ${(m.t + H - m.b) / 2}) rotate(-90)" text-anchor="middle">${esc(yLabel)}</text>
      ${dots}
    </svg>
    <figcaption class="chart-tip" hidden></figcaption>
  </figure>`;
}

export function bindScatter(root) {
  const fig = root.querySelector(".chart.scatter");
  if (!fig) return;
  const tip = fig.querySelector(".chart-tip");
  fig.querySelectorAll(".dot").forEach((d) => {
    const show = (e) => {
      tip.hidden = false;
      tip.innerHTML = `<b>${esc(d.dataset.label)}</b><br>${esc(d.dataset.sub)}`;
      const r = fig.getBoundingClientRect();
      const c = d.querySelector("circle").getBoundingClientRect();
      tip.style.left = `${c.left - r.left + 14}px`;
      tip.style.top = `${c.top - r.top - 44}px`;
    };
    d.addEventListener("pointerenter", show);
    d.addEventListener("focus", show);
    d.addEventListener("pointerleave", () => { tip.hidden = true; });
    d.addEventListener("blur", () => { tip.hidden = true; });
  });
}

// Horizontal percentile bar: value against the league (0-100), with the median tick at 50.
export function pctBar(pct, { better = "high", colour = "var(--gold)" } = {}) {
  const good = better === "low" ? 100 - pct : pct;
  const tone = better == null ? "neutral" : good >= 80 ? "great" : good >= 60 ? "good" : good <= 20 ? "poor" : "ok";
  return `<span class="pbar ${tone}" style="--p:${Math.max(2, Math.min(100, pct))}%;--c:${colour}"><i></i><b></b></span>`;
}

// Simple vertical bars (e.g. goals by 15-minute spell). values: [{ label, a, b? }]
export function spellBars(values, { a = "For", b = "Against", ca = "var(--gold)", cb = "var(--chalk-3)" } = {}) {
  const max = Math.max(1, ...values.flatMap((v) => [v.a, v.b ?? 0]));
  return `<div class="spells" role="img" aria-label="${esc(a)} and ${esc(b)} by match period">
    ${values.map((v) => `<div class="spell">
      <div class="cols"><span style="height:${(v.a / max) * 100}%;background:${ca}" title="${esc(a)}: ${v.a}"><em>${v.a}</em></span>
      ${v.b != null ? `<span style="height:${(v.b / max) * 100}%;background:${cb}" title="${esc(b)}: ${v.b}"><em>${v.b}</em></span>` : ""}</div>
      <small>${esc(v.label)}</small></div>`).join("")}
  </div>
  <div class="spell-key"><span><i style="background:${ca}"></i>${esc(a)}</span>${values[0]?.b != null ? `<span><i style="background:${cb}"></i>${esc(b)}</span>` : ""}</div>`;
}
