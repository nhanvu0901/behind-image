import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { INTENT, EASE, VALUE, SOURCE, TEXT_SOURCE, intentLabel, valueLabel, sourceLabel, textSourceLabel } from '../../bti/editor/static/js/labels.js';

const REG = JSON.parse(fs.readFileSync(new URL('../../style/gae/techniques.json', import.meta.url), 'utf8')).techniques;
const VI = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;
const readable = (t) => VI.test(t) || /^[A-ZĐ][a-zA-Zàáảãạăâêôơưđ ]+$/.test(t);

test('R2U-004: every intent of the registry has a Vietnamese label that is not the raw id', () => {
  const all = [...new Set(REG.flatMap((t) => t.intents))];
  assert.ok(all.length >= 10);
  for (const i of all) { assert.ok(INTENT[i], `intent ${i} has no label`); assert.notEqual(intentLabel(i), i); assert.doesNotMatch(intentLabel(i), /_/); }
});

test('every enum value of every param of the registry has a label (and none shows an underscore id)', () => {
  let n = 0;
  for (const t of REG) for (const p of t.params) {
    if (p.type !== 'enum') continue;
    for (const v of p.values || []) {
      n++;
      assert.ok(VALUE[v], `${t.id}.${p.name}: value "${v}" has no label`);
      const l = valueLabel(v, p.name);
      assert.notEqual(l, v, `${t.id}.${p.name}=${v}`);
      assert.doesNotMatch(l, /_/, `${t.id}.${p.name}=${v} -> ${l}`);
      assert.ok(readable(l), `${t.id}.${p.name}=${v} -> ${l}`);
    }
  }
  assert.ok(n > 100);
});

test('every ease name has a label; unknown words come back as they are', () => {
  for (const e of ['linear', 'in_quad', 'out_quad', 'in_cubic', 'out_cubic', 'inout_sine', 'inout_cubic']) assert.ok(EASE[e] && valueLabel(e) !== e);
  assert.equal(valueLabel('something_new'), 'something_new');
  assert.equal(valueLabel(null), '');
});

test('where one word means two things, the param decides', () => {
  assert.notEqual(valueLabel('frame', 'connector_mode'), valueLabel('frame', 'space'));
});

test('source and text-source labels', () => {
  for (const k of ['import', 'agent', 'human']) assert.ok(SOURCE[k]);
  assert.equal(sourceLabel(undefined), SOURCE.import);
  for (const k of ['clean', 'layer', 'mixed']) assert.ok(TEXT_SOURCE[k]);
  assert.equal(textSourceLabel('clean'), TEXT_SOURCE.clean);
});
