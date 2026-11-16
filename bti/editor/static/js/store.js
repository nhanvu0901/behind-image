// Single draft store with undo/redo. No DOM. Snapshots are stripped JSON strings.
import { derive, stripDerived, clone } from './logic.js';

export class Store {
  constructor(limit = 200) {
    this.limit = limit;
    this.draft = null; this.timing = null; this.rev = null;
    this.undoStack = []; this.redoStack = [];
    this.savedSnap = ''; this.lastKey = null; this.lastAt = 0;
    this.listeners = new Set();
    this.version = 0;
    this.sel = { shot: null, overlay: null };
  }
  reset() {
    this.draft = null; this.timing = null; this.rev = null; this.undoStack = []; this.redoStack = [];
    this.savedSnap = ''; this.lastKey = null; this.lastAt = 0; this.listeners.clear(); this.version = 0;
    this.sel = { shot: null, overlay: null };
  }
  on(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn); }
  emit(kind = 'draft') { this.version++; for (const fn of this.listeners) fn(kind); }
  snap() { return JSON.stringify(stripDerived(this.draft)); }

  load(storyboard, timing, rev) {
    this.draft = clone(storyboard);
    this.timing = timing; this.rev = rev;
    derive(this.draft, timing);
    this.undoStack = []; this.redoStack = []; this.lastKey = null;
    this.savedSnap = this.snap();
    this.emit('load');
  }
  /** After a successful save: the server's copy becomes the baseline, history is kept. */
  markSaved(storyboard, rev) {
    this.rev = rev;
    if (storyboard) {
      this.draft = clone(storyboard); derive(this.draft, this.timing);
    }
    this.savedSnap = this.snap();
    this.emit('saved');
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
    this.emit('draft');
    return true;
  }
  _restore(snap) {
    this.draft = JSON.parse(snap);
    derive(this.draft, this.timing);
    this.lastKey = null;
  }
  undo() {
    const e = this.undoStack.pop();
    if (!e) return false;
    this.redoStack.push({ label: e.label, snap: this.snap() });
    this._restore(e.snap); this.emit('draft'); return true;
  }
  redo() {
    const e = this.redoStack.pop();
    if (!e) return false;
    this.undoStack.push({ label: e.label, snap: this.snap() });
    this._restore(e.snap); this.emit('draft'); return true;
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
