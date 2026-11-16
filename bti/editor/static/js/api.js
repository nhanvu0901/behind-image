// API layer: the real HTTP client (design section 9) or, with ?mock=1, in-browser fixtures.
import { API_BASE, MOCK } from './config.js';
import { ApiError } from './errors.js';

export { ApiError };

async function parse(res, url) {
  const ct = res.headers.get('content-type') || '';
  const body = ct.includes('json') ? await res.json().catch(() => null) : await res.text().catch(() => '');
  if (!res.ok) throw new ApiError(res.status, body, url);
  return body;
}
const jget = async (path) => { const u = API_BASE + path; return parse(await fetch(u), u); };
const jsend = async (method, path, body) => {
  const u = API_BASE + path;
  return parse(await fetch(u, { method, headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }), u);
};
const P = (pid) => `/api/projects/${encodeURIComponent(pid)}`;
const qs = (o) => new URLSearchParams(Object.entries(o).filter(([, v]) => v !== undefined && v !== null && v !== '')).toString();

const real = {
  mode: 'real',
  health: () => jget('/api/health'),
  style: (style) => jget(`/api/styles/${style}`),
  projects: () => jget('/api/projects'),
  project: (pid) => jget(P(pid)),
  save: (pid, storyboard, base_rev) => jsend('PUT', `${P(pid)}/storyboard`, { storyboard, base_rev }),
  validate: (pid, storyboard) => jsend('POST', `${P(pid)}/validate`, { storyboard }),
  defaults: (pid, technique, context) => jsend('POST', `${P(pid)}/defaults`, { technique, context }),
  approve: (pid, rev) => jsend('POST', `${P(pid)}/approve`, { rev }),
  async frame(pid, t, width, storyboard) {
    const u = `${API_BASE}${P(pid)}/frame`;
    const res = await fetch(u, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ t, width, storyboard }) });
    if (!res.ok) throw new ApiError(res.status, await res.text().catch(() => ''), u);
    return res.blob();
  },
  thumbUrl: (pid, shotId, rev) => `${API_BASE}${P(pid)}/thumb/${encodeURIComponent(shotId)}?${qs({ rev })}`,
  waveform: (pid, bins = 4000) => jget(`${P(pid)}/waveform?bins=${bins}`),
  audioUrl: (pid) => `${API_BASE}${P(pid)}/audio`,
  preview: (pid, body) => jsend('POST', `${P(pid)}/preview`, body),
  job: (id) => jget(`/api/jobs/${encodeURIComponent(id)}`),
  /** result_url / thumb_url may be root-relative; make them loadable. */
  url: (u) => (u && u.startsWith('/') ? API_BASE + u : u),
  fileUrl: (pid, path) => `${API_BASE}${P(pid)}/files/${path.split('/').map(encodeURIComponent).join('/')}`,
  assets: (pid) => jget(`${P(pid)}/assets`),
  putRegions: (pid, key, regions) => jsend('PUT', `${P(pid)}/assets/${encodeURIComponent(key)}/regions`, { regions }),
  async upload(pid, form) {
    const u = `${API_BASE}${P(pid)}/assets/upload`;
    return parse(await fetch(u, { method: 'POST', body: form }), u);
  },
  search: (q_, source, kind, limit = 24) => jget(`/api/media/search?${qs({ q: q_, source, kind, limit })}`),
  importAsset: (pid, source, source_id) => jsend('POST', `${P(pid)}/assets/import`, { source, source_id }),
  proposals: (pid) => jget(`${P(pid)}/proposals`),
  proposal: (pid, id) => jget(`${P(pid)}/proposals/${encodeURIComponent(id)}`),
  applyProposal: (pid, id, accept) => jsend('POST', `${P(pid)}/proposals/${encodeURIComponent(id)}/apply`, { accept }),
};

export const api = MOCK ? (await import('./mockapi.js')).mockApi : real;
