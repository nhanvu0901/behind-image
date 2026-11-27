// Pure logic and Vietnamese label tests for Step 4 ("Kịch bản hình") and Step 5 ("Dựng hình") on the visual path.
import test from 'node:test';
import assert from 'node:assert/strict';
import { VISUAL_PAGE_LABELS } from '../../bti/editor/static/js/labels.js';
import { looksRaw } from '../../bti/editor/static/js/shotsentence.js';
import {
  isVisualProject,
  findStateAction,
  visualEditAction,
  needsHint,
  regionDisplayName,
  momentWordsText,
  momentWhy,
  resolveShow,
  describeIntents,
  buildVisualScriptView,
} from '../../bti/editor/static/js/visualpage_logic.js';
import {
  isVisualStoryboard,
  momentWordsMap,
  composeNoteKind,
  translateComposeNoteText,
  groupComposeNotes,
  extractReviewFindings,
} from '../../bti/editor/static/js/visualedit_logic.js';

const VI = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;

function collectStrings(obj, path = 'VISUAL_PAGE_LABELS', out = []) {
  if (typeof obj === 'string') out.push([path, obj]);
  else if (typeof obj === 'function') {
    for (const args of [[1], [3], ['Gương', 4], ['Gương và Mặt'], ['Tên', 'chi tiết phụ', 'từ khóa'], ['Chi tiết', 'phụ'], ['lý do']]) {
      try { const v = obj(...args); if (typeof v === 'string') out.push([path + '()', v]); } catch { /* ignore */ }
    }
  } else if (obj && typeof obj === 'object') {
    for (const [k, v] of Object.entries(obj)) collectStrings(v, `${path}.${k}`, out);
  }
  return out;
}

test('every label in VISUAL_PAGE_LABELS is Vietnamese and free of raw identifiers', () => {
  const all = collectStrings(VISUAL_PAGE_LABELS);
  assert.ok(all.length >= 60);
  for (const [path, str] of all) {
    if (!/\p{L}/u.test(str)) continue;
    assert.ok(VI.test(str), `${path}: "${str}" has no Vietnamese character`);
    assert.ok(!looksRaw(str), `${path}: "${str}" looks raw`);
  }
});

test('visual vs legacy detection preserves legacy pages when visual script is absent', () => {
  assert.equal(isVisualProject({ visual: null, state: { pipeline: 'legacy' }, pipeline: {} }), false);
  assert.equal(isVisualProject({ visual: { moments: [] } }), true);
  assert.equal(isVisualProject({ state: { pipeline: 'visual' } }), true);
  assert.equal(isVisualStoryboard({ storyboard: { shots: [{ id: 's1', technique: 'CAM-01' }] }, visual: null }), false);
  assert.equal(isVisualStoryboard({ storyboard: { made_from: { visual: 'abc' }, shots: [] } }), true);
  assert.equal(isVisualStoryboard({ storyboard: { shots: [{ id: 's_m0001', moment: 'm0001' }] } }), true);
});

test('visualEditAction reads state.next_actions without hard-coding readiness', () => {
  assert.equal(visualEditAction(null), null);
  assert.equal(visualEditAction({ next_actions: [{ id: 'picks.approve', ready: true }] }), null);
  const act = visualEditAction({
    next_actions: [
      { id: 'visual.edit', method: 'POST', path: '/api/projects/p/visual/edit', ready: false, needs: ['no_running_job'] },
    ],
  });
  assert.equal(act.ready, false);
  assert.match(needsHint(act.needs), /Đang có một việc khác/);
  assert.equal(findStateAction({ next_actions: [{ id: 'visual.plan', ready: true }] }, 'visual.plan').ready, true);
});

