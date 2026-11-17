// `Element.append(null)` and `replaceChildren(false)` write the words "null" and "false" into the page.
// A conditional child must go through h() (which skips null/undefined/false), or through the shared `kids(...)` filter in util.js.
// This test reads every file under static/js and fails when an argument of `.append(` / `.replaceChildren(` / `.prepend(` is
// literally null/undefined/false, a `cond && x` (false when cond is false), or a ternary with a null/undefined/false branch.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const JS = new URL('../../bti/editor/static/js/', import.meta.url).pathname;
const files = [];
const walk = (d) => { for (const f of fs.readdirSync(d, { withFileTypes: true })) { const p = path.join(d, f.name); if (f.isDirectory()) walk(p); else if (f.name.endsWith('.js')) files.push(p); } };
walk(JS);

/** Remove comments and blank out string contents (keeps length and line breaks) so that brackets and commas inside text do not count. */
export function mask(src) {
  let out = '', i = 0;
  const n = src.length;
  while (i < n) {
    const c = src[i], d = src[i + 1];
    if (c === '/' && d === '/') { while (i < n && src[i] !== '\n') { out += ' '; i++; } continue; }
    if (c === '/' && d === '*') { while (i < n && !(src[i] === '*' && src[i + 1] === '/')) { out += src[i] === '\n' ? '\n' : ' '; i++; } out += '  '; i += 2; continue; }
    if (c === '"' || c === "'") { out += c; i++; while (i < n && src[i] !== c && src[i] !== '\n') { if (src[i] === '\\') { out += ' '; i++; } out += ' '; i++; } out += c; i++; continue; }
    if (c === '`') {                               // template literal: keep the ${...} code, blank the text
      out += c; i++;
      while (i < n && src[i] !== '`') {
        if (src[i] === '\\') { out += '  '; i += 2; continue; }
        if (src[i] === '$' && src[i + 1] === '{') {
          let depth = 0; const start = i;
          while (i < n) { if (src[i] === '{') depth++; if (src[i] === '}') { depth--; if (depth === 0) { i++; break; } } i++; }
          out += ' '.repeat(i - start); continue;
        }
        out += src[i] === '\n' ? '\n' : ' '; i++;
      }
      out += c; i++; continue;
    }
    out += c; i++;
  }
  return out;
}

/** The arguments (as masked text with their start offset) of every `.append(` style call. */
export function calls(masked) {
  const res = [];
  const re = /\.(append|replaceChildren|prepend)\(/g;
  let m;
  while ((m = re.exec(masked))) {
    let i = re.lastIndex, depth = 0, start = i; const args = [];
    for (; i < masked.length; i++) {
      const c = masked[i];
      if ('([{'.includes(c)) depth++;
      else if (')]}'.includes(c)) { if (depth === 0) break; depth--; }
      else if (c === ',' && depth === 0) { args.push([masked.slice(start, i), start]); start = i + 1; }
    }
    args.push([masked.slice(start, i), start]);
    res.push({ at: m.index, args });
  }
  return res;
}

/** Why this argument may be null/undefined/false, or '' when it cannot be. */
export function risky(arg) {
  const a = arg.trim();
  if (!a) return '';
  if (/^(null|undefined|false)$/.test(a)) return 'a literal null/undefined/false';
  if (a.startsWith('...')) return risky(a.slice(3));
  let depth = 0, q = -1, colon = -1, andand = false;
  for (let i = 0; i < a.length; i++) {
    const c = a[i];
    if ('([{'.includes(c)) depth++;
    else if (')]}'.includes(c)) depth--;
    else if (depth === 0) {
      if (c === '&' && a[i + 1] === '&') { andand = true; i++; }
      else if (c === '?' && a[i + 1] !== '.' && a[i + 1] !== '?' && q < 0) q = i;
      else if (c === ':' && q >= 0 && colon < 0) colon = i;
    }
  }
  if (q >= 0 && colon > q) {
    const bad = /(^|[^\w.])(null|undefined|false)\s*$/;
    const yes = a.slice(q + 1, colon), no = a.slice(colon + 1);
    if (bad.test(yes.trim()) || bad.test(no.trim())) return 'a ternary with a null/undefined/false branch';
    return '';
  }
  if (andand) return 'a `cond && child` (false when the condition is false)';
  return '';
}

test('no view passes null, undefined or false to append / replaceChildren', () => {
  const bad = [];
  for (const f of files) {
    const src = fs.readFileSync(f, 'utf8');
    const masked = mask(src);
    for (const c of calls(masked)) {
      for (const [arg, off] of c.args) {
        const why = risky(arg);
        if (why) bad.push(`${path.relative(JS, f)}:${src.slice(0, c.at).split('\n').length}: ${why}: ${src.slice(off, off + arg.length).trim().replace(/\s+/g, ' ').slice(0, 100)}`);
      }
    }
  }
  assert.deepEqual(bad, [], '\nwrap conditional children in kids(...) from util.js, or build them with h():\n' + bad.join('\n'));
});

test('the detector itself catches the shapes it is meant to catch', () => {
  const found = (s) => calls(mask(s)).flatMap((c) => c.args.map(([a]) => risky(a))).filter(Boolean).length;
  assert.equal(found('el.append(run ? h("button") : null)'), 1);
  assert.equal(found('el.append(a, !run && h("b"))'), 1);
  assert.equal(found('el.append(null)'), 1);
  assert.equal(found('el.replaceChildren(...rows.map((r) => r.ok ? h("a") : null))'), 0);   // inside a callback: not an argument shape we can judge
  assert.equal(found('el.append(run ? h("a") : h("b"), "x, y", `a ${b ? 1 : 2}`)'), 0);
  assert.equal(found('el.append(...kids(run ? h("a") : null))'), 0);
  assert.equal(found('el.append(x?.y ? h("a") : h("b"))'), 0);
});
