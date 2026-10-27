// Heat maps for the player card: soft blobs on a canvas, coloured pale yellow to red.
// Coordinates are in the player's attacking frame (x 0-105 toward the goal he attacks, y 0-68
// from his right touchline), drawn so he always attacks to the right.

const L = 105, W = 68;
let palette = null;

function ramp() {
  if (palette) return palette;
  const c = document.createElement("canvas"); c.width = 256; c.height = 1;
  const g = c.getContext("2d"), gr = g.createLinearGradient(0, 0, 256, 0);
  gr.addColorStop(0.0, "rgba(255,236,150,0)");
  gr.addColorStop(0.18, "rgba(255,226,120,0.55)");
  gr.addColorStop(0.45, "rgba(250,170,60,0.85)");
  gr.addColorStop(0.75, "rgba(232,72,40,0.95)");
  gr.addColorStop(1.0, "rgba(196,20,28,1)");
  g.fillStyle = gr; g.fillRect(0, 0, 256, 1);
  palette = g.getImageData(0, 0, 256, 1).data;
  return palette;
}

// points: [[x, y, weight], ...] in the attacking frame.
export function drawHeat(canvas, points, radiusM = 6) {
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  const w = canvas.clientWidth || 300, h = Math.round(w * (W / L));
  canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!points.length) return;
  const sx = canvas.width / L, sy = canvas.height / W, r = radiusM * sx;
  const maxW = Math.max(...points.map((p) => p[2] ?? 1));
  for (const [x, y, wt = 1] of points) {
    const px = x * sx, py = (W - y) * sy;
    const g = ctx.createRadialGradient(px, py, 0, px, py, r);
    const a = Math.min(1, 0.35 * (wt / maxW) + 0.05);
    g.addColorStop(0, `rgba(0,0,0,${a})`); g.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = g;
    ctx.fillRect(px - r, py - r, 2 * r, 2 * r);
  }
  const img = ctx.getImageData(0, 0, canvas.width, canvas.height), d = img.data, pal = ramp();
  let peak = 0;
  for (let i = 3; i < d.length; i += 4) peak = Math.max(peak, d[i]);
  const k = peak ? 255 / peak : 1;
  for (let i = 0; i < d.length; i += 4) {
    const v = Math.min(255, Math.round(d[i + 3] * k));
    d[i] = pal[v * 4]; d[i + 1] = pal[v * 4 + 1]; d[i + 2] = pal[v * 4 + 2]; d[i + 3] = pal[v * 4 + 3];
  }
  ctx.putImageData(img, 0, 0);
}

// A season grid (rows of y bins, each a list of x bins, values 0-100) as weighted points.
export function gridPoints(grid, bins) {
  const [nx, ny] = bins, cw = L / nx, ch = W / ny, out = [];
  grid.forEach((v, i) => {
    if (v > 0) out.push([(i % nx + 0.5) * cw, (Math.floor(i / nx) + 0.5) * ch, v]);
  });
  return out;
}

export function heatPitchSVG() {
  // Ink lines for a light card; the canvas sits underneath.
  const box = (x0, dir) => {
    const bx = dir > 0 ? x0 : x0 - 16.5, sx = dir > 0 ? x0 : x0 - 5.5, arcX = x0 + dir * 16.5;
    return `<rect x="${bx}" y="13.84" width="16.5" height="40.32"/><rect x="${sx}" y="24.84" width="5.5" height="18.32"/>
      <path d="M ${arcX} 26.7 A 9.15 9.15 0 0 ${dir > 0 ? 1 : 0} ${arcX} 41.3"/>`;
  };
  return `<svg class="heat-lines" viewBox="0 0 ${L} ${W}" preserveAspectRatio="none" aria-hidden="true">
    <rect x="0.4" y="0.4" width="${L - 0.8}" height="${W - 0.8}"/><line x1="52.5" y1="0.4" x2="52.5" y2="${W - 0.4}"/>
    <circle cx="52.5" cy="34" r="9.15"/>${box(0.4, 1)}${box(L - 0.4, -1)}</svg>`;
}
