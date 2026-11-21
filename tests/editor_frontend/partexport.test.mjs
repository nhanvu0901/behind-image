// Incremental ~60 s export part labels and stale-approval hints: Vietnamese, plain, and free of raw parameter or id tokens.
import test from 'node:test';
import assert from 'node:assert/strict';
import { EXPORT_LABELS, OUTPUT_LABELS, PARTEXPORT_LABELS } from '../../bti/editor/static/js/labels.js';
import { STAGE_CODES } from '../../bti/editor/static/js/errmsg.js';
import { looksRaw } from '../../bti/editor/static/js/shotsentence.js';

const VI = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;

test('partexport labels are Vietnamese and contain no raw identifiers', () => {
  const samples = [
    PARTEXPORT_LABELS.reusedNote,
    PARTEXPORT_LABELS.renderedNote,
    PARTEXPORT_LABELS.partsPlan(0, 13, 13),
    PARTEXPORT_LABELS.partsPlan(13, 0, 13),
    PARTEXPORT_LABELS.partsPlan(1, 12, 13),
    PARTEXPORT_LABELS.partsSummary(0, 13),
    PARTEXPORT_LABELS.partsSummary(13, 0),
    PARTEXPORT_LABELS.partsSummary(1, 12),
    OUTPUT_LABELS.hint,
    STAGE_CODES.export.approval_stale,
  ];
  for (const s of samples) {
    assert.equal(typeof s, 'string');
    assert.ok(VI.test(s), `"${s}" has no Vietnamese letter`);
    assert.ok(!looksRaw(s), `"${s}" looks raw`);
  }
  assert.equal(EXPORT_LABELS.reusedNote, PARTEXPORT_LABELS.reusedNote);
  assert.equal(EXPORT_LABELS.renderedNote, PARTEXPORT_LABELS.renderedNote);
  assert.equal(EXPORT_LABELS.partsPlan, PARTEXPORT_LABELS.partsPlan);
  assert.equal(EXPORT_LABELS.partsSummary, PARTEXPORT_LABELS.partsSummary);
  assert.match(OUTPUT_LABELS.hint, /không bị xóa/);
  assert.match(OUTPUT_LABELS.hint, /đoạn dựng của lần xuất này/);
  assert.match(STAGE_CODES.export.approval_stale, /đổi|duyệt/);
});
