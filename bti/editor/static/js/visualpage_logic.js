// Pure helpers for Step 4 ("Kịch bản hình") and shared state-driven visual.edit availability.
// No DOM, no network. Tested in tests/editor_frontend/visualpage.test.mjs.
import { VISUAL_PAGE_LABELS as VL } from './labels.js';
import { minSec } from './editlogic.js';

const ID_LOOKING = /^[A-Z0-9_]{2,}$/;
const cleanText = (v) => (typeof v === 'string' ? v.replace(/\s+/g, ' ').trim() : '');

/** Whether the project uses the unified visual pipeline rather than legacy picks. */
export function isVisualProject({ visual = null, state = null, pipeline = null } = {}) {
  if (visual && typeof visual === 'object' && Array.isArray(visual.moments)) return true;
  if (state?.pipeline === 'visual' || pipeline?.pipeline === 'visual') return true;
  return false;
}

/** Look up an action spec from GET /api/projects/{pid}/state -> next_actions. */
export function findStateAction(state, id) {
  const list = Array.isArray(state?.next_actions) ? state.next_actions : [];
  return list.find((a) => a && a.id === id) || null;
}

/** Action descriptor for visual.edit, or null when the state answer does not offer it. */
export function visualEditAction(state) {
  return findStateAction(state, 'visual.edit');
}

/** Translate state action `needs` codes into a short Vietnamese explanation. */
export function needsHint(needs) {
  const arr = Array.isArray(needs) ? needs : [];
  if (!arr.length) return '';
  const map = VL.step4.actions.needs;
  const parts = arr.map((k) => map[k] || map.fallback);
  return [...new Set(parts)].join(' ');
}

/** Human-readable painting region name; never returns a raw ALL_CAPS key. */
export function regionDisplayName(asset, regionKey) {
  const label = cleanText(asset?.regions?.[regionKey]?.label);
  return label && !ID_LOOKING.test(label) ? label : VL.step4.show.regionAny;
}

/** Read a moment's Vietnamese rationale safely. */
export function momentWhy(entry) {
  return cleanText(entry?.why);
}

/** Slice spoken words and timestamps for a moment [w0, w1). */
export function momentWordsText(moment, words) {
  const list = Array.isArray(words) ? words : [];
  const w0 = Number.isInteger(moment?.w0) ? Math.max(0, moment.w0) : 0;
  const w1 = Number.isInteger(moment?.w1) ? Math.min(list.length, moment.w1) : w0;
  const slice = w1 > w0 ? list.slice(w0, w1) : [];
  const spoken = slice.map((w) => cleanText(w?.w)).filter(Boolean).join(' ');
  const t0 = Number.isFinite(slice[0]?.s) ? slice[0].s : null;
  const last = slice[slice.length - 1];
  const t1 = Number.isFinite(last?.e) ? last.e : Number.isFinite(last?.s) ? last.s : t0;
  const dur = t0 != null && t1 != null ? Math.max(0, t1 - t0) : null;
  return {
    text: spoken,
    t0,
    t1,
    timeText: t0 != null ? minSec(t0) : '',
    durText: dur != null ? `${dur.toFixed(1).replace('.', ',')} giây` : '',
  };
}

function singlePictureInfo(assetKey, { assets, mainKey }) {
  const a = assets?.[assetKey] || null;
  const cap = cleanText(a?.caption);
  const title = cleanText(a?.title);
  return {
    assetKey,
    asset: a,
    caption: cap || title || VL.step4.show.noCaption,
    hasCaption: Boolean(cap),
    gone: !a,
    isMain: assetKey === mainKey,
  };
}

