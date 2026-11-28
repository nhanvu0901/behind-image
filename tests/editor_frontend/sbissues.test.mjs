import test from 'node:test';
import assert from 'node:assert/strict';
import { issueText, SAYTWICE_CODES, FIXDRAFT_CODES, CATALOGUE_CODES, PANELBOX_CODES, POINTFIX_CODES, BOXCAM_CODES, NAMEFIRST_CODES, IDFIX_CODES, SUBJDRAFT_CODES, PICTIME_CODES, SUBJVIS_CODES, REVIEWFIX_CODES, APIKEY_CODES, STALECHAP_CODES } from '../../bti/editor/static/js/errmsg.js';
import { storyboardIssueText, whereOf, KNOWN_CODES, paramReason } from '../../bti/editor/static/js/sbissues.js';

const VI = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;
const ENGLISH = /\b(must|is not|are not|does not|not defined|required|should|differs|folder name|unknown|needs|could not)\b/i;

// every message the storyboard checks produce today (bti/engine/storyboard.py, registry.py), one example each
const SAMPLES = [
  ['project', "project 'arnolfini' differs from the folder name 'arnolfini_edit'"],
  ['canvas', 'renderers are tuned for 1920x1080; the engine always renders 1080p'],
  ['schema', "schema must be 'bti.storyboard/1'"],
  ['canvas', 'canvas must be an object like {"w": 1920, "h": 1080}'],
  ['canvas.w', 'w must be a positive number'],
  ['canvas.fps', 'fps must be a number from 1 to 60'],
  ['title', 'title must be a string'],
  ['approvals', 'approvals must be an object'],
  ['audio', "audio file 'a.m4a' does not exist"],
  ['audio', 'audio must be a file path inside the project'],
  ['assets', 'assets must be an object'],
  ['assets.mirror', 'asset must be an object'],
  ['assets.mirror.kind', 'kind must be image, video or mask'],
  ['assets.mirror.file', 'file is required'],
  ['assets.mirror.file', "file 'x.jpg' must be a path inside the project"],
  ['assets.mirror.file', "file 'x.jpg' does not exist"],
  ['assets.mirror.credit', 'credit must be an object'],
  ['assets.mirror.width', 'width must be a positive number'],
  ['assets.mirror.regions', 'regions must be an object'],
  ['assets.mirror.regions.face', 'region needs numeric x and y'],
  ['shots[0].slots', 'slots must be an object'],
  ['shots[0].slots.image', "unknown slot 'pic' for CAM-01 (allowed: image)"],
  ['shots[0].slots.image.asset', "asset 'zz' is not defined"],
  ['shots[0].slots.image.asset', "slot 'image' takes image or video but asset 'a' is a mask"],
  ['shots[0].locked', 'locked must be true or false'],
  ['shots[0].source', "unknown source 'robot' (expected import, agent, human)"],
  ['shots[0].intent', "unknown intent 'dance'"],
  ['shots[0].params.at', "region 'face' is not defined on asset 'mirror'"],
  ['shots[0].params.at', "region 'face' needs an image on the shot to take it from"],
  ['end', 'end anchor is required'],
  ['end', 'end is not after the last shot start'],
  ['shots', 'a storyboard needs at least one shot'],
  ['shots[1].start', 'start anchor is required (an object like {"t": 12.5})'],
  ['shots[1].start', 'start must be >= 0 s (got -1.000 s)'],
  ['shots[0].start', 'the first shot starts at 2.00 s: the beginning of the timeline is not covered'],
  ['shots[1].id', "duplicate shot id 's0001'"],
  ['shots[1]', 'shot is shorter than 0.5 s (0.200 s)'],
  ['shots[1].start', 'shots must be in time order (starts before the previous shot)'],
  ['shots[1].technique', "unknown technique 'ZZZ-99'"],
  ['shots[1].technique', 'OVL-01 is a overlay technique; a shot needs kind base or card'],
  ['shots[1].technique', 'CAM-09 is not available in the engine yet'],
  ['shots[1].params.camera[1].at', 'camera keys must be in strictly increasing time order'],
  ['shots[1].params.camera[1].ease', "unknown ease 'bouncy'"],
  ['shots[1].transition_in.dur', 'transition is longer than the shot'],
  ['shots[0].transition_in', 'the first shot has nothing to transition from'],
  ['shots[1].overlays[0].start', 'overlay starts outside its shot (3.00 s; shot spans 4.00-9.00 s)'],
  ['shots[1].overlays[0]', 'overlay ends outside its shot (12.00 s > 9.00 s)'],
  ['shots[1].overlays[0]', 'overlay ends before it starts'],
  ['shots[1].overlays[0].params', 'neither `at` nor `screen` is set: the label has no position and is not drawn'],
  ['shots[1].params', "unknown parameter 'zzz' for CAM-01 (allowed: camera, shadow)"],
  ['shots[1].slots.image', "incomplete: required slot 'image' of CAM-01 is not set"],
  ['shots[1].params.text', "incomplete: required parameter 'text' is not set"],
  ['shots[1].params.zoom', 'zoom: must be a number'],
  ['shots[1].params.zoom', 'zoom: must be >= 0.5'],
  ['shots[1].params.zoom', 'zoom: must be <= 4'],
  ['shots[1].params.shape', 'shape: must be one of rect, circle'],
  ['shots[1].params.shadow', 'shadow: must be true or false'],
  ['shots[1].params.tint', 'tint: must be a #rrggbb colour'],
  ['shots[1].params.at', 'at: must be a region name or [x, y]'],
  ['shots[1].params.pts', 'pts: needs exactly 4 items (got 3)'],
  ['shots[1].params.pts', 'pts: item 2: must be a region name or [x, y]'],
  ['shots[1].params.box', 'box: must be [x0, y0, x1, y1]'],
  ['shots[1].params.camera', 'camera: camera key 0 is missing \'zoom\''],
  ['shots[1].params.tiles', 'tiles: Số cột x số hàng, ví dụ 4x2'],
];

