// The tag of a restored source, one look for every view that shows trust (library, script step, artwork step).
// The yellow tag of a low-trust source stays where it is (`tag lowtrust`); a restored source gets this blue one.
import { h } from './util.js';
import { RESTORED_NOTE, TRUST_LEVEL } from './labels.js';

const BLUE = { color: 'var(--accent)', borderColor: '#25507f', background: '#0f1b2d' };

/** "Bản khôi phục", with the note in the tooltip. */
export const restoredTag = (note) => h('span', { class: 'tag restored', title: note || RESTORED_NOTE, style: BLUE, text: TRUST_LEVEL.restored });
/** The same look for a short tag whose own words are given (a book badge). */
export const restoredStyle = BLUE;
