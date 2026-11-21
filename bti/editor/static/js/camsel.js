// Which camera key is selected (d-camera, D22): one small shared state between the preview (frames on the picture) and the form
// (the block of the key). No DOM. `shot` is the id of the shot it belongs to; a selection of another shot is ignored.
import { bus } from './ctx.js';

let sel = { shot: null, param: null, index: 0 };
export const camSel = () => sel;
/** Select key `index` of camera parameter `param` of shot `shot`; tells the preview and the form when it changed. `from` names who asked. */
export function setCamSel(shot, param, index, from = '') {
  if (sel.shot === shot && sel.param === param && sel.index === index) return false;
  sel = { shot, param, index };
  bus.emit('camsel', { ...sel, from });
  return true;
}
/** Is key `index` of `param` the selected one of shot `shot`? */
export const isCamSel = (shot, param, index) => sel.shot === shot && sel.param === param && sel.index === index;