test('every message of the storyboard checks reads as Vietnamese, with no English left', () => {
  for (const [path, message] of SAMPLES) {
    const t = issueText({ level: 'error', path, message });
    assert.ok(!t.generic, `no template for: ${message}`);
    assert.match(t.text, VI, message);
    assert.doesNotMatch(t.text, ENGLISH, `${message} -> ${t.text}`);
  }
});

test('R2U-002: the warning every copy of a project has (name differs from folder)', () => {
  const t = issueText({ level: 'warn', path: 'project', message: "project 'arnolfini' differs from the folder name 'arnolfini_edit'" });
  assert.match(t.text, /arnolfini_edit/);
  assert.doesNotMatch(t.text, /differs|folder name/);
});

test('an issue names its shot (by id when given, else by position) and its overlay', () => {
  assert.equal(whereOf({ path: 'shots[2].params.at', shot: 's0003' }).loc, 'shot s0003');
  assert.equal(whereOf({ path: 'shots[2].params.at' }).loc, 'shot thứ 3');
  assert.equal(whereOf({ path: 'shots[2].overlays[1].start' }).loc, 'lớp phủ thứ 2 của shot thứ 3');
  assert.match(issueText({ path: 'shots[2].params.at', message: 'at: must be a region name or [x, y]' }).text, /^Shot thứ 3: /);
});

test('a code the page does not know still gives a Vietnamese sentence that names the shot and the field; English only in detail', () => {
  const t = issueText({ level: 'error', code: 'brand_new_code', path: 'shots[4].dur', shot: 's0005', message: 'quantum flux is misaligned' });
  assert.equal(t.generic, true);
  assert.match(t.text, /s0005/);
  assert.match(t.text, /thời lượng/);
  assert.doesNotMatch(t.text, /quantum|misaligned/);
  assert.equal(t.detail, 'quantum flux is misaligned');
});

test('a known code is translated by the code, whatever the English says', () => {
  const t = storyboardIssueText({ level: 'error', code: 'undrawable', path: 'shots[1]', shot: 's0002', message: 'completely different words' });
  assert.match(t.text, /s0002/);
  assert.ok(!t.generic);
});

test('script issues are not taken over by the storyboard catalogue', () => {
  assert.match(issueText({ code: 'no_thesis', message: 'x' }).text, /thesis/);
  assert.match(issueText({ code: 'empty_beat', beat: 'b0001', chapter: 'c01', message: 'Beat b0001 is empty' }).text, /Dòng b0001/);
});

test('param reasons use the owner\'s words for enum values', () => {
  assert.match(paramReason('treatment_1', 'must be one of none, sepia'), /Không, Nâu cũ/);
  assert.match(paramReason('tiles', 'Số cột x số hàng, ví dụ 4x2'), /^Số cột/);
});

