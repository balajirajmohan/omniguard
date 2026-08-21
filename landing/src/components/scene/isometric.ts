/** Shared isometric projection helpers for the warehouse scene. */

export const OX = 330;
export const OY = 232;
export const CX = 36;
export const CY = 18;

/** Grid coordinate → screen point in the 660×560 scene viewBox. */
export function iso(x: number, y: number, lift = 0): [number, number] {
  return [OX + (x - y) * CX, OY + (x + y) * CY - lift];
}

export function pt(x: number, y: number, lift = 0): string {
  const [sx, sy] = iso(x, y, lift);
  return `${sx.toFixed(1)},${sy.toFixed(1)}`;
}

/** Flat quad on the floor plane, e.g. a zone overlay. */
export function quad(x0: number, y0: number, x1: number, y1: number, lift = 0): string {
  return [pt(x0, y0, lift), pt(x1, y0, lift), pt(x1, y1, lift), pt(x0, y1, lift)].join(' ');
}

/** Extruded box: the three faces visible from this camera angle. */
export function box(x0: number, y0: number, x1: number, y1: number, h: number) {
  return {
    top: quad(x0, y0, x1, y1, h),
    // Down-right facing face.
    right: [pt(x1, y0, h), pt(x1, y1, h), pt(x1, y1), pt(x1, y0)].join(' '),
    // Down-left facing face.
    left: [pt(x0, y1, h), pt(x1, y1, h), pt(x1, y1), pt(x0, y1)].join(' '),
  };
}
