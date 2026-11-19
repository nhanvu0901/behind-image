// The one plain sentence of a shot, for the list of shots on the simple page of step 5 ("Dựng hình"). Pure: no DOM, no network.
//   shotSentence(shot, env) -> "Zoom vào khuôn mặt · vòng sáng" | "Bản đồ: Bruges tới Lucca" | "Trục thời gian: 6 mốc"
// It is made from the registry's Vietnamese names (`label_vi`), the picture and the region the shot shows, and the overlays on it. A short phrase table
// (labels.js SHOT_WORDS) only makes a name read as "what happens"; when nothing is known the answer is "Một cảnh", never an id, a file name or a parameter name.
// env: { tech(id) -> registry entry | null, assets: {key: asset}, mainKey: key of the main painting | null }
import { SHOT_WORDS as W } from './labels.js';
import { isVietnamese } from './errmsg.js';

const ID_LOOKING = /^[A-Z0-9_]{2,}$/;                         // "MIRROR", "R1", "HEAD_2": a name for a program, not for the owner
const MAX = 96;

const clip = (s, n = MAX) => { const t = String(s).replace(/\s+/g, ' ').trim(); return t.length > n ? t.slice(0, n - 1).trimEnd() + '…' : t; };
const lowerFirst = (s) => (s ? s[0].toLowerCase() + s.slice(1) : s);
const sentenceCase = (s) => (s.length > 3 && s === s.toUpperCase() && s !== s.toLowerCase() ? s[0] + s.slice(1).toLowerCase() : s);    // "THE MIRROR" -> "The mirror"
const shortTitle = (s, n = 30) => (s.length > n ? s.slice(0, n - 1).trimEnd() + '…' : s);               // a picture's title inside a sentence
const isObj = (v) => v && typeof v === 'object' && !Array.isArray(v);
const text = (v) => (typeof v === 'string' ? v.replace(/\s+/g, ' ').trim() : '');
const list = (v) => (Array.isArray(v) ? v : []);

// ---------------------------------------------------------------- the pictures and the regions
/** The asset key of the main painting: the one whose title is the project's painting, else the picture the base slots of the storyboard use most. */
export function mainAssetKey(draft, paintingTitle = '') {
  const assets = draft?.assets || {};
  const want = text(paintingTitle).toLowerCase();
  if (want) { const hit = Object.keys(assets).find((k) => text(assets[k]?.title).toLowerCase() === want && (assets[k]?.kind || 'image') === 'image'); if (hit) return hit; }
  const n = {};
  for (const s of draft?.shots || []) for (const v of Object.values(s.slots || {})) { const k = v?.asset; if (k && assets[k] && (assets[k].kind || 'image') === 'image') n[k] = (n[k] || 0) + 1; }
  return Object.keys(n).sort((a, b) => n[b] - n[a] || (a < b ? -1 : 1))[0] || null;
}

/** A region as the owner reads it: its label when that is a name (Vietnamese as it is, any other word in quotes), never its key. */
export function regionWords(asset, key) {
  const label = text(asset?.regions?.[key]?.label);
  if (!label || ID_LOOKING.test(label)) return W.detail;
  return isVietnamese(label) ? lowerFirst(label) : W.quoted(label);
}

/** The key of the region the last camera key ends on (the smallest region that holds the centre), when the camera comes in; null when it does not. */
export function cameraFocus(shot, asset) {
  const keys = list(shot?.params?.camera).filter((k) => k && Number.isFinite(k.cx) && Number.isFinite(k.cy) && Number.isFinite(k.zoom));
  if (!keys.length || !asset?.regions) return null;
  const first = keys[0], last = keys[keys.length - 1];
  if (keys.length > 1 && last.zoom < first.zoom * 1.05) return null;                       // the camera goes out or stays: no detail to name
  let best = null, area = Infinity;
  for (const [name, r] of Object.entries(asset.regions)) {
    const rx = Number(r.rx) > 0 ? Number(r.rx) : null, ry = Number(r.ry) > 0 ? Number(r.ry) : rx;
    if (!rx || !ry) continue;
    if (((last.cx - r.x) / rx) ** 2 + ((last.cy - r.y) / ry) ** 2 > 1) continue;
    if (rx * ry < area) { area = rx * ry; best = name; }
  }
  return best;
}

function slotTargets(shot, tech, env) {
  const out = [];
  const slots = list(tech?.slots).filter((s) => s.type === 'image' || s.type === 'video');
  for (const s of slots) {
    if (/^mask(_\d+)?$/.test(s.name)) continue;
    const v = shot?.slots?.[s.name];
    const key = v?.asset;
    const asset = key ? env.assets?.[key] : null;
    if (!asset || (asset.kind || 'image') === 'mask') continue;
    out.push({ slot: s.name, key, asset, region: v.region || null, video: asset.kind === 'video' || s.type === 'video', main: key === env.mainKey });
  }
  return out;
}
const phraseOf = (t) => {
  if (t.video) return W.clip(shortTitle(text(t.asset.title)), Number.isFinite(Number(t.asset.duration)) && Number(t.asset.duration) > 0 ? Math.round(Number(t.asset.duration)) : 0);
  if (t.region) return regionWords(t.asset, t.region);
  return t.main ? W.whole : W.other(shortTitle(text(t.asset.title)));
};
const joinPhrases = (ps, max = 2) => {
  const u = [...new Set(ps)];
  if (u.length <= 1) return u[0] || '';
  if (u.length === 2) return W.twoOf(u[0], u[1]);
  return `${u.slice(0, max).join(', ')} ${W.moreImages(u.length - max)}`;
};

