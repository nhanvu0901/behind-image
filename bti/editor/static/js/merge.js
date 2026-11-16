// Three-way merge of a document the user is editing (mine) with the version the server now has (theirs), both
// derived from `base`, the last version the page knew. Rule of the script view: a server answer must never
// overwrite something the user typed. Whatever only the user changed is kept, whatever only the server changed
// (a job that wrote a chapter) is taken, and when both changed the same unit it is a conflict the owner decides.
// Units: the keys of the document, and the elements of the `collections` (chapters, facts...) by `id`.
// Inside a unit the merge goes deeper (a chapter's beats are merged by id too) before it gives up.
// Pure; tested in tests/editor_frontend/merge.test.mjs.

const isObj = (x) => x !== null && typeof x === 'object' && !Array.isArray(x);

export function deepEqual(a, b) {
  if (a === b) return true;
  if (typeof a !== typeof b || a === null || b === null) return false;
  if (Array.isArray(a)) return Array.isArray(b) && a.length === b.length && a.every((x, i) => deepEqual(x, b[i]));
  if (isObj(a)) {
    if (!isObj(b)) return false;
    const ka = Object.keys(a).filter((k) => a[k] !== undefined), kb = Object.keys(b).filter((k) => b[k] !== undefined);
    return ka.length === kb.length && ka.every((k) => deepEqual(a[k], b[k]));
  }
  return false;
}

const isIdArray = (a) => Array.isArray(a) && a.every((x) => isObj(x) && typeof x.id === 'string');
const FAIL = { ok: false };
const ok = (value) => ({ ok: true, value });

function deep3(b, m, t) {
  if (deepEqual(m, t)) return ok(m);
  if (deepEqual(m, b)) return ok(t);
  if (deepEqual(t, b)) return ok(m);
  if (isObj(m) && isObj(t) && (isObj(b) || b === undefined)) {
    const out = {};
    for (const k of new Set([...Object.keys(m), ...Object.keys(t)])) {
      const r = deep3(b?.[k], m[k], t[k]);
      if (!r.ok) return FAIL;
      if (r.value !== undefined) out[k] = r.value;
    }
    return ok(out);
  }
  if (isIdArray(m) && isIdArray(t) && (b === undefined || isIdArray(b))) {
    const r = mergeIdArray(b || [], m, t, null);
    return r.conflicts.length ? FAIL : ok(r.value);
  }
  return FAIL;
}

/** Order of the merged ids: the side that reordered wins; ids only the other side has are put after their predecessor. */
function mergeOrder(bIds, mIds, tIds) {
  const both = (x, y) => { const s = new Set(y); return x.filter((i) => s.has(i)); };
  const changed = (cur) => !deepEqual(both(bIds, cur), both(cur, bIds));
  const [first, second] = changed(mIds) ? [mIds, tIds] : [tIds, mIds];
  const out = [...first];
  second.forEach((id, i) => {
    if (out.includes(id)) return;
    let at = 0;
    for (let k = i - 1; k >= 0; k--) { const p = out.indexOf(second[k]); if (p >= 0) { at = p + 1; break; } }
    out.splice(at, 0, id);
  });
  return out;
}

/** Merge arrays of {id} elements. `conflicts` (an array, or null for "just report") collects units both sides changed.
 *  `choices[id]` = 'theirs' | 'mine' (default 'mine': the owner's text is never dropped silently). */
function mergeIdArray(b, m, t, key, choices = {}) {
  const idx = (a) => new Map(a.map((x) => [x.id, x]));
  const B = idx(b), M = idx(m), T = idx(t);
  const ids = mergeOrder(b.map((x) => x.id), m.map((x) => x.id), t.map((x) => x.id));
  const conflicts = [], out = [];
  for (const id of ids) {
    const bb = B.get(id), mm = M.get(id), tt = T.get(id);
    let res, conflict = false;
    if (mm && tt) {
      if (deepEqual(mm, tt)) res = mm;
      else if (bb) { const r = deep3(bb, mm, tt); if (r.ok) res = r.value; else conflict = true; }
      else conflict = true;
    } else if (mm) { if (!bb) res = mm; else if (deepEqual(mm, bb)) res = undefined; else conflict = true; }
    else if (tt) { if (!bb) res = tt; else if (deepEqual(tt, bb)) res = undefined; else conflict = true; }
    if (conflict) {
      conflicts.push({ key, id, mine: mm, theirs: tt });
      res = (choices[id] === 'theirs') ? tt : mm;
    }
    if (res !== undefined) out.push(res);
  }
  return { value: out, conflicts };
}

/**
 * mergeDoc(base, mine, theirs, { collections: ['chapters'] }, choices)
 * -> { value, conflicts: [{ key, id?, mine, theirs }] }. `choices` maps "key" or "key:id" to 'theirs' or 'mine'.
 */
export function mergeDoc(base, mine, theirs, { collections = [] } = {}, choices = {}) {
  if (!mine) return { value: theirs, conflicts: [] };
  if (!theirs) return { value: mine, conflicts: [] };
  base = base || {};
  const value = {}, conflicts = [];
  for (const k of new Set([...Object.keys(mine), ...Object.keys(theirs)])) {
    const b = base[k], m = mine[k], t = theirs[k];
    if (collections.includes(k) && Array.isArray(m ?? []) && Array.isArray(t ?? []) && isIdArray(m ?? []) && isIdArray(t ?? [])) {
      const ch = {};
      for (const [ck, v] of Object.entries(choices)) if (ck.startsWith(k + ':')) ch[ck.slice(k.length + 1)] = v;
      const r = mergeIdArray(Array.isArray(b) ? b : [], m ?? [], t ?? [], k, ch);
      value[k] = r.value; conflicts.push(...r.conflicts);
      continue;
    }
    const r = deep3(b, m, t);
    if (r.ok) { if (r.value !== undefined) value[k] = r.value; }
    else {
      conflicts.push({ key: k, mine: m, theirs: t });
      const v = choices[k] === 'theirs' ? t : m;
      if (v !== undefined) value[k] = v;
    }
  }
  return { value, conflicts };
}