test('the table has a code for every kind of message', () => {
  assert.ok(KNOWN_CODES.length >= 60);
});

// ---- every code of the engine has a Vietnamese template (R2U-002)
import { execFileSync } from 'node:child_process';
import { TEMPLATE_CODES } from '../../bti/editor/static/js/sbissues.js';
import fs from 'node:fs';
const PY = new URL('../../.venv/bin/python', import.meta.url).pathname;
const engineCodes = () => JSON.parse(execFileSync(PY, ['-c', 'import json; from bti.engine.storyboard import ISSUE_CODES; print(json.dumps(sorted(ISSUE_CODES)))'], { cwd: new URL('../..', import.meta.url).pathname, encoding: 'utf8' }));

test('every code in bti.engine.storyboard.ISSUE_CODES has a Vietnamese template (and no template is for a code that does not exist)', { skip: !fs.existsSync(PY) && 'no .venv/bin/python' }, () => {
  const codes = engineCodes();
  assert.ok(codes.length >= 90, 'ISSUE_CODES looks empty');
  const missing = codes.filter((c) => !TEMPLATE_CODES.includes(c) && !SAYTWICE_CODES.includes(c) && !APIKEY_CODES.includes(c) && !FIXDRAFT_CODES.includes(c) && !CATALOGUE_CODES.includes(c) && !PANELBOX_CODES.includes(c) && !POINTFIX_CODES.includes(c) && !BOXCAM_CODES.includes(c) && !NAMEFIRST_CODES.includes(c) && !IDFIX_CODES.includes(c) && !SUBJDRAFT_CODES.includes(c) && !PICTIME_CODES.includes(c) && !SUBJVIS_CODES.includes(c) && !REVIEWFIX_CODES.includes(c) && !STALECHAP_CODES.includes(c));         // fixdraft, catalogue, panelbox, pointfix, boxcam, idfix, subjdraft: their sentences live in errmsg.js
  assert.deepEqual(missing, [], 'codes without a Vietnamese template: ' + missing.join(', '));
  const extra = TEMPLATE_CODES.filter((c) => !codes.includes(c));
  assert.deepEqual(extra, [], 'templates for codes the engine does not have: ' + extra.join(', '));
  for (const code of codes) {
    for (const args of [undefined, {}, { param: 'zoom', technique: 'CAM-01', index: 1, min: 1, max: 4, got: 7, field: 'w', values: ['a', 'b'], takes: ['image'], got_kind: 'mask' }]) {
      const t = issueText({ level: 'error', code, args, path: 'shots[0].params.zoom', message: 'English text' });
      assert.ok(!t.generic, `${code}: fell back to the general sentence`);
      assert.match(t.text, VI, code);
      assert.doesNotMatch(t.text, /English|undefined|null|NaN|\[object/, `${code}: ${t.text}`);
    }
  }
});

test('templates use args: param, technique, limits, region', () => {
  const t = (code, args, path = 'shots[2].params.x') => issueText({ level: 'error', code, args, path, message: 'x' }).text;
  assert.match(t('param_below_min', { param: 'zoom', technique: 'CAM-01', min: 0.5 }), /"zoom".*0\.5/);
  assert.match(t('param_item_count', { param: 'to_quad', technique: 'DIA-02', min: 4, max: 4, got: 3 }), /đúng 4 mục \(hiện có 3\)/);
  assert.match(t('param_item_count', { param: 'pts', technique: 'X', min: 2, max: 8, got: 9 }), /nhiều nhất 8/);
  assert.match(t('region_undefined', { region: 'face', asset: 'mirror', param: 'at' }), /"face".*"mirror"/);
  assert.match(t('param_bad_form', { param: 'tiles', technique: 'LAY-08', hint: 'Số cột x số hàng, ví dụ 4x2', pattern: 'x' }), /Số cột x số hàng/);
  assert.match(t('point_numeric_only', { param: 'from_quad', technique: 'DIA-02', index: 0 }), /chỉ nhập được hai số/);
  assert.match(t('unknown_technique', { technique: 'ZZZ-99' }), /ZZZ-99/);
});

// worker reviewfix
test("incomplete review has a Vietnamese count", () => {
  const t = issueText({code: "review_incomplete", args: {count: 3}});
  assert.equal(t.text, "Chưa xem được 3 cảnh.");
  assert.ok(!t.generic);
});
