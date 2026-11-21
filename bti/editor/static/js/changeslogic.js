// "Lịch sử thay đổi" (worker c2box): the pure parts of the list of changes of one document. changeslist.js draws; this file decides.
// A record is one batch of the change log (GET /api/projects/{pid}/changes): time, actor, the owner's request as its note, the sentences of what
// it changed, and `undone_by`. A row can be undone only when the state answer (GET /api/projects/{pid}/state) names that batch as the one that can
// be undone now (its action `changes.undo`). Tested in tests/editor_frontend/changeslist.test.mjs.
import { BOX_LABELS as BL } from './labels.js';
import { authorLabel } from './agentlogic.js';

const pad2 = (n) => String(n).padStart(2, '0');
const sameDay = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();

/** The time of a record as the owner reads it: "14:20", or "14:20 ngày 18/11" for another day (with the year for another year). '' when unreadable.
 *  The server writes its local time with the offset ("2026-11-19T14:20:05+0700"); the page shows the clock of the server's own stamp. */
export function whenLabel(iso, now = new Date()) {
  const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/.exec(String(iso || ''));
  if (!m) return '';
  const d = new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]);
  const hm = `${m[4]}:${m[5]}`;
  if (sameDay(d, now)) return BL.changes.today(hm);
  return BL.changes.other(hm, `${pad2(d.getDate())}/${pad2(d.getMonth() + 1)}${d.getFullYear() !== now.getFullYear() ? '/' + d.getFullYear() : ''}`);
}

/** Who made a change: "Bạn", the label of the agent ("Opus 5.5 High"), "Công cụ ngoài" for a command line. Never the raw actor. */
export function whoLabel(actor, agents) {
  const raw = typeof actor === 'string' ? actor.trim() : '';
  if (/^cli:/i.test(raw)) return BL.changes.tool;
  return authorLabel(agents, raw) || BL.changes.agent;
}

/** The batch the state answer says can be undone now: `{batch, body, path, doc}` or null. `doc` is the step it belongs to (`picks` | `edit`). */
export function undoTarget(state) {
  const a = (state?.next_actions || []).find((x) => x?.id === 'changes.undo' && x.ready);
  const m = a && /\/changes\/(batch_\d+)\/undo$/.exec(String(a.path || ''));
  return m ? { batch: m[1], body: a.body || null, path: a.path, step: a.step || null } : null;
}

/** The rows of the list, newest first as the server gives them. `target`: what `undoTarget` returned. */
export function changeRows(records, { agents = null, now = new Date(), target = null } = {}) {
  return (Array.isArray(records) ? records : []).map((r) => {
    const lines = (Array.isArray(r?.changes) ? r.changes : []).map((c) => String(c?.what || '')).filter(Boolean);
    const undone = !!r?.undone_by;
    return {
      batch: r?.batch || '', when: whenLabel(r?.time, now), who: whoLabel(r?.actor, agents), isUndo: !!r?.undo_of,
      note: r?.undo_of ? '' : String(r?.note || '').trim(), lines, undone,
      canUndo: !!target && target.batch === r?.batch && !undone,
    };
  });
}

/** What the undo of a row sends: the body the state answer gave, as the owner ("human"). */
export const undoBody = (target) => ({ ...(target?.body || {}), actor: 'human', note: '' });
