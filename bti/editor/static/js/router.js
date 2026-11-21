// Hash routes of the app. Pure functions (no DOM), tested in tests/editor_frontend/router.test.mjs.
//   #/                                  home (projects)
//   #/library                           library: artworks      #/library/books   shelf
//   #/library/book/<id>                 works of a book        #/library/work/<book>/<n>   a work
//   #/library/artwork/<key>             dossier of an artwork
//   #/project/<id>                      opens the step the stage calls for
//   #/project/<id>/<step>               step: artwork | script | voice | picks | edit | export
export const STEP_IDS = ['artwork', 'script', 'voice', 'picks', 'edit', 'export'];
const PID = /^[a-z0-9][a-z0-9_-]{0,63}$/;

const clean = (hash) => String(hash || '').replace(/^#/, '').split('?')[0];
const dec = (s) => { try { return decodeURIComponent(s); } catch { return s; } };

export function parseHash(hash) {
  const parts = clean(hash).split('/').filter(Boolean).map(dec);
  if (!parts.length) return { name: 'home' };
  if (parts[0] === 'library') {
    const [, a, b, c] = parts;
    if (!a) return { name: 'library', sub: 'artworks' };
    if (a === 'books') return { name: 'library', sub: 'shelf' };
    if (a === 'book' && b) return { name: 'library', sub: 'book', bid: b };
    if (a === 'work' && b && /^\d+$/.test(c || '')) return { name: 'library', sub: 'work', bid: b, n: Number(c) };
    if (a === 'artwork' && b) return { name: 'library', sub: 'artwork', key: parts.slice(2).join('/') };
    return { name: 'notfound', hash: clean(hash) };
  }
  if (parts[0] === 'project') {
    const [, pid, step] = parts;
    if (!pid || !PID.test(pid) || parts.length > 3) return { name: 'notfound', hash: clean(hash) };
    if (!step) return { name: 'project', pid, step: null };
    if (!STEP_IDS.includes(step)) return { name: 'notfound', hash: clean(hash) };
    return { name: 'project', pid, step };
  }
  return { name: 'notfound', hash: clean(hash) };
}

export function formatHash(r) {
  const e = encodeURIComponent;
  switch (r.name) {
    case 'home': return '#/';
    case 'library':
      if (r.sub === 'shelf') return '#/library/books';
      if (r.sub === 'book') return `#/library/book/${e(r.bid)}`;
      if (r.sub === 'work') return `#/library/work/${e(r.bid)}/${r.n}`;
      if (r.sub === 'artwork') return `#/library/artwork/${r.key.split('/').map(e).join('/')}`;
      return '#/library';
    case 'project': return `#/project/${e(r.pid)}${r.step ? '/' + r.step : ''}`;
    default: return '#/';
  }
}
export const projectHash = (pid, step) => formatHash({ name: 'project', pid, step: step || null });

/** Hash routes of the old library.html -> routes of the app. */
export function legacyLibraryHash(hash) {
  const p = clean(hash).split('/').filter(Boolean);
  if (!p.length) return '#/library';
  if (p[0] === 'books') return '#/library/books';
  if (p[0] === 'projects') return '#/';
  if (p[0] === 'artwork' && p[1]) return '#/library/artwork/' + p.slice(1).join('/');
  if (p[0] === 'book' && p[1]) return `#/library/book/${p[1]}`;
  if (p[0] === 'work' && p[1] && p[2]) return `#/library/work/${p[1]}/${p[2]}`;
  return '#/library';
}

/**
 * The old addresses: /library.html (with its hash), /script.html?project=..., and /?project=...
 * Returns { search, hash } to open on `/`, or null when the address is already an address of the app.
 * `?mock=1`, `?all=1` and the other parameters are kept; only `project` is consumed.
 */
export function legacyTarget({ pathname = '/', search = '', hash = '' } = {}) {
  const sp = new URLSearchParams(search);
  const pid = sp.get('project') || '';
  const validPid = PID.test(pid) ? pid : '';
  const rest = () => { const c = new URLSearchParams(sp); c.delete('project'); const s = c.toString(); return s ? '?' + s : ''; };
  const file = pathname.split('/').pop();
  if (file === 'library.html') return { search: rest(), hash: legacyLibraryHash(hash) };
  if (file === 'script.html') return { search: rest(), hash: validPid ? projectHash(validPid, 'script') : '#/' };
  if (file === 'index.html' || file === '') {
    if (sp.has('project') && !clean(hash)) return { search: rest(), hash: validPid ? projectHash(validPid, 'edit') : '#/' };
    if (sp.has('project')) return { search: rest(), hash: hash };
  }
  return null;
}
