// Camera frames of the source view ("Ảnh gốc"): pure geometry, no DOM. d-camera (D22).
//
// A camera key {cx, cy, zoom} says: the point (cx, cy) of the source picture is at the centre of a PANEL (a rectangle of the video
// frame), and one source pixel is `zoom` panel pixels (bti/engine/vfx.py Img.view: x_panel = panel_w/2 + (x - cx) * zoom).
// So the key sees, in source pixels, a rectangle of (panel_w / zoom) x (panel_h / zoom) centred at (cx, cy).
// For a camera that fills the whole video frame the panel is the canvas (1920 x 1080); for a layout technique it is the cell the
// picture is drawn into (LAY-01: panel_w_px x panel_h_px, ...). Which slot a camera looks at and how big its panel is are facts of
// each technique's engine code; the table TARGETS below records them (with the file that says so), and a test fails when the
// registry gets a camera parameter the table does not know.

// ---- limits: the engine's validation (bti/engine/limits.py: |cx|, |cy| <= 1e6, 0 < zoom <= 1000) and the lowest zoom the form accepts
export const ZOOM_MAX = 1000;
export const ZOOM_MIN = 0.01;
export const CENTRE_ABS_MAX = 1e6;

const fin = (n) => typeof n === 'number' && Number.isFinite(n);
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const rnd = (v, d) => { const m = 10 ** d; return Math.round(v * m) / m; };

// ---- which slot and which panel a camera parameter belongs to
const CANVAS = 'canvas';
const wh = (a, b) => [a, b];                 // the panel is the integers params[a] x params[b]

/** Tiles of LAY-07: the non-empty tile slots, packed in `columns` columns (layouts_grid.py GridWithObject.render). */
function lay07Tile(get, slots, canvas) {
  const n = Math.max(1, [1, 2, 3, 4, 5, 6].filter((i) => slots?.['tile_' + i]?.asset).length);
  const cols = Math.max(1, Math.trunc(get('columns') || 1));
  const rows = Math.ceil(n / cols);
  return { w: Math.floor(canvas.w / cols), h: Math.floor(canvas.h / rows) };
}
/** LAY-08: one motif view tiled "CxR": the tile is canvas / (C, R) (layouts_grid.py MirroredMotif.render). */
function lay08Tile(get, slots, canvas) {
  const [c, r] = String(get('tiles') || '1x1').toLowerCase().replace(/\s+/g, '').split('x').map((v) => Math.max(1, parseInt(v, 10) || 1));
  return { w: Math.floor(canvas.w / c), h: Math.floor(canvas.h / (r || 1)) };
}
/** CMP-02: the finished picture fills finished_box [x0, y0, x1, y1] (compare.py FinishedAndStages.render). */
function cmp02Box(get) {
  const b = get('finished_box');
  return Array.isArray(b) && b.length === 4 ? { w: Math.trunc(b[2]) - Math.trunc(b[0]), h: Math.trunc(b[3]) - Math.trunc(b[1]) } : null;
}