// ---------------------------------------------------------------- explainers that have their own facts
const placeName = (p) => text(p?.name) || '';
function mapSentence(shot, name) {
  const P = shot.params || {};
  const places = list(P.places), byId = new Map(places.map((p) => [String(p?.id ?? ''), placeName(p)]));
  const named = places.map(placeName).filter(Boolean);
  const r = list(P.route)[0] || (isObj(P.route) ? P.route : null);
  const a = r ? byId.get(String(r.from ?? '')) : '', b = r ? byId.get(String(r.to ?? '')) : '';
  if (a && b) return `${name}: ${W.route(a, b)}`;
  const from = text(P.from_label), to = text(P.to_label);                                  // the older map technique
  if (from && to) return `${name}: ${W.route(from, to)}`;
  if (named.length === 1) return `${name}: ${named[0]}`;
  if (named.length === 2) return `${name}: ${W.twoOf(named[0], named[1])}`;
  if (named.length > 2) return `${name}: ${named.slice(0, 2).join(', ')} ${W.morePlaces(named.length - 2)}`;
  return name;
}
function countSentence(name, n, word) { return n > 0 ? `${name}: ${word(n)}` : name; }

function explainer(shot, tech, id, env) {
  const P = shot.params || {};
  const name = W.names[id] || text(tech?.label_vi);
  switch (id) {
    case 'MAP-01': case 'STATIC-06': return mapSentence(shot, name);
    case 'TIME-01': return countSentence(name, list(P.items).length, W.count.moments);
    case 'TREE-01': return countSentence(name, list(P.nodes).length, W.count.people);
    case 'STATE-01': { const a = text(P.label_a), b = text(P.label_b); return a && b ? `${name}: ${W.states(a, b)}` : name; }
    default: return null;
  }
}

function cardSentence(shot, id) {
  const base = W.card[id];
  if (!base) return null;
  const t = text(shot.params?.title) || text(shot.params?.text);
  return t && !ID_LOOKING.test(t) ? `${base}: ${clip(sentenceCase(t), 40)}` : base;
}

// ---------------------------------------------------------------- the base of the shot
function cameraSentence(shot, tech, env, targets) {
  const spec = W.camera[tech.id];
  if (!spec) return null;
  const t = targets[0], tail = spec.tail || '';
  if (spec.use === 'whole') return `${spec.lead} ${W.whole}`;
  if (!t) return `${spec.lead}${spec.otherwise ? ` ${spec.otherwise}` : ''} ${W.painting}${tail}`;
  if (t.video || spec.use === 'target') return `${spec.lead} ${phraseOf(t)}${tail}`;
  const region = t.region || cameraFocus(shot, t.asset);
  if (region) return `${spec.lead}${spec.prep ? ` ${spec.prep}` : ''} ${regionWords(t.asset, region)}${tail}`;
  return `${spec.lead}${spec.otherwise ? ` ${spec.otherwise}` : ''} ${t.main ? W.whole : W.other(shortTitle(text(t.asset.title)))}${tail}`;
}

function baseSentence(shot, tech, env) {
  const id = tech.id, label = text(tech.label_vi);
  const targets = slotTargets(shot, tech, env);
  const own = explainer(shot, tech, id, env) || cardSentence(shot, id) || cameraSentence(shot, tech, env, targets);
  if (own) return own;
  const what = joinPhrases(targets.map(phraseOf));
  if (!label) return what ? `${W.unknown}: ${what}` : '';
  return what ? `${label}: ${what}` : label;
}

// ---------------------------------------------------------------- the overlays
/** The overlays of a shot as short phrases: "2 vòng sáng", "nhãn chi tiết"; the same phrase is counted once. */
export function overlayPhrases(shot, env) {
  const order = [], n = new Map();
  for (const o of list(shot?.overlays)) {
    const t = env.tech?.(o?.technique);
    const phrase = W.overlay[o?.technique] || lowerFirst(text(t?.label_vi));
    if (!phrase) continue;
    if (!n.has(phrase)) order.push(phrase);
    n.set(phrase, (n.get(phrase) || 0) + 1);
  }
  return order.map((p) => (n.get(p) > 1 ? W.count2(n.get(p), p) : p));
}

/** The sentence of a shot. Never empty and never an id. */
export function shotSentence(shot, env = {}) {
  const tech = env.tech?.(shot?.technique) || null;
  let base = '';
  if (tech && text(tech.label_vi)) { try { base = baseSentence(shot || {}, tech, env); } catch { base = text(tech.label_vi); } }
  const ov = overlayPhrases(shot || {}, env);
  const shown = ov.length > 3 ? [...ov.slice(0, 3), W.andMore(ov.length - 3)] : ov;
  const sentence = [base || W.unknown, ...shown].join(W.joiner);
  return clip(sentence);
}

/** The words that show that a sentence is plain: no id of a technique, no underscore name, no raw file path. (Used by the tests and by the page's own guard.) */
export const looksRaw = (s) => /\b[A-Z]{1,6}-[A-Z0-9]{1,3}(-\d+)?\b|\b[a-z]+_[a-z_]+\b|\.(jpg|png|mp4|json)\b/.test(String(s));
