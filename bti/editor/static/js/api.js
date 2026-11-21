// The one API client: the real HTTP client (design section 9) or, with ?mock=1, in-browser fixtures for the editing view.
// Requests made while a view is mounted carry that view's AbortSignal (set by the shell with setViewSignal). When a view
// is left, its requests are cancelled and their promises never settle, so no stray handler runs on a dead view.
import { API_BASE, MOCK } from './config.js';
import { ApiError } from './errors.js';

export { ApiError };

let viewSignal = null;
/** Called by the shell: requests that do not pass their own `signal` use this one. */
export const setViewSignal = (s) => { viewSignal = s; };

let netDown = false, netHook = null;
/** The shell asks to be told when the server stops answering ('down', url) and when it answers again ('up', url). */
export const setNetworkHook = (fn) => { netHook = fn; };
const net = (state, u) => { if (state === 'up' ? !netDown : netDown && state === 'down') return; netDown = state === 'down'; try { netHook?.(state, u); } catch { /* the hook never breaks a request */ } };

const hang = () => new Promise(() => {});
const url = (path) => API_BASE + path;
const JSON_HEADERS = { 'content-type': 'application/json' };

async function readBody(res) {
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('json')) return res.json().catch(() => null);
  return res.text().catch(() => '');
}

/** One request. `opts.signal`: an AbortSignal, or null for none (shell calls). `opts.raw`: return the Response body as blob/text. */
async function request(method, path, body, opts = {}) {
  const u = url(path);
  const signal = opts.signal !== undefined ? opts.signal : viewSignal;
  const init = { method, signal: signal || undefined };
  if (body instanceof FormData) init.body = body;
  else if (body !== undefined) { init.headers = JSON_HEADERS; init.body = JSON.stringify(body); }
  try {
    const res = await fetch(u, init);
    net('up', u);
    if (!res.ok) {
      const err = await readBody(res);
      throw new ApiError(res.status, err, u);
    }
    if (opts.as === 'blob') return await res.blob();
    return await readBody(res);
  } catch (e) {
    if (e?.name === 'AbortError' || signal?.aborted) return hang();
    if (e?.name === 'TypeError') net('down', u);
    throw e;
  }
}
const P = (pid) => `/api/projects/${encodeURIComponent(pid)}`;
const qs = (o) => new URLSearchParams(Object.entries(o).filter(([, v]) => v !== undefined && v !== null && v !== '')).toString();

const real = {
  mode: 'real',
  // generic verbs (paths start with /api): used by the library and script views
  get: (path, opts) => request('GET', path, undefined, opts),
  send: (method, path, body, opts) => request(method, path, body ?? {}, opts),
  post: (path, body, opts) => request('POST', path, body ?? {}, opts),
  put: (path, body, opts) => request('PUT', path, body ?? {}, opts),
  del: (path, opts) => request('DELETE', path, undefined, opts),
  // app shell
  health: () => request('GET', '/api/health', undefined, { signal: null }),
  pipeline: (pid) => request('GET', `${P(pid)}/pipeline`, undefined, { signal: null }),
  pipelineTemplate: () => request('GET', '/api/pipeline', undefined, { signal: null }),
  deleteProject: (pid, confirm) => request('DELETE', `${P(pid)}?${qs({ confirm })}`, undefined, { signal: null }),
  // editing view
  style: (style) => request('GET', `/api/styles/${style}`),
  projects: (opts) => request('GET', '/api/projects', undefined, opts),
  project: (pid) => request('GET', P(pid)),
  save: (pid, storyboard, base_rev) => request('PUT', `${P(pid)}/storyboard`, { storyboard, base_rev }),
  validate: (pid, storyboard) => request('POST', `${P(pid)}/validate`, { storyboard }),
  defaults: (pid, technique, context) => request('POST', `${P(pid)}/defaults`, { technique, context }),
  approve: (pid, rev) => request('POST', `${P(pid)}/approve`, { rev }),
  frame: (pid, t, width, storyboard) => request('POST', `${P(pid)}/frame`, { t, width, storyboard }, { as: 'blob' }),
  thumbUrl: (pid, shotId, rev) => `${API_BASE}${P(pid)}/thumb/${encodeURIComponent(shotId)}?${qs({ rev })}`,
  waveform: (pid, bins = 4000) => request('GET', `${P(pid)}/waveform?bins=${bins}`),
  audioUrl: (pid) => `${API_BASE}${P(pid)}/audio`,
  preview: (pid, body) => request('POST', `${P(pid)}/preview`, body),
  job: (id) => request('GET', `/api/jobs/${encodeURIComponent(id)}`),
  /** result_url / thumb_url may be root-relative; make them loadable. */
  url: (u) => (u && u.startsWith('/') ? API_BASE + u : u),
  fileUrl: (pid, path) => `${API_BASE}${P(pid)}/files/${path.split('/').map(encodeURIComponent).join('/')}`,
  assets: (pid) => request('GET', `${P(pid)}/assets`),
  putRegions: (pid, key, regions) => request('PUT', `${P(pid)}/assets/${encodeURIComponent(key)}/regions`, { regions }),
  upload: (pid, form) => request('POST', `${P(pid)}/assets/upload`, form),
  search: (q_, source, kind, limit = 24) => request('GET', `/api/media/search?${qs({ q: q_, source, kind, limit })}`),
  importAsset: (pid, source, source_id) => request('POST', `${P(pid)}/assets/import`, { source, source_id }),
  proposals: (pid) => request('GET', `${P(pid)}/proposals`),
  proposal: (pid, id) => request('GET', `${P(pid)}/proposals/${encodeURIComponent(id)}`),
  applyProposal: (pid, id, accept, base_rev) => request('POST', `${P(pid)}/proposals/${encodeURIComponent(id)}/apply`, { accept, base_rev }),
};

export const api = MOCK ? (await import('./mockapi.js')).mockApi : real;
