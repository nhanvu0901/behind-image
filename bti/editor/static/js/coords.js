// The ONE place that maps between coordinate spaces. Nothing else in the editor does this arithmetic.
//
//   screen  svg pixels of the preview stage, {W, H} (what the pointer and the drawn handles use)
//   canvas  pixels of the output frame, {w, h} (1920 x 1080 for the channel)
//   source  pixels of an asset image, seen through the camera {cx, cy, zoom} (zoom = canvas px per source px)
//   frame   fractions 0..1 of the canvas (x of width, y of height)
//
// A parameter lives in exactly one space (see paramSpace). Screen is only ever reached through a Spaces object, which also says
// which spaces are available right now (no camera: no source space; "Ảnh gốc" view: no canvas space, the picture shown is the
// source image, not the frame).
export const SPACES = ['source', 'canvas', 'frame'];

/** spaces = makeSpaces({canvas:{w,h}, view:{W,H}, cam:{cx,cy,zoom}|null, canvasOk:true}) */
export function makeSpaces({ canvas, view, cam = null, canvasOk = true }) {
  const kx = view.W / canvas.w, ky = view.H / canvas.h;     // screen px per canvas px
  const z = cam ? cam.zoom : null;
  const S = {
    canvas, view, cam, kx, ky,
    has: (space) => (space === 'source' ? !!cam : space === 'canvas' || space === 'frame' ? !!canvasOk : false),
    // canvas <-> screen
    canvasToScreen: (x, y) => [x * kx, y * ky],
    screenToCanvas: (sx, sy) => [sx / kx, sy / ky],
    // frame <-> canvas
    frameToCanvas: (x, y) => [x * canvas.w, y * canvas.h],
    canvasToFrame: (x, y) => [x / canvas.w, y / canvas.h],
    // source <-> canvas (through the camera)
    sourceToCanvas: (x, y) => (cam ? [(x - cam.cx) * z + canvas.w / 2, (y - cam.cy) * z + canvas.h / 2] : null),
    canvasToSource: (x, y) => (cam ? [(x - canvas.w / 2) / z + cam.cx, (y - canvas.h / 2) / z + cam.cy] : null),
  };
  S.sourceToScreen = (x, y) => { const c = S.sourceToCanvas(x, y); return c && S.canvasToScreen(c[0], c[1]); };
  S.screenToSource = (sx, sy) => { const c = S.screenToCanvas(sx, sy); return c && S.canvasToSource(c[0], c[1]); };
  S.frameToScreen = (x, y) => S.canvasToScreen(x * canvas.w, y * canvas.h);
  S.screenToFrame = (sx, sy) => { const c = S.screenToCanvas(sx, sy); return S.canvasToFrame(c[0], c[1]); };
  /** A point of `space` -> screen px (null when the space is not available). */
  S.toScreen = (space, p) => {
    if (!S.has(space)) return null;
    return space === 'source' ? S.sourceToScreen(p[0], p[1]) : space === 'canvas' ? S.canvasToScreen(p[0], p[1]) : S.frameToScreen(p[0], p[1]);
  };
  S.fromScreen = (space, s) => {
    if (!S.has(space)) return null;
    return space === 'source' ? S.screenToSource(s[0], s[1]) : space === 'canvas' ? S.screenToCanvas(s[0], s[1]) : S.screenToFrame(s[0], s[1]);
  };
  /** Screen px per one unit of `space`, along x and y (for radii and box sizes). */
  S.scale = (space) => (space === 'source' ? [kx * (z || 1), ky * (z || 1)] : space === 'canvas' ? [kx, ky] : [view.W, view.H]);
  /** Round a value written into `space`: whole pixels, or 4 decimals for fractions. */
  S.round = (space, p) => (space === 'frame' ? p.map((v) => Math.round(v * 1e4) / 1e4) : p.map((v) => Math.round(v)));
  return S;
}

/** Move a point of `space` by a screen delta, from where it was at the start of the drag. Exact in every space. */
export function dragPoint(S, space, startPt, dxs, dys) {
  const s0 = S.toScreen(space, startPt);
  if (!s0) return null;
  return S.round(space, S.fromScreen(space, [s0[0] + dxs, s0[1] + dys]));
}