test('buildVisualScriptView resolves all SHOW types, tried queries, intents, counts and top regions', () => {
  const words = [
    { w: 'In', s: 0.0, e: 0.3 },
    { w: '1434', s: 0.3, e: 0.8 },
    { w: 'Giovanni', s: 0.8, e: 1.4 },
    { w: 'left', s: 1.4, e: 1.8 },
    { w: 'Lucca', s: 1.8, e: 2.3 },
    { w: 'for', s: 2.3, e: 2.6 },
    { w: 'Bruges', s: 2.6, e: 3.1 },
    { w: 'and', s: 3.1, e: 3.3 },
    { w: 'dyers', s: 3.3, e: 3.9 },
    { w: 'worked', s: 3.9, e: 4.5 },
  ];
  const picks = {
    main_asset: 'main',
    assets: {
      main: {
        file: 'media/main.jpg',
        width: 2000,
        height: 2600,
        regions: {
          MAN_HEAD: { x: 800, y: 600, rx: 120, ry: 150, label: 'Khuôn mặt người đàn ông' },
          RAW_ONLY: { x: 500, y: 500, rx: 50, ry: 50, label: 'RAW_ONLY' },
          MIRROR: { x: 1000, y: 1200, rx: 90, ry: 90, label: 'Chiếc gương lồi' },
        },
      },
      pic_lucca: { file: 'media/lucca.jpg', title: 'Lucca', caption: 'Thành phố Lucca thời Trung cổ' },
      pic_eyck: { file: 'media/eyck.jpg', title: 'Van Eyck', caption: 'Chân dung Jan van Eyck' },
    },
  };
  const narration = {
    chapters: [
      { id: 'c01', title: 'Mở đầu', beats: [{ id: 'b1', text: 'In 1434 Giovanni left Lucca for Bruges and dyers worked.' }] },
    ],
  };
  const visual = {
    cast: [
      { id: 'giovanni', kind: 'person', name: 'Giovanni Arnolfini', strip: true, sub: 'merchant from Lucca', shown_by: [{ region: 'MAN_HEAD' }] },
      { id: 'dyers', kind: 'work', name: 'thợ nhuộm', strip: false, sub: '', shown_by: [] },
    ],
    wanted: [
      { id: 'w_missing', subject: 'dyers', kind: 'work', search: 'medieval dyers', status: 'none', picture: null, tried: ['medieval dyers', '15th century dyers guild'] },
    ],
    moments: [
      {
        id: 'm1', line: 'b1', w0: 0, w1: 3, about: 'giovanni',
        show: { region: 'MAN_HEAD' }, move: 'push',
        say: [{ intro: 'giovanni', word: 2 }, { point: [{ region: 'MIRROR', word: 1 }] }],
        why: 'Giới thiệu Giovanni bằng khuôn mặt.',
      },
      {
        id: 'm2', line: 'b1', w0: 3, w1: 5, about: null,
        show: { pair: [{ picture: 'pic_lucca' }, { picture: 'pic_eyck' }] }, move: 'hold',
        say: [], why: 'Đặt hai hình cạnh nhau.',
      },
      {
        id: 'm3', line: 'b1', w0: 5, w1: 7, about: null,
        show: { map: { places: ['Lucca, Italy', 'Bruges, Belgium'] }, else: { region: 'RAW_ONLY' } }, move: 'hold',
        say: [], why: 'Chỉ tuyến đường đi.',
      },
      {
        id: 'm4', line: 'b1', w0: 7, w1: 10, about: 'dyers', about_not_shown: 'Chưa có hình dùng được.',
        show: { want: 'w_missing', else: { region: 'MAN_HEAD' } }, move: 'hold',
        say: [], why: 'Dùng tạm cận cảnh khi chưa tìm thấy hình.',
      },
    ],
  };

  assert.equal(regionDisplayName(picks.assets.main, 'RAW_ONLY'), 'một chi tiết của tranh');
  assert.equal(regionDisplayName(picks.assets.main, 'MAN_HEAD'), 'Khuôn mặt người đàn ông');
  assert.equal(momentWordsText(visual.moments[0], words).text, 'In 1434 Giovanni');
  assert.equal(momentWhy(visual.moments[0]), 'Giới thiệu Giovanni bằng khuôn mặt.');

  const vm = buildVisualScriptView({ visual, picks, narration, words });
  assert.equal(vm.counts.moments, 4);
  assert.equal(vm.counts.borrowed, 2);
  assert.equal(vm.counts.notFound, 1);
  assert.equal(vm.counts.topRegions[0].region, 'MAN_HEAD');
  assert.equal(vm.counts.topRegions[0].count, 2);

  const moments = vm.chapters[0].lines[0].moments;
  assert.equal(moments[0].show.kind, 'region');
  assert.equal(moments[0].intents.intros[0].where, 'Giovanni');
  assert.equal(moments[0].intents.points[0].name, 'Chiếc gương lồi');
  assert.equal(moments[1].show.kind, 'pair');
  assert.equal(moments[1].show.items[0].caption, 'Thành phố Lucca thời Trung cổ');
  assert.equal(moments[2].show.kind, 'map');
  assert.equal(moments[2].show.placesText, 'Lucca, Italy → Bruges, Belgium');
  assert.equal(moments[3].show.kind, 'want_none');
  assert.deepEqual(moments[3].show.tried, ['medieval dyers', '15th century dyers guild']);
  assert.equal(moments[3].show.fallback.region, 'MAN_HEAD');
  assert.ok(describeIntents(visual.moments[0], { castById: new Map(), mainAsset: picks.assets.main, words }).points.length === 1);
  assert.equal(resolveShow({ whole: true }, { assets: picks.assets, mainKey: 'main' }).kind, 'whole');
});

