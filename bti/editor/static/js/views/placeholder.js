// Steps that have nothing to edit: imported projects (no data), steps that are not built yet (honest placeholder), locked steps.
// No fake controls: the only buttons here are real navigation.
import { h } from '../util.js';
import { PLANNED } from '../labels.js';
import { nextOpenable } from '../stepper.js';
import { projectHash } from '../router.js';

const mb = (n) => (n >= 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(n / 1024)) + ' KB');

export async function mount(host, { shell, kind, step, pipeline }) {
  const pid = pipeline.project;
  const root = h('div', { class: 'infov', 'data-kind': kind, 'data-step': step.id });
  host.append(root);
  const next = nextOpenable(pipeline.steps, step.id);
  const edit = pipeline.steps.find((s) => s.id === 'edit');
  const acts = h('div', { class: 'acts' },
    kind === 'nodata' && edit && edit.state !== 'locked' ? h('button', { class: 'primary', text: 'Mở bước Dựng hình', onclick: () => shell.go(projectHash(pid, 'edit')) }) : null,
    kind !== 'nodata' && next ? h('button', { class: 'primary', text: `Tiếp tục: ${next.label}`, title: next.state === 'not_built' ? 'Bước kế tiếp cũng chưa được xây dựng' : '', onclick: () => shell.go(projectHash(pid, next.id)) }) : null,
    h('a', { class: 'lnk', href: '#/', text: 'Về danh sách dự án', style: { alignSelf: 'center' } }));

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
  const pl = PLANNED[step.id] || { title: step.label, will: [], meanwhile: '' };
  root.append(h('h1', { text: `${step.n}. ${pl.title}` }),
    h('div', { class: 'box warn' }, h('b', { text: 'Bước này chưa được xây dựng. ' }), 'Chưa có gì để làm hoặc để bấm ở đây.'),
    h('div', { class: 'box' }, h('h4', { text: 'Khi xây xong, bước này sẽ' }), h('ul', null, pl.will.map((t) => h('li', { text: t })))),
    h('div', { class: 'muted', text: pl.meanwhile }));
  if (step.id === 'export') {
    const out = pipeline.outputs || [];
    root.append(h('div', { class: 'box' }, h('h4', { text: 'Tệp video đã có' }),
      out.length ? h('div', { class: 'files' }, out.map((o) => h('div', { class: 'file' }, h('code', { text: `projects/${pid}/${o.path}` }), h('span', { class: 'muted', text: mb(o.size) }),
        h('a', { class: 'lnk', href: o.url, target: '_blank', rel: 'noopener', text: 'Mở tệp' }))))
        : h('div', { class: 'muted', text: 'Dự án này chưa có tệp video dựng sẵn.' })));
  }
  root.append(acts);
  return {};
}
