// Everything a view starts must be stoppable. A view gets one Scope; the shell disposes it when the view is left:
// timers, intervals, animation frames, listeners on document/window, pending requests (via `signal`), audio, observers.
export function createScope() {
  const ac = new AbortController();
  let fns = [], dead = false;
  const scope = {
    signal: ac.signal,
    get dead() { return dead; },
    /** addEventListener that is removed on dispose. */
    on(target, evt, fn, opts) { target.addEventListener(evt, fn, opts); fns.push(() => target.removeEventListener(evt, fn, opts)); },
    interval(fn, ms) { const id = setInterval(() => { if (!dead) fn(); }, ms); fns.push(() => clearInterval(id)); return id; },
    timeout(fn, ms) { const id = setTimeout(() => { if (!dead) fn(); }, ms); fns.push(() => clearTimeout(id)); return id; },
    raf(fn) { const id = requestAnimationFrame(() => { if (!dead) fn(); }); fns.push(() => cancelAnimationFrame(id)); return id; },
    /** Register any cleanup function (disconnect an observer, stop audio, remove an element...). */
    add(fn) { if (dead) { try { fn(); } catch { /* already gone */ } } else fns.push(fn); },
    dispose() {
      if (dead) return;
      dead = true;
      ac.abort();
      const all = fns; fns = [];
      for (const fn of all.reverse()) { try { fn(); } catch { /* keep disposing */ } }
    },
  };
  return scope;
}