/** Resolve any SHOW object (whole | region | picture | want | pair | map) into view data. */
export function resolveShow(show, { wantedById = new Map(), castById = new Map(), assets = {}, mainKey = null } = {}) {
  if (!show || typeof show !== 'object') {
    return { kind: 'whole', label: VL.step4.show.whole, assetKey: mainKey, region: null, borrowedCount: 0, notFound: false };
  }
  if (show.whole) {
    return { kind: 'whole', label: VL.step4.show.whole, assetKey: mainKey, region: null, borrowedCount: 0, notFound: false };
  }
  if (typeof show.region === 'string') {
    const main = assets?.[mainKey] || null;
    const name = regionDisplayName(main, show.region);
    return {
      kind: 'region',
      label: VL.step4.show.region(name),
      region: show.region,
      regionName: name,
      assetKey: mainKey,
      borrowedCount: 0,
      notFound: false,
    };
  }
  if (typeof show.picture === 'string') {
    const info = singlePictureInfo(show.picture, { assets, mainKey });
    return {
      kind: 'picture',
      label: VL.step4.show.picture(info.caption),
      ...info,
      borrowedCount: 1,
      notFound: false,
    };
  }
  if (typeof show.want === 'string') {
    const w = wantedById.get(show.want) || null;
    const subj = w?.subject ? castById.get(w.subject) : null;
    const subjectName = cleanText(subj?.name) || cleanText(w?.search) || VL.step4.show.noCaption;
    const tried = Array.isArray(w?.tried) ? w.tried.map(cleanText).filter(Boolean) : [];
    const fallback = resolveShow(show.else || { whole: true }, { wantedById, castById, assets, mainKey });
    if (w?.status === 'found' && typeof w.picture === 'string') {
      const info = singlePictureInfo(w.picture, { assets, mainKey });
      return {
        kind: 'picture',
        label: VL.step4.show.picture(info.caption),
        ...info,
        wantedId: show.want,
        subjectName,
        borrowedCount: 1,
        notFound: false,
      };
    }
    if (w?.status === 'none') {
      return {
        kind: 'want_none',
        wantedId: show.want,
        subjectName,
        search: cleanText(w.search),
        tried,
        fallback,
        label: VL.step4.show.notFoundSubject(subjectName),
        borrowedCount: 0,
        notFound: true,
      };
    }
    return {
      kind: 'want_open',
      wantedId: show.want,
      subjectName,
      search: cleanText(w?.search),
      tried,
      fallback,
      label: VL.step4.show.notFoundSubject(subjectName),
      borrowedCount: 0,
      notFound: false,
    };
  }
  if (Array.isArray(show.pair)) {
    const items = show.pair.map((part) => resolveShow(part, { wantedById, castById, assets, mainKey }));
    return {
      kind: 'pair',
      label: VL.step4.show.pair,
      items,
      borrowedCount: items.reduce((sum, it) => sum + (it.borrowedCount || 0), 0),
      notFound: items.some((it) => it.notFound),
    };
  }
  if (show.map && typeof show.map === 'object') {
    const places = Array.isArray(show.map.places) ? show.map.places.map(cleanText).filter(Boolean) : [];
    const mapKey = typeof show.map.picture === 'string' ? show.map.picture : null;
    const hasMap = Boolean(mapKey && assets?.[mapKey]);
    const fallback = !hasMap && show.else ? resolveShow(show.else, { wantedById, castById, assets, mainKey }) : null;
    return {
      kind: 'map',
      places,
      placesText: places.join(' → '),
      label: VL.step4.show.map(places.join(' → ')),
      assetKey: hasMap ? mapKey : null,
      fallback,
      borrowedCount: hasMap ? 1 : 0,
      notFound: false,
    };
  }
  return { kind: 'whole', label: VL.step4.show.whole, assetKey: mainKey, region: null, borrowedCount: 0, notFound: false };
}

function wordAtText(words, idx) {
  if (!Number.isInteger(idx) || !Array.isArray(words) || idx < 0 || idx >= words.length) return '';
  return cleanText(words[idx]?.w);
}

/** Turn a moment's `say` intents into plain Vietnamese descriptions with where they happen. */
export function describeIntents(moment, { castById = new Map(), mainAsset = null, words = [] } = {}) {
  const out = { intros: [], points: [], reads: [], labels: [], numbers: [] };
  for (const intent of moment?.say || []) {
    if (!intent || typeof intent !== 'object') continue;
    if (typeof intent.intro === 'string') {
      const subj = castById.get(intent.intro);
      const name = cleanText(subj?.name) || intent.intro;
      const sub = subj?.strip ? cleanText(subj?.sub) : '';
      const where = wordAtText(words, intent.word);
      out.intros.push({
        name,
        sub,
        where,
        text: VL.step4.meta.introAt(name, sub, where),
      });
    } else if (Array.isArray(intent.point)) {
      const items = intent.point.map((pt) => {
        const regName = regionDisplayName(mainAsset, pt?.region);
        const where = wordAtText(words, pt?.word);
        return { region: pt?.region, name: regName, where, text: VL.step4.meta.pointItem(regName, where) };
      });
      out.points.push(...items);
    } else if (intent.read && typeof intent.read === 'object') {
      const regName = regionDisplayName(mainAsset, intent.read.region);
      const reading = cleanText(intent.read.text);
      out.reads.push({ regionName: regName, text: reading ? `${regName}: “${reading}”` : regName });
    } else if (Array.isArray(intent.labels)) {
      const items = intent.labels.map((lb) => {
        const regName = regionDisplayName(mainAsset, lb?.region);
        const label = cleanText(lb?.text);
        return label ? `${label} (${regName})` : regName;
      });
      if (items.length) out.labels.push(items.join(', '));
    } else if (intent.number && typeof intent.number === 'object') {
      const num = cleanText(intent.number.text);
      const of = cleanText(intent.number.of);
      out.numbers.push(of ? `${num} — ${of}` : num);
    }
  }
  return out;
}

