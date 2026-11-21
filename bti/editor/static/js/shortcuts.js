// Which keyboard shortcut of the storyboard view applies to a key press? One pure function decides, so every dialog, every text
// field and every modal state is handled in one place (U2-002: Delete, S and Space acted on the timeline behind a dialog).
//
// facts: { key, ctrl, meta, shift, alt, repeat, composing, target: {tag, type, editable, role}, modalOpen, picking, slotPicking, hasDraft }
// result: an action name, or null (the key is not ours: the page, the dialog or the focused control keeps it).

const TEXT_TYPES = new Set(['text', 'search', 'number', 'email', 'url', 'tel', 'password', 'date', 'time', 'datetime-local', 'month', 'week', '']);

/** What kind of element has the focus: 'text' (typing, select), 'control' (button, checkbox, range, select...: Space/Enter/arrows are its own) or 'none'. */
export function targetKind(t = {}) {
  const tag = String(t.tag || '').toLowerCase();
  if (t.editable) return 'text';
  if (tag === 'textarea' || tag === 'select') return 'text';        // a select takes letters (type-ahead) as well as arrows and Space
  if (tag === 'input') return TEXT_TYPES.has(String(t.type || '').toLowerCase()) ? 'text' : 'control';
  if (tag === 'button' || tag === 'a' || tag === 'summary' || tag === 'video' || tag === 'audio') return 'control';
  if (['button', 'tab', 'slider', 'menuitem', 'option', 'checkbox', 'radio', 'switch', 'link'].includes(String(t.role || ''))) return 'control';
  return 'none';
}

export const factsOf = (e, { modalOpen = false, picking = false, slotPicking = false, hasDraft = true } = {}) => ({
  key: e.key, ctrl: e.ctrlKey, meta: e.metaKey, shift: e.shiftKey, alt: e.altKey, repeat: e.repeat, composing: e.isComposing,
  target: { tag: e.target?.tagName, type: e.target?.type, editable: !!e.target?.isContentEditable, role: e.target?.getAttribute?.('role') },
  modalOpen, picking, slotPicking, hasDraft,
});

const ONE_SHOT = new Set([' ', 's', 'S', 'l', 'L', 'Delete', 'Backspace']);   // never repeat while a key is held

export function resolveShortcut(f) {
  if (f.composing) return null;
  const kind = targetKind(f.target);
  const mod = f.ctrl || f.meta;
  const k = String(f.key || '');
  if (f.modalOpen) return mod && k.toLowerCase() === 's' ? 'swallow' : null;   // a dialog owns the keyboard (it closes itself with Esc); Ctrl+S must not open the browser's save-page
  if (mod && k.toLowerCase() === 's' && !f.alt) return 'save';
  if (f.picking || f.slotPicking) return k === 'Escape' ? 'cancelpick' : null;   // choosing on the picture / an asset: only Esc is ours
  if (kind === 'text') return null;                     // typing: undo, arrows, Delete, Space all belong to the field
  if (mod) {
    if (f.alt) return null;
    if (k.toLowerCase() === 'z') return f.shift ? 'redo' : 'undo';
    if (k.toLowerCase() === 'y') return 'redo';
    return null;
  }
  if (f.alt || !f.hasDraft) return null;
  if (kind === 'control' && (k === ' ' || k === 'Enter' || k.startsWith('Arrow'))) return null;   // the focused control's own keys
  if (f.repeat && ONE_SHOT.has(k)) return null;
  switch (k) {
    case ' ': return 'play';
    case 's': case 'S': return 'split';
    case 'l': case 'L': return 'lock';
    case 'Delete': case 'Backspace': return 'delete';
    case '[': return 'prev';
    case ']': return 'next';
    case 'ArrowLeft': return 'wordprev';
    case 'ArrowRight': return 'wordnext';
    case 'Escape': return 'escape';
    default: return null;
  }
}
