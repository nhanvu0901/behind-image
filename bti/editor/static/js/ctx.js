// Shared application context: one store, registry, project state, tiny event bus.
import { Store } from './store.js';
import { stripDerived } from './logic.js';
import { incompleteMap, missingLabel } from './slots.js';

const handlers = {};
export const bus = {
  on(evt, fn) { (handlers[evt] ||= new Set()).add(fn); return () => handlers[evt].delete(fn); },
  emit(evt, data) { for (const fn of handlers[evt] || []) fn(data); },
  /** Drop every subscriber (the editing view does this when it is left). */
  clear() { for (const k of Object.keys(handlers)) delete handlers[k]; },
};

export const ctx = {
  pid: null,
  store: new Store(150),
  reg: { list: [], byId: {}, intents: [], style: null },
  assetInfo: {},      // key -> {thumb_url, ...} from GET /assets
  issues: [],
  t: 0,               // playhead, seconds
  playing: false,
  proposalsCount: 0,
  pick: null,         // active "pick on preview" request: {space, cb}
  thumbFails: new Map(), // 'shotId|rev' -> Vietnamese reason a shot's small picture could not be drawn (422 render_failed)
  incomplete: new Map(), // item key ('s0001' or 's0001/o1') -> names of its empty required slots/params
  health: null,
  canvasDims() { return this.store.draft?.canvas || { w: 1920, h: 1080 }; },
  words() { return this.store.timing?.words || []; },
  duration() { return this.store.timing?.duration || this.store.draft?.end?.t || 0; },
  draftPlain() { return stripDerived(this.store.draft); },
  tech(id) { return this.reg.byId[id] || null; },
  /** Recompute which shots/overlays are incomplete (registry rules now, the server's `incomplete` issues when they arrive). */
  refreshIncomplete() { this.incomplete = this.store.draft ? incompleteMap(this.store.draft, (id) => this.tech(id), this.issues) : new Map(); },
  thumbFailOf(shotId) { return this.thumbFails.get(shotId + '|' + (this.renderKey || this.store.rev)) || null; },
  incompleteOf(shotId, overlayId = null) { return this.incomplete.get(overlayId ? `${shotId}/${overlayId}` : shotId) || null; },
  incompleteText(shotId, overlayId = null) { const n = this.incompleteOf(shotId, overlayId); return n ? missingLabel(n) : ''; },
  /** Move the playhead (clamped). The one way to seek; the timeline, the keys and the selection all use it. */
  seek(t) { this.t = Math.min(Math.max(0, t), Math.max(0, this.duration())); bus.emit('time', this.t); },
  /** Forget everything about the project that was open (the style registry is kept). */
  reset() {
    this.pid = null; this.store.reset(); this.assetInfo = {}; this.issues = []; this.t = 0; this.playing = false;
    this.proposalsCount = 0; this.pick = null; this.slotPick = null; this.noAudio = false; this.incomplete = new Map(); this.renderKey = null; this.thumbFails = new Map();
  },
};

export function setRegistry(styleBody) {
  const list = styleBody.techniques || [];
  ctx.reg = { list, byId: Object.fromEntries(list.map((t) => [t.id, t])), intents: styleBody.intents || [...new Set(list.flatMap((t) => t.intents))].sort(), style: styleBody.style };
}

export function intentColor(intent) {
  const i = Math.max(0, ctx.reg.intents.indexOf(intent));
  return { h: (i * 47 + 205) % 360 };
}
export const intentHsl = (intent, s = 45, l = 32, a = 1) => `hsl(${intentColor(intent).h} ${s}% ${l}% / ${a})`;

/** First picture slot asset of a shot: {key, asset}. Only images count: a mask or a video is never "the picture". */
export function primaryAsset(shot) {
  const sb = ctx.store.draft;
  const slots = shot?.slots || {};
  for (const v of Object.values(slots)) {
    const a = v?.asset && sb.assets[v.asset];
    if (a && a.width && a.height && (a.kind || 'image') === 'image') return { key: v.asset, asset: a };
  }
  return null;
}

export function assetThumbUrl(key, api) {
  const info = ctx.assetInfo[key];
  const a = ctx.store.draft?.assets?.[key];
  return api.url(info?.thumb_url || a?.thumb_url || '') || '';
}