// camera parameter -> [slot, panel]; panel is CANVAS, [width param, height param], or a function (get, slots, canvas) -> {w, h}
const MATTE = (slot = 'image') => [slot, CANVAS];
const PANEL = (slot, w = 'panel_w_px', h = 'panel_h_px') => [slot, wh(w, h)];
export const TARGETS = {
  // camera.py MatteShot, camera_extra.py HoldAndLabel, annotations_extra.py DotField: the whole frame
  'CAM-01': { camera: MATTE() }, 'CAM-03': { camera: MATTE() }, 'CAM-04': { camera: MATTE() }, 'CAM-05': { camera: MATTE() },
  'CAM-06': { camera: MATTE() }, 'STATIC-01': { camera: MATTE() }, 'X-LAY-01': { camera: MATTE() }, 'AN-07': { camera: MATTE() },
  // identity.py (the channel-name beat and the chapter marks of the two identity styles): the picture is drawn exactly as CAM-01 draws it
  'ID-BRAND-01': { camera: MATTE() }, 'ID-BRAND-02': { camera: MATTE() }, 'ID-BRAND-03': { camera: MATTE() }, 'ID-MARK-01': { camera: MATTE() }, 'ID-MARK-02': { camera: MATTE() },
  // camera_extra.py LayerRelativeMotion: each layer in the pixels of its own picture, both over the whole frame
  'CAM-02': { fg_camera: MATTE('foreground'), bg_camera: MATTE('background') },
  // highlights_extra.py FigureReveal: plate and figures are registered, the camera is in the plate's pixels
  'HI-02': { camera: MATTE('room_plate') },
  // layout.py TwoPanel: each side has its own picture and its own panel_w_px x panel_h_px cell
  'LAY-01': { camera_left: PANEL('left'), camera_right: PANEL('right') },
  // layouts_grid.py
  'LAY-02': Object.fromEntries([1, 2, 3, 4].map((i) => ['camera_' + i, PANEL('tile_' + i, 'tile_w_px', 'tile_h_px')])),
  'LAY-04': { camera: MATTE(), inset_camera: PANEL('inset', 'inset_w_px', 'inset_h_px') },
  'LAY-05': { camera: MATTE(), ...Object.fromEntries([1, 2, 3, 4].map((i) => ['camera_bg_' + i, MATTE('background_' + i)])) },
  'LAY-06': { camera_base: ['background|image', CANVAS] },           // the base layer is `background`, or `image` when there is none
  'LAY-07': { ...Object.fromEntries([1, 2, 3, 4, 5, 6].map((i) => ['camera_' + i, ['tile_' + i, lay07Tile]])), object_camera: MATTE('object') },
  'LAY-08': { camera: ['image', lay08Tile] },
  // compare.py
  'CMP-01': { camera: PANEL('colour') },
  'CMP-02': { finished_camera: ['finished', cmp02Box], stage_camera: ['finished', wh('derive_px', 'derive_px')] },
  'CMP-03': { camera: PANEL('image') },
  'CMP-04': { camera: PANEL('image') },
  'CMP-05': { camera: MATTE('state_a') },
  'X-CMP-01': { camera_anchor: PANEL('anchor') },
  'X-CMP-02': { camera: MATTE('state_a') },
  // compbase: explain_base.py TwoStates (STATE-01): one camera over the whole frame, in the pixels of slot a
  'STATE-01': { camera: MATTE('a') },
};

/** The first slot of the list "a|b" that holds a picture, else the first name. */
function pickSlot(spec, slots) {
  const names = String(spec).split('|');
  return names.find((n) => slots?.[n]?.asset) || names[0];
}

/**
 * Where does camera parameter `name` of technique `techId` look, and through which panel?
 * `tech` is the registry entry (for defaults and slots), `params` and `slots` are the shot's, `canvas` {w, h}.
 * -> {slot, panel: {w, h}, known} ; `known` is false for a camera parameter the table does not list (then: first image slot, whole frame).
 */
export function cameraTarget(tech, name, params, slots, canvas) {
  const defs = Object.fromEntries((tech?.params || []).map((p) => [p.name, p]));
  const get = (n) => (params && n in params && params[n] !== null && params[n] !== undefined ? params[n] : defs[n]?.default);
  const row = TARGETS[tech?.id]?.[name];
  if (!row) {
    const first = (tech?.slots || []).find((s) => (s.type || 'image') === 'image');
    return { slot: first?.name || 'image', panel: { w: canvas.w, h: canvas.h }, known: false };
  }
  const [slotSpec, panelSpec] = row;
  let panel;
  if (panelSpec === CANVAS) panel = { w: canvas.w, h: canvas.h };
  else if (Array.isArray(panelSpec)) panel = { w: Math.trunc(get(panelSpec[0])), h: Math.trunc(get(panelSpec[1])) };
  else panel = panelSpec(get, slots, canvas);
  if (!panel || !(panel.w > 0) || !(panel.h > 0)) panel = { w: canvas.w, h: canvas.h };
  return { slot: pickSlot(slotSpec, slots), panel, known: true };
}

/** A value is a drawable key list: every key has a finite centre and a zoom in (0, ZOOM_MAX]. */
export const isKeyList = (v) => Array.isArray(v) && v.length > 0 && v.every((k) => k && typeof k === 'object' && fin(k.cx) && fin(k.cy) && fin(k.zoom) && k.zoom > 0);

