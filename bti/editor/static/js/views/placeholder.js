// Steps that have nothing to open: imported projects (no data) and locked steps.
// No fake controls: the only buttons here are real navigation.
import { h, kids } from '../util.js';
import { OPEN_STEP } from '../labels.js';
import { nextOpenable } from '../stepper.js';
import { projectHash } from '../router.js';

export async function mount(host, { shell, kind, step, pipeline }) {
  const pid = pipeline.project;
  const root = h('div', { class: 'infov', 'data-kind': kind, 'data-step': step.id });
  host.append(root);
  const next = nextOpenable(pipeline.steps, step.id);
  const edit = pipeline.steps.find((s) => s.id === 'edit');
  // a locked page always says which step has to be done first and takes the owner there
  const blocker = kind === 'locked' ? pipeline.steps.find((s) => s.id === step.blocked_by && s.state !== 'locked') : null;
  const acts = h('div', { class: 'acts' }, ...kids(
    blocker ? h('button', { class: 'primary', text: OPEN_STEP(blocker.label), onclick: () => shell.go(projectHash(pid, blocker.id)) }) : null,
    kind === 'nodata' && edit && edit.state !== 'locked' ? h('button', { class: 'primary', text: 'Mở bước Dựng hình', onclick: () => shell.go(projectHash(pid, 'edit')) }) : null,
    kind !== 'nodata' && !blocker && next ? h('button', { class: 'primary', text: `Tiếp tục: ${next.label}`, title: next.state === 'not_built' ? 'Bước kế tiếp cũng chưa được xây dựng' : '', onclick: () => shell.go(projectHash(pid, next.id)) }) : null,
    h('a', { class: 'lnk', href: '#/', text: 'Về danh sách dự án', style: { alignSelf: 'center' } })));

  if (kind === 'nodata') {
    root.append(h('h1', { text: `${step.n}. ${step.label}` }),
      h('div', { class: 'box warn' }, h('b', { text: 'Dự án này được nhập từ bản dựng trước. ' }),
        `Nó chưa có dữ liệu cho bước "${step.label}": dự án không đi qua thư viện sách, kịch bản, giọng đọc hay bước chọn hình, mà chỉ có storyboard đã dựng sẵn.`),
      h('div', { class: 'muted', text: 'Bước Dựng hình dùng được bình thường. Muốn làm một video từ đầu, hãy tạo video mới từ một tác phẩm trong thư viện.' }), acts);
    return {};
  }
  if (kind === 'locked') {
    root.append(h('h1', { text: `${step.n}. ${step.label}` }), h('div', { class: 'box warn' }, h('b', { text: 'Bước này đang khóa. ' }), step.reason), acts);
    return {};
  }
  root.append(h('h1', { text: `${step.n}. ${step.label}` }), h('div', { class: 'box warn' }, step.reason || 'Bước này chưa mở được.'), acts);
  return {};
}
