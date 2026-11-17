// Single draft store with undo/redo. No DOM. Snapshots are stripped JSON strings.
import { derive, stripDerived, clone } from './logic.js';

/** Content snapshot (JSON string) of a storyboard: no derived keys, no approvals. */
export function snapOf(sb) {
  const c = stripDerived(sb);
  delete c.approvals;
  return JSON.stringify(c);
}

export class Store {
  constructor(limit = 200) {
    this.limit = limit;
    this.draft = null; this.timing = null; this.rev = null;
    this.undoStack = []; this.redoStack = [];
    this.savedSnap = ''; this.lastKey = null; this.lastAt = 0;
    this.listeners = new Set();
    this.version = 0;        // every emit
    this.editVersion = 0;    // every change of the draft (edit, undo, redo, load): lets a late answer know it is out of date
    this.sel = { shot: null, overlay: null };
  }
  reset() {
    this.draft = null; this.timing = null; this.rev = null; this.undoStack = []; this.redoStack = [];
    this.savedSnap = ''; this.lastKey = null; this.lastAt = 0; this.listeners.clear(); this.version = 0; this.editVersion = 0;
    this.sel = { shot: null, overlay: null };
  }
  on(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn); }
  emit(kind = 'draft') { this.version++; for (const fn of this.listeners) fn(kind); }
  /** What "unsaved" means: the content of the storyboard. `approvals` belongs to the server (it changes on Duyệt and on Lưu), never to the draft. */
  snap() { return snapOf(this.draft); }

  load(storyboard, timing, rev) {
    this.draft = clone(storyboard);
    this.timing = timing; this.rev = rev;
    derive(this.draft, timing);
    this.undoStack = []; this.redoStack = []; this.lastKey = null;
    this.savedSnap = this.snap();
    this.editVersion++;
    this.emit('load');
  }
  /** Start a save: what is sent, and the state it was taken from. Edits made after this call are NOT part of the save. */
  beginSave() {
    return { board: stripDerived(this.draft), snap: this.snap(), version: this.editVersion, rev: this.rev };
  }
  /** The server accepted `sent`. The saved baseline is what the server holds; the draft keeps every edit made since the request
   * was sent (so the unsaved marker stays true). Server-owned parts (approvals, anything the user did not touch) are adopted. */
  finishSave(sent, serverBoard, rev) {
    this.rev = rev;
    const edited = this.snap() !== sent.snap;
    const baseline = serverBoard ? snapOf(serverBoard) : sent.snap;
    if (serverBoard) {
      if (!edited) { this.draft = clone(serverBoard); }
      else {
        this.draft.approvals = clone(serverBoard.approvals);
        for (const k of Object.keys(serverBoard)) {
          if (k === 'shots' || k === 'approvals') continue;
          if (JSON.stringify(sent.board[k]) === JSON.stringify(stripDerived(this.draft)[k])) this.draft[k] = clone(serverBoard[k]);
        }
      }
      derive(this.draft, this.timing);
    }
    this.savedSnap = baseline;
    this.emit('saved');
    return { edited };
  }
  /** The server has a newer version (`theirsBoard`, `rev`). The draft becomes `merged` (an edit the owner can undo) and the saved
   * baseline becomes the server's version, so the next save is "my draft on top of what the server has". */
  rebase(merged, theirsBoard, rev, label = 'Ghép với bản khác') {
    const before = this.snap();
    this.draft = clone(merged);
    this.draft.approvals = clone(theirsBoard.approvals);
    derive(this.draft, this.timing);
    if (this.snap() !== before) { this.undoStack.push({ label, snap: before }); if (this.undoStack.length > this.limit) this.undoStack.shift(); this.redoStack = []; }
    this.rev = rev; this.savedSnap = snapOf(theirsBoard); this.lastKey = null;
    this.editVersion++;
    this.emit('draft');
  }
  /** Only the server-owned approvals changed (Duyệt): the content, and so the unsaved marker, is untouched. */
  setApprovals(approvals) {
    this.draft.approvals = clone(approvals);
    this.emit('approvals');
  }
  get dirty() { return !!this.draft && this.snap() !== this.savedSnap; }
  get canUndo() { return this.undoStack.length > 0; }
  get canRedo() { return this.redoStack.length > 0; }

  /** Apply fn(draft). coalesce: same key within `ms` merges into one history step (drags, typing). */
  commit(label, fn, { coalesce = null, ms = 900 } = {}) {
    const before = this.snap();
    const now = Date.now();
    fn(this.draft);
    derive(this.draft, this.timing);
    const after = this.snap();
    if (after === before) return false;
    const merge = coalesce && coalesce === this.lastKey && now - this.lastAt < ms && this.undoStack.length;
    if (!merge) {
      this.undoStack.push({ label, snap: before });
      if (this.undoStack.length > this.limit) this.undoStack.shift();
    }
    this.redoStack = [];
    this.lastKey = coalesce; this.lastAt = now;
    this.editVersion++;
    this.emit('draft');
    return true;
  }
  _restore(snap) {
    const approvals = this.draft?.approvals;
    this.draft = JSON.parse(snap);
    if (approvals !== undefined) this.draft.approvals = approvals;
    derive(this.draft, this.timing);
    this.lastKey = null;
  }
  undo() {
    const e = this.undoStack.pop();
    if (!e) return false;
    this.redoStack.push({ label: e.label, snap: this.snap() });
    this._restore(e.snap); this.editVersion++; this.emit('draft'); return true;
  }
  redo() {
    const e = this.redoStack.pop();
    if (!e) return false;
    this.undoStack.push({ label: e.label, snap: this.snap() });
    this._restore(e.snap); this.editVersion++; this.emit('draft'); return true;
  }
  select(shot, overlay = null) {
    this.sel = { shot, overlay };
    this.emit('select');
  }
  shotById(id) { return this.draft?.shots.find((s) => s.id === id) || null; }
  get shot() { return this.shotById(this.sel.shot); }
  get overlay() {
    const s = this.shot;
    return s ? (s.overlays || []).find((o) => o.id === this.sel.overlay) || null : null;
  }
}
