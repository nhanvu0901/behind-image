// The rule of the whole app: nothing the owner reads comes straight from the server or from an exception.
// Errors go through describeError / errorToast / errorInto, issues through issueText, enum values through labels.js.
// This test reads the view files and fails when one of them shows `.message`, a status number or a raw issue text.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const JS = new URL('../../bti/editor/static/js/', import.meta.url).pathname;
const files = [];
const walk = (d) => { for (const f of fs.readdirSync(d, { withFileTypes: true })) { const p = path.join(d, f.name); if (f.isDirectory()) walk(p); else if (f.name.endsWith('.js')) files.push(p); } };
walk(JS);
// these modules ARE the translators, or are not shown to the owner (the in-browser fixtures)
const EXEMPT = new Set(['errmsg.js', 'sbissues.js', 'errors.js', 'mockapi.js', 'api.js']);
const code = (src) => src.split('\n').map((l) => l.replace(/^\s*\/\/.*$/, '').replace(/\s\/\/ .*$/, ''));

// [pattern, why]. A line that matches fails the test unless it also matches ALLOW.
const FORBIDDEN = [
  [/\be(?:rr)?\.message\b/, 'an exception message is shown or built into text: use describeError / errorToast / errorInto'],
  [/\(\s*e(?:rr)?\.status\s*\|\|/, 'a status number is shown: use describeError'],
  [/['"`]\s*\+\s*e(?:rr)?\.status\b|\$\{\s*e(?:rr)?\.status\s*\}/, 'a status number is built into text'],
  [/\b(?:i|x|issue|is|it)\.message\b/, 'a raw validation message is shown: use issueText'],
  [/\bj\.error\b|job\.error\b/, 'a raw job error is shown: use jobErrorText / jobFailText'],
  [/e\.body\??\.detail\??\.(?:message|reason)|e\.body\??\.(?:reason|detail)\b.*text/, 'a raw server body text is shown'],
];
const ALLOW = [/new RegExp|\.test\(|\.exec\(|\.match\(|console\.|throw new|\/\*\*|^\s*\*/];

test('no view or helper shows an exception message, a status number or a raw validation text', () => {
  const bad = [];
  for (const f of files) {
    const name = path.basename(f);
    if (EXEMPT.has(name)) continue;
    code(fs.readFileSync(f, 'utf8')).forEach((line, i) => {
      for (const [re, why] of FORBIDDEN) if (re.test(line) && !ALLOW.some((a) => a.test(line))) bad.push(`${path.relative(JS, f)}:${i + 1}: ${why}\n    ${line.trim().slice(0, 150)}`);
    });
  }
  assert.deepEqual(bad, [], '\n' + bad.join('\n'));
});

test('the storyboard modules import errmsg.js or util.js error helpers when they catch an error', () => {
  for (const n of ['views/storyboard.js', 'proposals.js', 'preview.js', 'media.js']) {
    const src = fs.readFileSync(path.join(JS, n), 'utf8');
    assert.match(src, /describeError|errorToast|errorInto|describeHttp/, n);
  }
});
