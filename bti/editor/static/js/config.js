// The ONLY place that knows where the backend lives. Override at runtime with ?api=<url>&previews=<url>.
// The page address keeps ?mock=1, ?all=1, ?api= and ?previews= while the app moves between hash routes.
const q = new URLSearchParams(typeof location === 'undefined' ? '' : location.search);

export const MOCK = q.get('mock') === '1';
/** ?all=1 also lists the lab_* and demo_* projects. */
export const SHOW_ALL = q.has('all');
/** Base URL of the HTTP API (design section 9). '' = same origin as the page. */
export const API_BASE = (q.get('api') || '').replace(/\/$/, '');
/** Base URL of the technique preview clips and thumbnails (`/style/{style}/previews/{file}`). */
export const PREVIEW_BASE = (q.get('previews') || `${API_BASE}/style/gae/previews/`).replace(/\/?$/, '/');
export const STYLE_ID = 'gae';
export const DEBOUNCE_MS = 150;