/**
 * The camera parameters of a shot that can be drawn, in registry order:
 * [{name, slot, assetKey, asset, panel, keys}]. Needs the picture (a slot with an asset that has a size) and a valid key list.
 */
export function cameraSets(tech, shot, assets, canvas) {
  const out = [];
  for (const def of tech?.params || []) {
    if (def.type !== 'camera') continue;
    const keys = shot?.params?.[def.name];
    if (!isKeyList(keys)) continue;
    const t = cameraTarget(tech, def.name, shot.params, shot.slots, canvas);
    const assetKey = shot.slots?.[t.slot]?.asset || null;
    const asset = assetKey ? assets?.[assetKey] : null;
    if (!asset || !(asset.width > 0) || !(asset.height > 0)) continue;
    out.push({ name: def.name, slot: t.slot, assetKey, asset, panel: t.panel, keys, known: t.known });
  }
  return out;
}

// ---- key <-> frame rectangle, in SOURCE pixels
export const frameSize = (zoom, panel) => ({ w: panel.w / zoom, h: panel.h / zoom });
export function keyToRect(k, panel) {
  const { w, h } = frameSize(k.zoom, panel);
  return { x: k.cx - w / 2, y: k.cy - h / 2, w, h };
}
export const rectToKey = (r, panel) => ({ cx: r.x + r.w / 2, cy: r.y + r.h / 2, zoom: panel.w / r.w });
/** What the key writes into the storyboard: centre to 0.1 px, zoom to 4 decimals (the precision the number fields show and keep). */
export const roundKey = (k) => ({ cx: rnd(k.cx, 1), cy: rnd(k.cy, 1), zoom: rnd(k.zoom, 4) });

export const clampZoom = (z) => clamp(fin(z) ? z : 1, ZOOM_MIN, ZOOM_MAX);

/**
 * Where the centre may go: the picture, widened so that it also holds where the centre already is (a key the owner put outside
 * the picture on purpose is not pulled back by touching it), never beyond the engine's own limit.
 */
export function centreBounds(asset, start) {
  const lim = CENTRE_ABS_MAX;
  const x0 = Math.min(0, start.cx), x1 = Math.max(asset.width, start.cx), y0 = Math.min(0, start.cy), y1 = Math.max(asset.height, start.cy);
  return { x0: Math.max(-lim, x0), x1: Math.min(lim, x1), y0: Math.max(-lim, y0), y1: Math.min(lim, y1) };
}

/** Move the centre of `k0` by (dx, dy) source pixels; zoom is kept. */
export function moveKey(k0, dx, dy, bounds) {
  return { ...k0, cx: clamp(k0.cx + dx, bounds.x0, bounds.x1), cy: clamp(k0.cy + dy, bounds.y0, bounds.y1) };
}

export const CORNERS = { nw: [-1, -1], ne: [1, -1], sw: [-1, 1], se: [1, 1] };
export function cornerPoints(r) {
  return { nw: [r.x, r.y], ne: [r.x + r.w, r.y], sw: [r.x, r.y + r.h], se: [r.x + r.w, r.y + r.h] };
}

/**
 * Drag corner `corner` of the frame of `k0` by (dx, dy) source pixels. The centre stays and the frame keeps the panel's aspect.
 * The pointer is projected on the frame's diagonal (in units of the frame's half sides), so pulling a corner diagonally resizes by
 * exactly as much as it moved, outward or inward, and pulling it along one side resizes by half as much.
 */
export function resizeKey(k0, panel, corner, dx, dy) {
  const [sx, sy] = CORNERS[corner];
  const r = keyToRect(k0, panel);
  const c = cornerPoints(r)[corner];
  const s = (((c[0] + dx - k0.cx) * sx) / (r.w / 2) + ((c[1] + dy - k0.cy) * sy) / (r.h / 2)) / 2;   // new half size / old half size
  return { ...k0, zoom: clampZoom(s > 0 ? k0.zoom / s : ZOOM_MAX) };
}

