// Home: the projects, each with its stage and a "Tiếp tục" button that opens it at the step its stage calls for.
import { api } from '../api.js';
import { SHOW_ALL } from '../config.js';
import { h } from '../util.js';
import { stageLabel } from '../labels.js';
import { projectHash } from '../router.js';

const when = (s) => (s || '').slice(0, 16).replace('T', ' ');

export async function mount(host, { shell, scope }) {
  const root = h('div', { class: 'home' });
  host.append(root);
  root.append(h('div', { class: 'muted', text: 'Đang tải danh sách dự án...' }));

  async function load() {
    const all = await shell.refreshProjects();
    if (scope.dead) return;
    const list = all.filter((p) => SHOW_ALL || !/^(lab_|demo_)/.test(p.id))
      .sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')));
    const pipes = await Promise.all(list.map((p) => api.pipeline(p.id).catch(() => null)));
    if (scope.dead) return;
    render(list, pipes);
  }

  function row(p, pl) {
    const cur = pl?.steps.find((s) => s.id === pl.current);
    const del = pl?.protected
      ? h('span', { class: 'tag', title: 'Dự án gốc, không xóa được', text: 'được bảo vệ' })
      : h('button', { class: 'small danger', text: 'Xóa', title: 'Xóa dự án này (phải gõ mã dự án để xác nhận)', onclick: async () => { if (await shell.deleteProject(p)) { shell.refreshProjects(); load(); } } });
    return h('div', { class: 'prow', 'data-pid': p.id },
      h('div', null, h('div', { class: 'pt', text: p.title || p.id }), h('div', { class: 'mono', text: p.id }),
        pl?.painting?.title ? h('div', { class: 'sub', text: [pl.painting.title, [pl.painting.artist, pl.painting.year].filter(Boolean).join(', ')].join(' · ') }) : null),
      h('div', null, h('div', null, h('span', { class: 'tag', text: stageLabel(p.stage) }), pl?.imported ? h('span', { class: 'tag', style: { marginLeft: '6px' }, title: 'Không đi qua các bước từ thư viện', text: 'nhập từ bản cũ' }) : null),
        pl ? h('div', { class: 'minisb', title: pl.steps.map((s) => `${s.n}. ${s.label}`).join('  |  ') }, pl.steps.map((s) => h('i', { class: `st-${s.state}` + (s.id === pl.current ? ' at' : '') }))) : null),
      h('div', null, cur ? h('div', null, 'Tiếp theo: ', h('b', { text: `${cur.n}. ${cur.label}` })) : null,
        h('div', { class: 'sub', text: (cur?.detail || '') + (cur && cur.state === 'not_built' ? ' Bước này chưa được xây dựng.' : '') }),
        p.updated_at ? h('div', { class: 'sub', text: 'Cập nhật ' + when(p.updated_at) }) : null),
      h('div', { class: 'acts' }, del,
        h('button', { class: 'primary', text: 'Tiếp tục', title: cur ? `Mở bước ${cur.label}` : 'Mở dự án', onclick: () => shell.go(projectHash(p.id)) })));
  }

  function render(list, pipes) {
    root.replaceChildren(
      h('div', { class: 'head' }, h('div', null, h('h1', { text: 'Dự án' }), h('div', { class: 'muted', text: list.length ? `${list.length} dự án. "Tiếp tục" mở dự án ở bước mà giai đoạn của nó cần làm tiếp.` : 'Chưa có dự án nào.' })), h('span', { class: 'grow' }),
        h('button', { class: 'primary', text: '+ Tạo video mới', onclick: () => shell.go('#/library') })),
      list.length ? h('div', { class: 'plist' }, list.map((p, i) => row(p, pipes[i])))
        : h('div', { class: 'empty-box' }, 'Một video bắt đầu từ một tác phẩm trong thư viện sách.', h('div', { style: { marginTop: '12px' } }, h('button', { class: 'primary', text: 'Tạo video mới', onclick: () => shell.go('#/library') }))));
  }

  await load();
  return { pipelineChanged: () => {} };
}
