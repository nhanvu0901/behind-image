// Shared application context: one store, registry, project state, tiny event bus.
import { Store } from './store.js';
import { stripDerived } from './logic.js';

const handlers = {};
export const bus = {
  on(evt, fn) { (handlers[evt] ||= new Set()).add(fn); return () => handlers[evt].delete(fn); },
  emit(evt, data) { for (const fn of handlers[evt] || []) fn(data); },
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
  pick: null,         // active "pick on preview" request
  health: null,
  canvasDims() { return this.store.draft?.canvas || { w: 1920, h: 1080 }; },
  words() { return this.store.timing?.words || []; },
  duration() { return this.store.timing?.duration || this.store.draft?.end?.t || 0; },
  draftPlain() { return stripDerived(this.store.draft); },
  tech(id) { return this.reg.byId[id] || null; },
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

/** First image slot asset of a shot: {key, asset}. */
export function primaryAsset(shot) {
  const sb = ctx.store.draft;
  const slots = shot?.slots || {};
  for (const v of Object.values(slots)) {
    const a = v?.asset && sb.assets[v.asset];
    if (a && a.width && a.height && a.kind !== 'video') return { key: v.asset, asset: a };
  }
  return null;
}

export function assetThumbUrl(key, api) {
  const info = ctx.assetInfo[key];
  const a = ctx.store.draft?.assets?.[key];
  return api.url(info?.thumb_url || a?.thumb_url || '') || '';
}
