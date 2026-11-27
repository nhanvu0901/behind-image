// Pure formatting helpers for the quality scorecard shown on the export page.
import { SCORECARD_LABELS } from './labels.js';

const comma = (n, d = 1) => Number(n).toFixed(d).replace('.', ',');

export function formatClock(sec) {
  const s = Math.max(0, Math.floor(Number(sec) || 0));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}` : `${m}:${String(r).padStart(2, '0')}`;
}

export function formatMetricValue(m) {
  const k = m?.key, v = m?.value;
  if (v === null || v === undefined) return k === 'loudness' || k === 'pause_vs_speech' ? 'Chưa xuất video' : 'Chưa có dữ liệu';
  if (k === 'small_painting_share') return `${comma(Number(v) * 100, 1)}% (${comma(m.seconds || 0, 1)} giây / ${m.shot_count || 0} cảnh)`;
  if (k === 'marks_per_minute') return `${comma(v, 2)}/phút (${m.total || 0} dấu: ${m.rings || 0} vòng tròn, ${m.spotlights || 0} đèn rọi)`;
  if (k === 'biggest_mark') return `${comma(Number(v) * 100, 1)}% (${m.over_30_count || 0} dấu > 30%)`;
  if (['marks_on_person', 'short_shots', 'subject_not_shown', 'unfilled_identity'].includes(k)) return String(v);
  if (k === 'name_strips') {
    const thing = v.on_thing === null || v.on_thing === undefined ? 'chưa xét' : `${v.on_thing} trên vật thường`;
    return `${v.count || 0} nhãn (${v.sub_repeats || 0} lặp tên, ${thing})`;
  }
  if (k === 'borrowed_pictures') {
    return `${v.count || 0} hình (${comma(v.seconds || 0, 1)} giây, ${comma(Number(v.share || 0) * 100, 1)}%; trống ${comma(v.longest_gap_s || 0, 1)} giây; ${v.under_3s_count || 0} < 3 giây)`;
  }
  if (k === 'repeated_regions') {
    const top = (m.items || [])[0];
    return top ? `${top.count} lần (${top.label || top.region})` : '0';
  }
  if (k === 'loudness') return `${comma(v.lufs, 1)} LUFS`;
  if (k === 'pause_vs_speech') return `Thấp hơn lời ${comma(v.diff_db, 1)} dB`;
  return String(v);
}

export function formatMetricTarget(m) {
  const k = m?.key, t = m?.target;
  const T = SCORECARD_LABELS.target;
  if (k === 'small_painting_share') return T.maxPct(Math.round(Number(t) * 100));
  if (k === 'marks_per_minute') return T.maxRate(comma(t, 1));
  if (k === 'biggest_mark') return T.maxPct(Math.round(Number(t) * 100));
  if (['marks_on_person', 'short_shots', 'subject_not_shown', 'unfilled_identity'].includes(k)) return T.zero;
  if (k === 'name_strips') return T.strips;
  if (k === 'borrowed_pictures') return T.borrowed(comma(t?.min_s ?? 3, 1), comma(t?.max_gap_s ?? 120, 0));
  if (k === 'repeated_regions') return T.maxRepeat(t);
  if (k === 'loudness') return T.loudness(comma(t?.lufs ?? -15, 1), comma(t?.tolerance ?? 1.5, 1));
  if (k === 'pause_vs_speech') return T.pause(comma(t?.min_db ?? 6, 0), comma(t?.max_db ?? 22, 0));
  return String(t ?? '');
}

export function formatMetricDetail(m) {
  const k = m?.key, items = m?.items || [];
  if (!items.length) return '';
  if (k === 'repeated_regions') {
    return items.slice(0, 3).map((it) => `${it.label || it.region} (${it.count})`).join(' · ');
  }
  if (k === 'name_strips') {
    const bad = items.filter((it) => it.sub_repeats || it.on_thing);
    return bad.slice(0, 4).map((it) => `${formatClock(it.time)} ${it.text}`).join(' · ');
  }
  if (m?.ok === false) {
    return items.slice(0, 4).map((it) => `${formatClock(it.time)} ${it.at || it.region || it.title || it.name || it.shot || ''}`.trim()).join(' · ');
  }
  return '';
}

export function scorecardRows(sc) {
  return (sc?.metrics || []).map((m) => ({
    key: m.key,
    label: SCORECARD_LABELS.metric[m.key] || m.key,
    valueText: formatMetricValue(m),
    targetText: formatMetricTarget(m),
    detail: formatMetricDetail(m),
    status: m.ok === true ? 'ok' : m.ok === false ? 'warn' : 'na',
    statusText: SCORECARD_LABELS.status[m.ok === true ? 'ok' : m.ok === false ? 'warn' : 'na'],
  }));
}

export function scorecardSummaryText(sc) {
  const s = sc?.summary;
  if (!s) return '';
  const evalTotal = (s.passed || 0) + (s.failed || 0);
  return SCORECARD_LABELS.summary(s.passed || 0, evalTotal, s.failed || 0);
}
