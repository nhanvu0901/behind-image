// Unicode-aware text helpers shared by the views. Pure (no DOM), tested in tests/editor_frontend/text.test.mjs.
// The word counter MUST agree with the server (bti/script/stats.py: count_words = tokens of str.split() that hold a \w):
// whitespace is Python's str.split() whitespace, and a "word character" is any letter, number or underscore of any script.

const WS_CODES = [0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x1c, 0x1d, 0x1e, 0x1f, 0x20, 0x85, 0xa0, 0x1680, 0x2000, 0x2001, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006, 0x2007, 0x2008, 0x2009, 0x200a, 0x2028, 0x2029, 0x202f, 0x205f, 0x3000];   // Python's str.split() whitespace
const WS = new RegExp('[' + WS_CODES.map((c) => '\\u' + c.toString(16).padStart(4, '0')).join('') + ']+');
const WORDCH = /[\p{L}\p{N}_]/u;

/** Tokens separated by whitespace, exactly what the server's `text.split()` gives. */
export const tokens = (text) => String(text ?? '').split(WS).filter(Boolean);
/** Number of whitespace tokens (the server's split/merge operations count these). */
export const tokenCount = (text) => tokens(text).length;
/** Number of words: tokens that hold a letter, a digit or "_" in any script. Same rule as the server. */
export const wordCount = (text) => { let n = 0; for (const t of tokens(text)) if (WORDCH.test(t)) n++; return n; };

// ---------------------------------------------------------------- accent-insensitive search
const EXTRA = { 'đ': 'd', 'Đ': 'D', 'ð': 'd', 'Ð': 'D', 'ł': 'l', 'Ł': 'L', 'ø': 'o', 'Ø': 'O', 'æ': 'ae', 'Æ': 'AE', 'œ': 'oe', 'Œ': 'OE', 'ß': 'ss', 'þ': 'th', 'Þ': 'TH', 'ı': 'i', 'ħ': 'h', 'Ħ': 'H', '’': "'" };   // the same table as bti/textfold.py, so the page and the server fold alike
const MARK = /\p{M}/u;

/** Folded copy of `s` (lower case, no accents, đ -> d) and, for each folded character, the [start, end) range it came from. */
export function foldMap(s) {
  s = String(s ?? '');
  let out = '';
  const from = [], to = [];
  let i = 0;
  for (const ch of s) {
    const start = i, end = i + ch.length; i = end;
    let f = (EXTRA[ch] ?? ch).normalize('NFKD').replace(/ς/g, 'σ');   // NFKD and case folding like the server's fold()
    f = [...f].filter((c) => !MARK.test(c)).join('').toLowerCase();
    for (const c of f) { for (let k = 0; k < c.length; k++) { from.push(start); to.push(end); } out += c; }
  }
  return { text: out, from, to };
}
/** Folded text: "Đức", "duc" and "DỨC" all become "duc". */
export const fold = (s) => foldMap(s).text;

/** First match of `query` in `text`, ignoring case and accents. Returns [start, end) in the ORIGINAL text, or null. */
export function findFolded(text, query) {
  const q = fold(query).trim();
  if (!q) return null;
  const m = foldMap(text);
  const i = m.text.indexOf(q);
  if (i < 0) return null;
  let end = m.to[i + q.length - 1];
  const t = String(text);
  while (end < t.length && MARK.test(t[end])) end++;     // keep combining marks that follow the last letter
  return [m.from[i], end];
}
export const matchesFolded = (text, query) => { const q = fold(query).trim(); return !q || fold(text).includes(q); };
