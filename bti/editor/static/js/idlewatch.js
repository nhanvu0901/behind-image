// A stage page that shows no running job still has to notice a job started somewhere else (another tab, another window).
// `watchIdle` is that one timer: every `every` ms it calls `check()` (one cheap GET), but only when
//  - the tab is visible,        - no dialog is open (unless the page itself lives in a dialog: `ownDialog`),
//  - the page shows no running job (`idle()`),     - the owner is not typing in a field of this page,
//  - the previous check has finished.
// The timer belongs to the view's scope, so it is cleared when the view is left. When the tab becomes visible again a check runs at once.
import { modalOpen } from './util.js';

const FIELD = 'input, textarea, select, [contenteditable="true"]';

/** True while the focus is in a field inside `root` (the owner is typing: a repaint would eat the text). */
export function typingIn(root) {
  const a = document.activeElement;
  return !!(root && a && a !== document.body && root.contains(a) && a.matches?.(FIELD));
}

/** Remembers the newest job of a list between checks. `seen(items)` is 'active' while a job runs, 'changed' once when the newest job
 * is a different one than at the last look (a job that began and ended between two checks), else null. The first look only remembers. */
export function jobWatcher() {
  let last;
  const known = new Set();                     // jobs this page started or followed itself: it repainted when they ended
  const seen = (items) => {
    const list = Array.isArray(items) ? items : items?.items || items?.jobs || [];
    if (list.some((j) => ['queued', 'waiting', 'running'].includes(j.state) && !known.has(j.id))) { last = undefined; return 'active'; }
    const newest = list.slice().sort((a, b) => (b.created || 0) - (a.created || 0))[0]?.id ?? null;
    const first = last === undefined;
    const changed = !first && newest !== last && !known.has(newest);
    last = newest;
    return changed ? 'changed' : null;
  };
  seen.know = (id) => { if (id) known.add(id); };
  return seen;
}

export function watchIdle(scope, { root, idle, check, every = 5000, ownDialog = false }) {
  let busy = false, n = 0;
  const tick = async () => {
    if (scope.dead || busy || document.hidden || (modalOpen() && !ownDialog) || !idle() || typingIn(root?.())) return;
    busy = true; n++;
    try { await check(); } catch { /* a failed check is tried again at the next tick */ } finally { busy = false; }
  };
  scope.interval(tick, every);
  scope.on(document, 'visibilitychange', () => { if (!document.hidden) tick(); });
  tick();                                   // the first look (it only remembers the newest job: a page that just loaded is already up to date)
  return { tick, get checks() { return n; } };
}
