// Mock API: same surface as the real client, backed by fixtures in ./mock and in-memory state.
import { derive, stripDerived, clone, MIN_SHOT, shotIndexAt } from './logic.js';
import { defaultParams } from './formgen.js';
import { renderMockFrame, thumbDataUrl, assetThumb } from './placeholder.js';
import { ApiError } from './errors.js';
import { PREVIEW_BASE } from './config.js';

const fx = (n) => fetch(new URL(`../mock/${n}`, import.meta.url)).then((r) => r.json());
const delay = (ms = 60) => new Promise((r) => setTimeout(r, ms));
let S = null; // state
let jobs = {};

async function init() {
  if (S) return S;
  const [reg, timing, sb, prop, intents] = await Promise.all([fx('techniques.json'), fx('timing.json'), fx('storyboard.json'), fx('proposal.json'), fx('intents.json')]);
  S = { reg, timing, sb, rev: 'mock-rev-1', n: 1, prop, intents: intents.intents, applied: false, thumbs: {}, assetThumbs: {} };
  return S;
}
const resolved = (sb) => derive(clone(sb), S.timing);
const techById = (id) => S.reg.techniques.find((t) => t.id === id);

function validate(sb) {
  const issues = [];
  const r = resolved(stripDerived(sb));
  r.shots.forEach((s, i) => {
    const t = techById(s.technique);
    if (!t) issues.push({ level: 'error', path: `shots[${i}].technique`, message: `Kỹ thuật không có trong registry: ${s.technique}` });
    else {
      if (!['base', 'card'].includes(t.kind)) issues.push({ level: 'error', path: `shots[${i}].technique`, message: `${s.technique} là kind ${t.kind}, shot cần base hoặc card` });
      if (t.engine.available === false) issues.push({ level: 'warn', path: `shots[${i}].technique`, message: `${s.technique} chưa render được` });
      const known = new Set(t.params.map((p) => p.name));
      for (const k of Object.keys(s.params || {})) if (!known.has(k)) issues.push({ level: 'error', path: `shots[${i}].params.${k}`, message: `Tham số không xác định: ${k}` });
      for (const sl of t.slots) if (sl.required && !s.slots?.[sl.name]?.asset) issues.push({ level: 'error', path: `shots[${i}].slots.${sl.name}`, message: `Slot bắt buộc còn trống: ${sl.name}` });
    }
    if (s._t1 - s._t0 < MIN_SHOT - 1e-9) issues.push({ level: 'error', path: `shots[${i}].start`, message: 'Shot ngắn hơn 0.2 s' });
    (s.overlays || []).forEach((o, j) => {
      const ot = techById(o.technique);
      if (!ot) issues.push({ level: 'error', path: `shots[${i}].overlays[${j}].technique`, message: `Kỹ thuật không có trong registry: ${o.technique}` });
      if (o._t0 < s._t0 - 1e-6 || o._t0 + (o.dur || 0) > s._t1 + 1e-6) issues.push({ level: 'warn', path: `shots[${i}].overlays[${j}].start`, message: 'Lớp phủ vượt ra ngoài shot' });
    });
  });
  return issues;
}

const projectBody = () => ({ storyboard: resolved(S.sb), timing: S.timing, issues: validate(S.sb), rev: S.rev });

