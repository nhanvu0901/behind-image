import test from 'node:test';
import assert from 'node:assert/strict';
import { dropdownOptions, NOT_IN_LIST, UNSET, intentLabel } from '../../bti/editor/static/js/labels.js';

const INTENTS = ['establish', 'explore'];
test('a stored value in the list is selected as it is', () => {
  const r = dropdownOptions(INTENTS, 'explore', intentLabel);
  assert.equal(r.selected, 'explore');
  assert.deepEqual(r.options.map((o) => o.value), INTENTS);
  assert.ok(r.options.every((o) => o.state === 'ok'));
});
test('a value the list does not know gets its own marked entry, selected', () => {
  const r = dropdownOptions(INTENTS, 'dance', intentLabel);
  assert.equal(r.selected, 'dance');
  assert.equal(r.options[0].value, 'dance');
  assert.equal(r.options[0].state, 'foreign');
  assert.ok(r.options[0].text.includes(NOT_IN_LIST));
  assert.equal(r.options.length, 3);
});
test('an empty value shows "chưa chọn" and is not the first real choice', () => {
  for (const v of [null, undefined, '']) {
    const r = dropdownOptions(INTENTS, v, intentLabel);
    assert.equal(r.selected, '');
    assert.equal(r.options[0].text, UNSET);
    assert.equal(r.options[0].disabled, true);
  }
});
test('when "" is itself a choice, an empty value selects it and adds nothing', () => {
  const r = dropdownOptions(['', 'T-01'], null, (x) => x || 'Cắt thẳng');
  assert.equal(r.selected, '');
  assert.equal(r.options.length, 2);
  assert.equal(r.options[0].text, 'Cắt thẳng');
});
test('the helper never changes the list it is given', () => {
  const l = ['a']; dropdownOptions(l, 'zz'); assert.deepEqual(l, ['a']);
});
