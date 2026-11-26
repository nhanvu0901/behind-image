import test from 'node:test';
import assert from 'node:assert/strict';
import { musicRows } from '../../bti/editor/static/js/musiclogic.js';

test('music cues show time, piece, composer and a Vietnamese role in order', () => {
  const rows = musicRows([{ start: 70, end: 90, title: 'Second', composer: 'B', role: 'ending', audio_url: '/b' },
                          { start: 3, end: 12, title: 'First', composer: 'A', role: 'bed', audio_url: '/a' }]);
  assert.deepEqual(rows.map(row => row.title), ['First', 'Second']);
  assert.equal(rows[0].time, '00:03–00:12');
  assert.equal(rows[0].composer, 'A');
  assert.equal(rows[0].role, 'Nhạc nền');
  assert.equal(rows[1].role, 'Kết');
  assert.equal(rows[0].url, '/a');
});