export const mockApi = {
  mode: 'mock',
  async health() { await init(); return { ok: true, engine: 'stub', media: 'stub', mock: true }; },
  async style() { await init(); return { style: await fx('style.json'), techniques: S.reg.techniques, intents: S.intents }; },
  async projects() { await init(); return [{ id: 'arnolfini-mock', title: S.sb.title, duration: S.timing.duration, updated_at: '2026-11-16T09:00:00Z' }, { id: 'empty-demo', title: 'Dự án trống (mock)', duration: 0, updated_at: '2026-11-10T09:00:00Z' }]; },
  async project(pid) { await init(); await delay(); return projectBody(); },
  async save(pid, storyboard, base_rev) {
    await init(); await delay(120);
    if (base_rev !== S.rev) throw new ApiError(409, { error: 'rev_conflict', rev: S.rev }, 'save');
    const issues = validate(storyboard);
    if (issues.some((i) => i.level === 'error')) throw new ApiError(422, { issues }, 'save');
    S.sb = clone(stripDerived(storyboard)); S.n++; S.rev = 'mock-rev-' + S.n;
    return { rev: S.rev, storyboard: resolved(S.sb), issues };
  },
  async validate(pid, storyboard) { await init(); return { issues: validate(storyboard) }; },
  async defaults(pid, technique, context) {
    await init(); const t = techById(technique);
    const params = defaultParams(t.params);
    const asset = context?.assets && Object.values(context.assets)[0];
    for (const p of t.params) if (p.type === 'camera' && asset) {
      params.camera = [
        { at: { rel: 0 }, cx: asset.width / 2, cy: asset.height / 2, zoom: Math.min(1920 / asset.width, 1080 / asset.height), ease: 'linear' },
        { at: { rel: 1 }, cx: asset.width / 2, cy: asset.height / 2, zoom: Math.min(1920 / asset.width, 1080 / asset.height) * (p.default?.zoom_ratio || 1.5), ease: 'linear' }];
    }
    return { params };
  },
  async approve(pid, rev) { return { approvals: { storyboard: { rev, at: new Date().toISOString() } } }; },
  async frame(pid, t, width, storyboard) {
    await init(); await delay(40);
    const sb = resolved(stripDerived(storyboard));
    const c = renderMockFrame(sb, t, width);
    return new Promise((res) => c.toBlob(res, 'image/jpeg', 0.85));
  },
  thumbUrl(pid, shotId) {
    if (!S) return '';
    const sb = resolved(S.sb), shot = sb.shots.find((s) => s.id === shotId);
    if (!shot) return '';
    const key = shotId + S.rev;
    return (S.thumbs[key] ||= thumbDataUrl(sb, shot));
  },
  async waveform(pid, bins = 4000) {
    await init(); const peaks = [];
    const w = S.timing.words;
    for (let i = 0; i < bins; i++) {
      const t = (i / bins) * S.timing.duration;
      let lo = 0, hi = w.length - 1, k = -1;
      while (lo <= hi) { const m = (lo + hi) >> 1; if (w[m].s <= t) { k = m; lo = m + 1; } else hi = m - 1; }
      const speaking = k >= 0 && t < w[k].e;
      peaks.push(speaking ? 0.25 + 0.7 * Math.abs(Math.sin(i * 0.9) * Math.cos(i * 0.31)) : 0.03);
    }
    return { duration: S.timing.duration, peaks };
  },
  audioUrl() { return null; },
  async preview(pid, body) {
    await init();
    const id = 'job' + Math.random().toString(36).slice(2, 8);
    const sb = resolved(stripDerived(body.storyboard || S.sb));
    const tech = sb.shots[shotIndexAt(sb.shots, body.t0)].technique;
    jobs[id] = { t: Date.now(), tech };
    return { job_id: id };
  },
  async job(id) {
    const j = jobs[id]; const p = Math.min(1, (Date.now() - j.t) / 1500);
    return p < 1 ? { state: 'running', progress: p } : { state: 'done', progress: 1, result_url: `${PREVIEW_BASE}${j.tech}.mp4` };
  },
  url: (u) => u,
  fileUrl: (pid, path) => path,
  async assets() {
    await init();
    return Object.fromEntries(Object.entries(S.sb.assets).map(([k, a]) => [k, { ...a, thumb_url: (S.assetThumbs[k] ||= assetThumb(k, a)) }]));
  },
  async putRegions(pid, key, regions) { await init(); S.sb.assets[key].regions = clone(regions); return { regions }; },
  async upload(pid, form) {
    await init(); await delay(200);
    const key = 'U' + (Object.keys(S.sb.assets).length + 1);
    const asset = { file: 'media/' + (form.get('file')?.name || 'upload.jpg'), kind: 'image', title: form.get('title') || 'Tải lên', artist: form.get('artist') || '', year: form.get('year') || '',
      width: 3200, height: 2400, credit: { source: 'upload', source_url: form.get('source_url'), author: form.get('author'), licence: form.get('licence'), licence_url: '' }, regions: {} };
    S.sb.assets[key] = asset; asset.thumb_url = S.assetThumbs[key] = assetThumb(key, asset);
    return { asset_key: key, asset };
  },
  async search(q, source = 'commons', kind = 'image', limit = 24) {
    await init(); await delay(250);
    const base = [
      ['Mirror detail, Arnolfini Portrait', 'Jan van Eyck', 'PD', true, ''],
      ['Wedding portrait, Bruges 1434', 'Wikimedia contributors', 'CC BY-SA 4.0', true, ''],
      ['Convex mirror in Flemish painting', 'M. Dupont', 'CC BY 3.0', true, ''],
      ['Candle chandelier close-up', 'A. Rossi', 'CC BY-NC 2.0', false, 'Giấy phép NC không được phép'],
      ['National Gallery interior photo', 'Press agency', 'All rights reserved', false, 'Giấy phép không rõ hoặc không cho phép'],
      ['Oil glazing diagram', 'Open Museum', 'CC0', true, ''],
      ['X-ray of a panel painting', 'Getty', 'Fair use', false, 'Fair use không được chấp nhận'],
      ['Van Eyck signature inscription', 'Wikimedia contributors', 'PD', true, ''],
    ];
    const f = (q || '').toLowerCase();
    return base.filter(([t]) => !f || t.toLowerCase().includes(f.split(' ')[0]) || f.length < 3).slice(0, limit).map(([title, author, licence, ok, reason], i) => ({
      source, source_id: `${source}:${i}`, title, thumb_url: assetThumb('M' + i, { width: 1600, height: 1200, title: '', regions: {} }), page_url: 'https://commons.wikimedia.org/',
      width: 1600 + i * 200, height: 1200 + i * 100, mime: kind === 'video' ? 'video/webm' : 'image/jpeg', author, licence, licence_ok: ok, licence_reason: reason,
    }));
  },
  async importAsset(pid, source, source_id) {
    await init(); await delay(300);
    const key = 'I' + (Object.keys(S.sb.assets).length + 1);
    const asset = { file: `media/${key}.jpg`, kind: 'image', title: 'Ảnh nhập (' + source_id + ')', artist: '', year: '', width: 2400, height: 1800,
      credit: { source, source_url: 'https://commons.wikimedia.org/', author: 'Wikimedia contributors', licence: 'CC BY-SA 4.0', licence_url: '' }, regions: {} };
    S.sb.assets[key] = asset; asset.thumb_url = S.assetThumbs[key] = assetThumb(key, asset);
    return { asset_key: key, asset };
  },
  async proposals() {
    await init();
    return S.applied ? [] : [{ id: S.prop.proposal.id, created_at: S.prop.proposal.created_at, author: S.prop.proposal.author, summary: S.prop.proposal.summary, n_changes: S.prop.changes.length }];
  },
  async proposal() { await init(); return clone(S.prop); },
  async applyProposal(pid, id, accept) {
    await init(); await delay(150);
    const ids = accept === 'all' ? S.prop.changes.filter((c) => !c.blocked_by_lock).map((c) => c.id) : accept;
    if (ids.includes('c1')) { const s = S.sb.shots.find((x) => x.id === 's0008'); s.technique = 'CAM-01'; s.params = { camera: s.params.camera }; }
    if (ids.includes('c5')) S.sb.shots.find((x) => x.id === 's0010').intent = 'reveal';
    if (ids.includes('c2')) S.sb.shots.find((x) => x.id === 's0002').overlays.push(clone(S.prop.changes[1].after));
    S.n++; S.rev = 'mock-rev-' + S.n; S.applied = true;
    return { rev: S.rev, storyboard: resolved(S.sb), issues: validate(S.sb) };
  },
};