// ---- hit testing in SCREEN pixels. rects: [{x, y, w, h}] (one per key), selected: index of the selected key.
export const HANDLE_TOL = 9;                                  // screen px around a corner handle
const inside = (r, p, m = 0) => p[0] >= r.x - m && p[0] <= r.x + r.w + m && p[1] >= r.y - m && p[1] <= r.y + r.h + m;

/**
 * What is under the pointer `pt`?
 *  1. a corner handle of the SELECTED key (these win over everything: they are small and sit on borders where frames overlap);
 *  2. otherwise the frames that contain the point: the SMALLEST one wins, so a small frame inside a large one can be picked.
 *     Frames of the same size (a camera that holds still has equal keys, which draw on top of each other) are a stack, `ties`:
 *     the selected one stays the target of a drag; a point where the selected one is not in the stack goes to the last of it.
 * -> {index, part: 'corner', corner} | {index, part: 'body', ties: [indices of the stack, ascending]} | null
 */
export function hitTest(rects, selected, pt, tol = HANDLE_TOL) {
  const sel = rects[selected];
  if (sel) {
    let best = null;
    for (const [name, p] of Object.entries(cornerPoints(sel))) {
      const d = Math.max(Math.abs(pt[0] - p[0]), Math.abs(pt[1] - p[1]));
      if (d <= tol && (!best || d < best.d)) best = { d, name };
    }
    if (best) return { index: selected, part: 'corner', corner: best.name };
  }
  const m = Math.min(2, tol / 4);
  let min = Infinity;
  rects.forEach((r) => { if (inside(r, pt, m)) min = Math.min(min, r.w * r.h); });
  if (min === Infinity) return null;
  const ties = [];
  rects.forEach((r, i) => { if (inside(r, pt, m) && r.w * r.h <= min + 1e-9 * Math.max(min, 1)) ties.push(i); });
  return { index: ties.includes(selected) ? selected : ties[ties.length - 1], part: 'body', ties };
}
/** In a stack of equal frames, the key after `selected` (a click without movement walks through the stack). */
export const nextInStack = (ties, selected) => ties.find((i) => i > selected) ?? ties[0];

/** Which corner cursor: nw and se resize along one diagonal, ne and sw along the other. */
export const cornerCursor = (corner) => (corner === 'nw' || corner === 'se' ? 'nwse-resize' : 'nesw-resize');

// ---- the source view: the picture, widened to hold every frame of the camera that is being edited
/**
 * The camera of the "Ảnh gốc" view (what the stage shows: `cam.zoom` canvas px per source px, `cam` at the centre of the stage).
 * Without frames it is the picture fitted at 94 % (what the view always showed). With frames, the view zooms out only as far as
 * needed to hold the picture and every frame, and is centred on both together.
 */
export function sourceViewCamera(asset, canvas, rects = []) {
  const fit = Math.min(canvas.w / asset.width, canvas.h / asset.height) * 0.94;
  let x0 = 0, y0 = 0, x1 = asset.width, y1 = asset.height;
  for (const r of rects) { x0 = Math.min(x0, r.x); y0 = Math.min(y0, r.y); x1 = Math.max(x1, r.x + r.w); y1 = Math.max(y1, r.y + r.h); }
  if (!(x1 - x0 > asset.width + 1e-6 || y1 - y0 > asset.height + 1e-6)) return { cx: asset.width / 2, cy: asset.height / 2, zoom: fit };
  const zoom = Math.min(fit, (Math.min(canvas.w / (x1 - x0), canvas.h / (y1 - y0))) * 0.94);
  return { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, zoom };
}

/** Choose what is selected after the data or the shot changed: keep it when it still exists, else the first camera, key 0. */
export function resolveSelection(sel, shotId, sets) {
  if (!sets.length) return { shot: shotId, param: null, index: 0 };
  const set = sel && sel.shot === shotId ? sets.find((s) => s.name === sel.param) : null;
  if (!set) return { shot: shotId, param: sets[0].name, index: 0 };
  return { shot: shotId, param: set.name, index: clamp(Math.trunc(sel.index) || 0, 0, set.keys.length - 1) };
}