test('Step 5 compose notes translate to Vietnamese, prefix line number, and group by kind', () => {
  assert.equal(composeNoteKind('C1'), 'timing');
  assert.equal(composeNoteKind('C6'), 'mark');
  assert.equal(translateComposeNoteText('extended backward toward sentence start'), 'hình mượn được kéo dài về đầu câu');

  const narration = {
    chapters: [{
      id: 'c01',
      beats: Array.from({ length: 12 }, (_, i) => ({ id: `b${i + 1}`, text: `Line ${i + 1}` })),
    }],
  };
  const visual = {
    moments: [
      { id: 'm12', line: 'b12', w0: 0, w1: 2 },
      { id: 'm05', line: 'b5', w0: 2, w1: 4 },
    ],
  };
  const storyboard = {
    shots: [
      { id: 's_m05', moment: 'm05', _t0: 1.0, _t1: 4.0 },
      { id: 's_m12', moment: 'm12', _t0: 4.0, _t1: 8.0 },
      { id: 'program_c01_card', intent: 'structure', _t0: 0.0, _t1: 1.0 },
    ],
    compose_notes: [
      { moment: 'm12', rule: 'C1', what: 'extended backward toward sentence start' },
      { moment: 'm05', rule: 'C6', what: 'mark DOG omitted: person, large, outside frame, or too late' },
    ],
  };
  const words = [
    { w: 'alpha', s: 0.0, e: 0.5 },
    { w: 'beta', s: 0.5, e: 1.0 },
    { w: 'gamma', s: 1.0, e: 1.5 },
    { w: 'delta', s: 1.5, e: 2.0 },
  ];

  const mw = momentWordsMap({ storyboard, visual, words });
  assert.equal(mw.get('s_m12'), 'alpha beta');
  assert.equal(mw.get('s_m05'), 'gamma delta');
  assert.equal(mw.get('program_c01_card'), '');

  const groups = groupComposeNotes(storyboard.compose_notes, { visual, storyboard, narration });
  assert.equal(groups.length, 2);
  assert.equal(groups[0].kind, 'timing');
  assert.equal(groups[0].items[0].sentence, 'câu 12: hình mượn được kéo dài về đầu câu');
  assert.equal(groups[0].items[0].shotId, 's_m12');
  assert.equal(groups[1].kind, 'mark');
  assert.match(groups[1].items[0].sentence, /^câu 5: /);
});

test('extractReviewFindings deduplicates and formats Vietnamese sentences', () => {
  const shots = [{ id: 's_m01' }, { id: 's_m02' }];
  const findings = extractReviewFindings({
    issues: [{ level: 'warn', code: 'review_picture_mismatch', shot: 's_m02', message: 'English' }],
    reviewReport: { warnings: [{ level: 'warn', code: 'review_picture_mismatch', shot: 's_m02', message: 'English' }] },
    shots,
  });
  assert.equal(findings.length, 1);
  assert.equal(findings[0].shotId, 's_m02');
  assert.equal(findings[0].shotNumber, 2);
  assert.ok(VI.test(findings[0].text));
  assert.doesNotMatch(findings[0].text, /English/);
});
