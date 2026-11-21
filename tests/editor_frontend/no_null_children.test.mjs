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

/** Names of the functions of a file whose body can return null / undefined / false (a `return null`, a bare `return`, or `: null`). */
export function nullableFns(masked) {
  const out = new Set();
  const re = /(?:function\s+([\w$]+)\s*\(|(?:const|let)\s+([\w$]+)\s*=\s*(?:async\s*)?\()/g;
  let m;
  while ((m = re.exec(masked))) {
    const name = m[1] || m[2];
    let k = re.lastIndex, depth = 1;                         // skip the parameter list
    for (; k < masked.length && depth > 0; k++) { if (masked[k] === '(') depth++; else if (masked[k] === ')') depth--; }
    while (/\s/.test(masked[k] || '')) k++;
    if (masked.startsWith('=>', k)) { k += 2; while (/\s/.test(masked[k] || '')) k++; }
    else if (m[2] && masked[k] !== '{') continue;            // `const x = (a + b)`: not a function
    let body;
    if (masked[k] === '{') {
      let d = 0, e = k;
      for (; e < masked.length; e++) { if (masked[e] === '{') d++; else if (masked[e] === '}') { d--; if (d === 0) break; } }
      body = masked.slice(k, e);
    } else {
      const e = masked.indexOf('\n', k);
      body = masked.slice(k, e < 0 ? undefined : e);
    }
    if (/\breturn\s*(null|undefined|false)?\s*[;}\n]|:\s*(null|undefined)\b|^\s*(null|undefined)\b/.test(body)) out.add(name);
  }
  return out;
}
/** True when the parenthesis opened just before `from` closes at the very end of `a` (one single call, not `f(x) + g(y)`). */
function closesAtEnd(a, from) {
  let depth = 1;
  for (let i = from; i < a.length; i++) {
    if ('([{'.includes(a[i])) depth++;
    else if (')]}'.includes(a[i])) { depth--; if (depth === 0) return i === a.length - 1; }
  }
  return false;
}

/** Why this argument may be null/undefined/false, or '' when it cannot be. */
export function risky(arg, nullable = new Set()) {
  const a = arg.trim();
  if (!a) return '';
  if (/^(null|undefined|false)$/.test(a)) return 'a literal null/undefined/false';
  if (a.startsWith('...')) {
    const r = a.slice(3).trim();
    if (/^kids\(/.test(r) || /\.filter\(Boolean\)$/.test(r)) return '';                  // filtered
    if (/=>\s*[^{(]*\?[^:]*:\s*(null|undefined|false)\s*\)\s*$/.test(r)) return 'a spread whose items may be null/undefined/false';
    return '';
  }
  // a call to a helper of this file that can return null (staleBox(d), lastErrorBox()...)
  const call = /^([\w$]+)\(/.exec(a);
  if (call && nullable.has(call[1]) && closesAtEnd(a, call[0].length)) return 'a call to ' + call[1] + '(), which can return null: wrap it in kids(...)';
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
    const nul = nullableFns(masked);
    for (const c of calls(masked)) {
      for (const [arg, off] of c.args) {
        const why = risky(arg, nul);
        if (why) bad.push(`${path.relative(JS, f)}:${src.slice(0, c.at).split('\n').length}: ${why}: ${src.slice(off, off + arg.length).trim().replace(/\s+/g, ' ').slice(0, 100)}`);
      }
    }
  }
  assert.deepEqual(bad, [], '\nwrap conditional children in kids(...) from util.js, or build them with h():\n' + bad.join('\n'));
});

test('the detector itself catches the shapes it is meant to catch', () => {
  const found = (s) => { const m = mask(s); const nul = nullableFns(m); return calls(m).flatMap((c) => c.args.map(([a]) => risky(a, nul))).filter(Boolean).length; };
  assert.equal(found('el.append(run ? h("button") : null)'), 1);
  assert.equal(found('el.append(a, !run && h("b"))'), 1);
  assert.equal(found('el.append(null)'), 1);
  assert.equal(found('el.replaceChildren(...rows.map((r) => r.ok ? h("a") : null))'), 1);
  assert.equal(found('el.append(run ? h("a") : h("b"), "x, y", `a ${b ? 1 : 2}`)'), 0);
  assert.equal(found('el.append(...kids(run ? h("a") : null))'), 0);
  assert.equal(found('el.append(x?.y ? h("a") : h("b"))'), 0);
  assert.equal(found('function staleBox(d) { if (!d) return null; return h("a"); }\nfunction okBox() { return h("a"); }\nroot.replaceChildren(h("h1"), staleBox(d), okBox())'), 1);      // a helper that returns null
  assert.equal(found('const lastBox = () => { if (!x) return null; return h("b"); };\nroot.replaceChildren(lastBox())'), 1);
  assert.equal(found('const sel = () => cond ? h("a") : null;\nroot.replaceChildren(sel())'), 1);
  assert.equal(found('function staleBox(d) { return null; }\nroot.replaceChildren(...kids(h("h1"), staleBox(d)))'), 0);
  assert.equal(found('root.replaceChildren(...rows.filter(Boolean))'), 0);
});