const chapterHeading = (ch, idx) => {
  const title = cleanText(ch?.title || ch?.name);
  if (!title || /^c\d+$/i.test(title)) return VL.step4.chapterN(idx + 1);
  const pretty = ID_LOOKING.test(title) ? title[0] + title.slice(1).toLowerCase().replace(/_/g, ' ') : title;
  return VL.step4.chapterNamed(idx + 1, pretty);
};

/** Build the complete view model for Step 4 ("Kịch bản hình"). */
export function buildVisualScriptView({ visual = null, picks = null, narration = null, words = [] } = {}) {
  const castById = new Map((visual?.cast || []).map((c) => [c.id, c]));
  const wantedById = new Map((visual?.wanted || []).map((w) => [w.id, w]));
  const assets = picks?.assets || {};
  const mainKey = picks?.main_asset || null;
  const mainAsset = mainKey ? assets[mainKey] || null : null;

  const regionCounts = new Map();
  let borrowedCount = 0;
  let notFoundCount = 0;
  const notFoundMoments = [];
  const momentsByLine = new Map();

  for (const m of visual?.moments || []) {
    const resolved = resolveShow(m.show, { wantedById, castById, assets, mainKey });
    borrowedCount += resolved.borrowedCount || 0;
    if (resolved.notFound) {
      notFoundCount++;
      notFoundMoments.push(m.id);
    }
    const regionUsed = resolved.kind === 'region'
      ? resolved.region
      : (resolved.fallback?.kind === 'region' ? resolved.fallback.region : null);
    if (regionUsed) regionCounts.set(regionUsed, (regionCounts.get(regionUsed) || 0) + 1);

    const span = momentWordsText(m, words);
    const subj = m.about ? castById.get(m.about) : null;
    const aboutName = subj ? cleanText(subj.name) : '';
    const intents = describeIntents(m, { castById, mainAsset, words });
    const whyText = momentWhy(m);
    const vm = {
      id: m.id,
      lineId: m.line,
      wordsText: span.text,
      timeText: span.timeText,
      durText: span.durText,
      show: resolved,
      moveLabel: VL.step4.move[m.move] || '',
      aboutName,
      aboutNotShown: cleanText(m.about_not_shown),
      intents,
      whyText,
    };
    if (!momentsByLine.has(m.line)) momentsByLine.set(m.line, []);
    momentsByLine.get(m.line).push(vm);
  }

  const chapters = [];
  const seenLines = new Set();
  let lineNum = 0;
  for (const [ci, ch] of (narration?.chapters || []).entries()) {
    const lines = [];
    for (const b of ch.beats || []) {
      lineNum++;
      seenLines.add(b.id);
      const moments = momentsByLine.get(b.id) || [];
      lines.push({
        id: b.id,
        number: lineNum,
        text: cleanText(b.text),
        moments,
        hasNotFound: moments.some((x) => x.show.notFound),
        timeText: moments[0]?.timeText || '',
      });
    }
    chapters.push({
      id: ch.id || `c${ci + 1}`,
      title: chapterHeading(ch, ci),
      lines,
      lineIds: lines.map((l) => l.id),
    });
  }

  // Fallback for any moments whose line is not in narration.chapters
  const strayLineIds = [...momentsByLine.keys()].filter((lid) => !seenLines.has(lid));
  if (strayLineIds.length) {
    const strayLines = strayLineIds.map((lid) => {
      lineNum++;
      const moments = momentsByLine.get(lid) || [];
      return {
        id: lid,
        number: lineNum,
        text: moments.map((x) => x.wordsText).filter(Boolean).join(' '),
        moments,
        hasNotFound: moments.some((x) => x.show.notFound),
        timeText: moments[0]?.timeText || '',
      };
    });
    chapters.push({
      id: 'extra',
      title: VL.step4.chapterN(chapters.length + 1),
      lines: strayLines,
      lineIds: strayLines.map((l) => l.id),
    });
  }

  const topRegions = [...regionCounts.entries()]
    .sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1))
    .slice(0, 5)
    .map(([region, count]) => ({
      region,
      name: regionDisplayName(mainAsset, region),
      count,
    }));

  const allLines = chapters.flatMap((c) => c.lines);
  return {
    counts: {
      moments: (visual?.moments || []).length,
      borrowed: borrowedCount,
      notFound: notFoundCount,
      topRegions,
    },
    chapters,
    lines: allLines,
    order: allLines.map((l) => l.id),
    chapterLines: Object.fromEntries(chapters.map((c) => [c.id, c.lineIds])),
    notFoundLineIds: allLines.filter((l) => l.hasNotFound).map((l) => l.id),
  };
}
