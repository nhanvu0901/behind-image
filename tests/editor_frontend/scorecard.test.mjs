// Quality scorecard frontend helpers and labels: Vietnamese, accurate formatting, and free of raw ids.
import test from 'node:test';
import assert from 'node:assert/strict';
import { SCORECARD_LABELS } from '../../bti/editor/static/js/labels.js';
import { STAGE_CODES, describeHttp } from '../../bti/editor/static/js/errmsg.js';
import {
  formatClock,
  formatMetricValue,
  formatMetricTarget,
  formatMetricDetail,
  scorecardRows,
  scorecardSummaryText,
} from '../../bti/editor/static/js/scorecardlogic.js';
import { looksRaw } from '../../bti/editor/static/js/shotsentence.js';

const VI = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;

test('scorecard labels and error codes are Vietnamese and contain no raw tokens', () => {
  const strings = [
    SCORECARD_LABELS.title,
    SCORECARD_LABELS.make,
    SCORECARD_LABELS.remake,
    SCORECARD_LABELS.making,
    SCORECARD_LABELS.empty,
    SCORECARD_LABELS.notReady,
    SCORECARD_LABELS.stale,
    SCORECARD_LABELS.doneToast,
    SCORECARD_LABELS.sheetsTitle,
    SCORECARD_LABELS.sheetsHint,
    SCORECARD_LABELS.sheetTile(1, 1, 20),
    SCORECARD_LABELS.status.ok,
    SCORECARD_LABELS.status.warn,
    SCORECARD_LABELS.status.na,
    ...Object.values(SCORECARD_LABELS.metric),
    SCORECARD_LABELS.summary(8, 10, 2),
    STAGE_CODES.scorecard.scorecard_not_ready,
    STAGE_CODES.scorecard.scorecard_failed,
    STAGE_CODES.scorecard.sheet_not_found,
    describeHttp(409, { code: 'scorecard_not_ready' }).text,
    describeHttp(500, { code: 'scorecard_failed' }).text,
  ];
  for (const s of strings) {
    assert.equal(typeof s, 'string');
    assert.ok(VI.test(s), `"${s}" has no Vietnamese character`);
    assert.ok(!looksRaw(s), `"${s}" looks like a raw identifier`);
  }
});

test('scorecard formatting helpers produce expected Vietnamese rows and targets', () => {
  assert.equal(formatClock(0), '0:00');
  assert.equal(formatClock(125), '2:05');
  assert.equal(formatClock(3665), '1:01:05');

  const sample = {
    summary: { passed: 9, failed: 3, unmeasured: 0 },
    metrics: [
      {
        key: 'small_painting_share',
        value: 0.108,
        seconds: 73.0,
        shot_count: 14,
        target: 0.06,
        ok: false,
        items: [{ shot: 's0010', time: 12.0, region: 'MAIN' }],
      },
      {
        key: 'marks_per_minute',
        value: 4.5,
        total: 45,
        rings: 25,
        spotlights: 20,
        target: 3.0,
        ok: false,
        items: [],
      },
      {
        key: 'biggest_mark',
        value: 0.42,
        over_30_count: 2,
        target: 0.30,
        ok: false,
        items: [{ time: 18, region: 'WOMAN_FIGURE' }],
      },
      {
        key: 'name_strips',
        value: { count: 4, sub_repeats: 1, on_thing: 1 },
        target: { sub_repeats: 0, on_thing: 0 },
        ok: false,
        items: [{ time: 90, text: 'Áo choàng', on_thing: true }],
      },
      {
        key: 'borrowed_pictures',
        value: { count: 5, seconds: 20.4, share: 0.03, longest_gap_s: 150.0, under_3s_count: 1 },
        target: { min_s: 3.0, max_gap_s: 120.0 },
        ok: false,
        items: [{ time: 200, shot: 's0040' }],
      },
      {
        key: 'repeated_regions',
        value: 4,
        target: 4,
        ok: true,
        items: [{ region: 'CHANDELIER', label: 'Đèn chùm', count: 4 }],
      },
      {
        key: 'loudness',
        value: null,
        target: { lufs: -15.0, tolerance: 1.5 },
        ok: null,
        items: [],
      },
      {
        key: 'pause_vs_speech',
        value: { diff_db: 12.5 },
        target: { min_db: 6.0, max_db: 22.0 },
        ok: true,
        items: [],
      },
    ],
  };

  const rows = scorecardRows(sample);
  assert.equal(rows.length, 8);
  assert.equal(rows[0].status, 'warn');
  assert.match(rows[0].valueText, /10,8%/);
  assert.match(rows[0].detail, /0:12/);
  assert.match(rows[2].valueText, /2 dấu > 30%/);
  assert.match(rows[3].detail, /1:30 Áo choàng/);
  assert.match(rows[5].valueText, /4 lần \(Đèn chùm\)/);
  assert.equal(rows[5].status, 'ok');
  assert.equal(rows[6].valueText, 'Chưa xuất video');
  assert.equal(rows[6].status, 'na');
  assert.match(rows[7].valueText, /12,5 dB/);
  assert.ok(formatMetricTarget(sample.metrics[6]).includes('-15,0 ± 1,5 LUFS'));
  assert.ok(VI.test(scorecardSummaryText(sample)));
});
