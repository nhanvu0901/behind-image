// The JavaScript side of the parity between the page's sentence of a shot (shotsentence.js) and the Python twin that writes `shots.md` (bti/output/shotwords.py).
// Both are checked against ONE file of cases, tests/output/fixtures/shot_cases.json: real shots with the sentence this function made for them. If a phrase of labels.js
// or a rule of shotsentence.js changes, this test fails until the file is regenerated (UPDATE_GOLDEN=1 node --test tests/output/shotsentence_parity.test.mjs), and then
// tests/output/test_shotwords.py fails until bti/output/shotwords.py says the same.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { shotSentence, mainAssetKey, looksRaw } from '../../bti/editor/static/js/shotsentence.js';

const read = (p) => JSON.parse(fs.readFileSync(new URL('../../' + p, import.meta.url), 'utf8'));
const FILE = 'tests/output/fixtures/shot_cases.json';
const REG = read('style/gae/techniques.json').techniques;
const BY = Object.fromEntries(REG.map((t) => [t.id, t]));
const tech = (id) => BY[id] || null;
const SOURCES = ['arnolfini', 'arnolfini_edit', 'technique_lab', 'lab_annot', 'lab_diagrams', 'lab_layouts', 'lab_text'];
const TITLE = 'The Arnolfini Portrait';

const assetKeys = (o, out = new Set()) => {
  if (Array.isArray(o)) o.forEach((v) => assetKeys(v, out));
  else if (o && typeof o === 'object') for (const [k, v] of Object.entries(o)) { if (k === 'asset' && typeof v === 'string') out.add(v); else assetKeys(v, out); }
  return out;
};

function build() {
  const cases = [], seen = new Set();
  for (const p of SOURCES) {
    const sb = read(`projects/${p}/storyboard.json`);
    const mainKey = mainAssetKey(sb, TITLE);
    for (const shot of sb.shots) {
      const keys = [...assetKeys(shot)];
      const assets = Object.fromEntries(keys.filter((k) => sb.assets?.[k]).map((k) => [k, { title: sb.assets[k].title, kind: sb.assets[k].kind, duration: sb.assets[k].duration, regions: sb.assets[k].regions }]));
      const expected = shotSentence(shot, { tech, assets, mainKey });
      const id = `${shot.technique}|${expected}`;
      if (seen.has(id)) continue;
      seen.add(id);
      cases.push({ name: `${p}/${shot.id}`, shot, assets, mainKey, expected });
    }
  }
  // the program's own opening shot (the reserved id s0000, from the voice's first word minus 0.35 s) with the overlays the identity puts on it: the words are the
  // opening's, not the technique's ("Zoom vào cả bức tranh"); the Python twin says the same (bti/output/shotwords.py)
  for (const id of ['CAM-01', 'CAM-03']) {
    const shot = { id: 's0000', start: { t: 0 }, technique: id, slots: { image: { asset: 'MAIN' } }, params: {}, overlays: [{ id: 'o1', technique: 'ID-OPEN-01' }, { id: 'o2', technique: 'ID-LABEL-01' }] };
    const assets = { MAIN: { title: TITLE, kind: 'image' } };
    cases.push({ name: `opening/${id}`, shot, assets, mainKey: 'MAIN', expected: shotSentence(shot, { tech, assets, mainKey: 'MAIN' }) });
  }
  const techniques = {};
  for (const t of REG) {
    techniques[t.id] = {
      base: shotSentence({ technique: t.id, slots: {}, params: {}, overlays: [] }, { tech, assets: {}, mainKey: null }),
      overlay: shotSentence({ technique: 'CAM-01', slots: {}, params: {}, overlays: [{ technique: t.id }] }, { tech, assets: {}, mainKey: null }),
    };
  }
  return { note: 'made by tests/output/shotsentence_parity.test.mjs (UPDATE_GOLDEN=1) from the shots of projects/*/storyboard.json and style/gae/techniques.json', cases, techniques };
}

if (process.env.UPDATE_GOLDEN) {
  const doc = build();
  fs.writeFileSync(new URL('../../' + FILE, import.meta.url), JSON.stringify(doc) + '\n');
  console.log(`wrote ${FILE}: ${doc.cases.length} cases, ${Object.keys(doc.techniques).length} techniques`);
}

test('the shots of the cases still make the sentences the file says (the JavaScript side)', () => {
  const doc = read(FILE);
  assert.ok(doc.cases.length > 60, 'cases: ' + doc.cases.length);
  for (const c of doc.cases) assert.equal(shotSentence(c.shot, { tech, assets: c.assets, mainKey: c.mainKey }), c.expected, c.name);
});

test('every technique as a base and as an overlay still makes the sentence the file says, and none shows an id', () => {
  const doc = read(FILE);
  assert.equal(Object.keys(doc.techniques).length, REG.length);
  for (const t of REG) {
    const e = doc.techniques[t.id];
    assert.equal(shotSentence({ technique: t.id, slots: {}, params: {}, overlays: [] }, { tech, assets: {}, mainKey: null }), e.base, t.id);
    assert.equal(shotSentence({ technique: 'CAM-01', slots: {}, params: {}, overlays: [{ technique: t.id }] }, { tech, assets: {}, mainKey: null }), e.overlay, t.id + ' as an overlay');
    assert.ok(!looksRaw(e.base) && !looksRaw(e.overlay), t.id);
  }
});
