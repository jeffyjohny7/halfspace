// A 105 x 68 pitch drawn in chalk. The home side always attacks to the right.

export const L = 105, W = 68;

// Event coordinates are in the acting team's frame (x towards the goal it attacks,
// y from its right touchline). Convert to the screen frame.
export function toScreen(team, x, y) {
  if (x == null || y == null) return null;
  return team === 0 ? [x, W - y] : [L - x, y];
}

export function pitchMarkings() {
  const stripes = Array.from({ length: 10 }, (_, i) =>
    i % 2 ? `<rect class="stripe" x="${(i * L) / 10}" y="0" width="${L / 10}" height="${W}"/>` : "").join("");
  const box = (x0, dir) => {
    const bx = dir > 0 ? x0 : x0 - 16.5, sx = dir > 0 ? x0 : x0 - 5.5;
    const spot = x0 + dir * 11;
    const arcX = x0 + dir * 16.5;
    const a1 = [arcX, 34 - 7.3], a2 = [arcX, 34 + 7.3];
    return `<rect x="${bx}" y="${34 - 20.16}" width="16.5" height="40.32"/>
      <rect x="${sx}" y="${34 - 9.16}" width="5.5" height="18.32"/>
      <path d="M ${a1[0]} ${a1[1]} A 9.15 9.15 0 0 ${dir > 0 ? 1 : 0} ${a2[0]} ${a2[1]}"/>
      <circle class="spot" cx="${spot}" cy="34" r="0.35"/>
      <rect x="${dir > 0 ? x0 - 1.6 : x0}" y="${34 - 3.66}" width="1.6" height="7.32"/>`;
  };
  return `<rect class="turf" x="0" y="0" width="${L}" height="${W}" rx="1.4"/>${stripes}
    <g class="markings">
      <rect x="0.6" y="0.6" width="${L - 1.2}" height="${W - 1.2}"/>
      <line x1="${L / 2}" y1="0.6" x2="${L / 2}" y2="${W - 0.6}"/>
      <circle cx="${L / 2}" cy="34" r="9.15"/>
      <circle class="spot" cx="${L / 2}" cy="34" r="0.4"/>
      ${box(0.6, 1)}${box(L - 0.6, -1)}
    </g>`;
}