// ---- boxes: the registry stores [x0, y0, x1, y1]; the drawing code wants {x, y, w, h}
export function boxToRect(v) {
  if (Array.isArray(v) && v.length === 4 && v.every((n) => typeof n === 'number' && Number.isFinite(n))) {
    return { x: Math.min(v[0], v[2]), y: Math.min(v[1], v[3]), w: Math.abs(v[2] - v[0]), h: Math.abs(v[3] - v[1]) };
  }
  if (v && typeof v === 'object' && !Array.isArray(v) && ['x', 'y', 'w', 'h'].every((k) => typeof v[k] === 'number' && Number.isFinite(v[k]))) return { x: v.x, y: v.y, w: v.w, h: v.h };   // old form, read only
  return null;
}
export const rectToBox = (r) => [Math.round(r.x), Math.round(r.y), Math.round(r.x + r.w), Math.round(r.y + r.h)];
/** Anything a box field may hold -> [x0,y0,x1,y1] or null (used to repair values written by the old widget). */
export const normBox = (v) => { const r = boxToRect(v); return r ? rectToBox(r) : null; };

// ---- which space does a parameter live in?
// An explicit `space` in the registry entry wins. Otherwise: the unit text, then the rules below (read from the engine code).
// Result: 'source' | 'canvas' | 'frame' | 'none' (not drawable on the preview: edit the numbers), or 'source:<slot>' (source pixels of another slot's image).
const FIXED = {
  'DIA-02.to_quad': 'none', 'DIA-02.from_quad': 'none', 'SHORT-02.to_quad': 'none',     // fractions of an internal panel
  'DIA-06.painting_box': 'source:room',                                                 // source px of the room image
  'LAY-06.strip_step': 'none',                                                          // a step, not a position
};
const MAP_TECHS = new Set(['AN-04', 'X-ANN-05']);
export function paramSpace(techId, def, { params = {}, hasSlot = () => false } = {}) {
  if (def.space) return def.space;
  const key = `${techId}.${def.name}`;
  if (FIXED[key]) return FIXED[key];
  const val = (n) => (n in params ? params[n] : undefined);
  if (techId === 'AN-03' && def.name === 'origins') return (val('origin_space') ?? 'frame') === 'frame' ? 'frame' : 'source';
  if (techId === 'AN-06' && def.name === 'shape_points') return (val('space') ?? 'frame') === 'frame' ? 'frame' : 'source';
  if (MAP_TECHS.has(techId)) {
    const bg = val('background') ?? 'auto';
    if (bg === 'base') return 'source';
    if (bg === 'procedural' || (bg === 'auto' && !hasSlot('map'))) return 'canvas';
    return 'none';                                                                       // pixels of the `map` slot image
  }
  const unit = String(def.unit || '');
  if (/canvas|screen/i.test(unit) || def.name.startsWith('screen')) return 'canvas';
  return 'source';
}
export const splitSpace = (s) => { const [space, slot] = String(s).split(':'); return { space, slot: slot || null }; };

/** A point value (array or region name) -> [x, y] in source px, or null. */
export function resolvePoint(v, regions) {
  if (Array.isArray(v) && v.length >= 2 && typeof v[0] === 'number' && typeof v[1] === 'number') return [v[0], v[1]];
  if (typeof v === 'string' && regions?.[v]) return [regions[v].x, regions[v].y];
  return null;
}

/** What a click on the preview gives for a field of `space`. Region names only exist in source space (Shift = always x, y). */
export function pickValue(S, space, screenPt, regions, shift = false) {
  const p = S.fromScreen(space, screenPt);
  if (!p) return null;
  const value = S.round(space, p);
  if (space === 'source' && !shift) {
    for (const [name, rg] of Object.entries(regions || {})) {
      const rx = rg.rx || 1, ry = rg.ry || 1;
      if (((p[0] - rg.x) / rx) ** 2 + ((p[1] - rg.y) / ry) ** 2 <= 1) return name;
    }
  }
  return value;
}

/** Is a source-space point outside its image? */
export const outsideImage = (pt, asset) => !!asset?.width && !!asset?.height && (pt[0] < 0 || pt[1] < 0 || pt[0] > asset.width || pt[1] > asset.height);
