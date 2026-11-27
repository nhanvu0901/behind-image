// Step 4 ("Kịch bản hình") on the unified visual path.
// Shows narration line by line with each line's moments in order, thumbnails, cast/intents/reason,
// not-found wanted pictures with every wording tried and fallback, top counts, state buttons, and visual.edit box.
import { api } from '../api.js';
import { h, kids, toast, confirmDialog } from '../util.js';
import { describeError, jobErrorText } from '../errmsg.js';
import { VISUAL_PAGE_LABELS as VL } from '../labels.js';
import { cropStyle } from './picks_logic.js';
import { emptySelection, applyClick, selectChapter, pruneSelection } from '../selectlogic.js';
import { buildVisualScriptView, findStateAction, needsHint, visualEditAction } from '../visualpage_logic.js';
import { mountVisualBox } from '../visual_box.js';
import { projectHash } from '../router.js';

const ACTIVE = new Set(['queued', 'waiting', 'running']);

function ensureCss() {
  if (document.querySelector('link[data-visual-css]')) return;
  const l = h('link', { rel: 'stylesheet', href: new URL('../../css/visual.css', import.meta.url).href });
  l.dataset.visualCss = '1';
  document.head.append(l);
}

function mapSvg() {
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('width', '26');
  svg.setAttribute('height', '26');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '1.8');
  const p = document.createElementNS(ns, 'path');
  p.setAttribute('d', 'M3 6l6-2 6 2 6-2v14l-6 2-6-2-6 2V6zm6-2v14m6-12v14');
  svg.append(p);
  return svg;
}

export async function mountVisualScript(host, { pid, scope, shell, picksData = null, visualData = null, stateData = null } = {}) {
  ensureCss();
  const W = VL.step4;
  let dead = false, picks = picksData, visualDoc = visualData?.visual || null, state = stateData, wordsData = null;
  let sel = emptySelection(), lastNotFound = null, planJobId = null, planJob = null, planTimer = null, busyApprove = false;
  const collapsed = new Set();

  const root = h('div', { class: 'v-vis', 'data-step': 'picks', 'data-visual': '1' });
  const topEl = h('div', { class: 'v-vis-top' });
  const scrollEl = h('div', { class: 'v-vis-scroll', tabindex: 0 });
  const footEl = h('div', { class: 'v-vis-foot hint', text: W.rowsHint });
  const boxCol = h('aside', { class: 'v-vis-boxcol', hidden: true });
  const bodyEl = h('div', { class: 'v-vis-body', 'data-has-box': '0' },
    h('div', { class: 'v-vis-main' }, scrollEl, footEl),
    boxCol);
  root.append(topEl, bodyEl);
  host.replaceChildren(root);

  const P = `/api/projects/${encodeURIComponent(pid)}`;
  const imgUrl = (a, w = 480) => `${api.fileUrl(pid, a.file)}?w=${w}`;
  let vm = null;

  const visualBox = mountVisualBox(boxCol, {
    pid,
    scope,
    state,
    getScope: () => {
      const ids = sel.ids || [];
      if (!vm || !ids.length) return { text: VL.editBox.scopeAll, payload: { all: true } };
      const numById = new Map(vm.lines.map((l) => [l.id, l.number]));
      const nums = ids.map((id) => numById.get(id)).filter(Boolean).sort((a, b) => a - b);
      const text = nums.length === 1 ? VL.editBox.scopeLineOne(nums[0]) : VL.editBox.scopeLines(nums.slice(0, 6).join(', '));
      return { text, payload: { lines: ids } };
    },
    onDone: async () => { await reloadAll(); shell?.refreshPipeline?.(); },
  });

  function thumbBox(assetKey, region, size = 76) {
    const a = picks?.picks?.assets?.[assetKey];
    const el = h('div', { class: 'v-vis-thumb', style: { width: size + 'px', height: size + 'px' } });
    if (!a || !a.file) { el.classList.add('gone'); return el; }
    const crop = region ? cropStyle(a, a.regions?.[region], size) : null;
    el.style.backgroundImage = `url("${imgUrl(a, crop ? 900 : 240)}")`;
    if (crop) Object.assign(el.style, crop);
    else el.classList.add('fit');
    return el;
  }

  function renderShowVisual(show) {
    const assets = picks?.picks?.assets || {};
    const mainKey = picks?.picks?.main_asset || null;
    if (show.kind === 'pair') {
      return h('div', { class: 'v-vis-visual' },
        ...show.items.map((item) => h('figure', { class: 'v-vis-pic' },
          thumbBox(item.assetKey || mainKey, item.region || null, 76),
          h('figcaption', { class: 'v-vis-cap', text: item.caption || item.label }))));
    }
    if (show.kind === 'map') {
      const sign = h('div', { class: 'v-vis-mapsign' }, mapSvg(), h('span', { text: W.show.mapSign }));
      if (show.assetKey && assets[show.assetKey]) {
        return h('div', { class: 'v-vis-visual' },
          h('figure', { class: 'v-vis-pic' },
            thumbBox(show.assetKey, null, 76),
            h('figcaption', { class: 'v-vis-cap', text: show.label })));
      }
      return h('div', { class: 'v-vis-visual' },
        h('figure', { class: 'v-vis-pic' }, sign, h('figcaption', { class: 'v-vis-cap', text: show.label })));
    }
    if (show.kind === 'want_none' || show.kind === 'want_open') {
      const fb = show.fallback || { kind: 'whole', assetKey: mainKey, region: null, label: W.show.whole };
      return h('div', { class: 'v-vis-visual' },
        h('figure', { class: 'v-vis-pic' },
          thumbBox(fb.assetKey || mainKey, fb.region || null, 76),
          h('figcaption', { class: 'v-vis-cap', text: fb.label })));
    }
    const key = show.assetKey || mainKey;
    return h('div', { class: 'v-vis-visual' },
      h('figure', { class: 'v-vis-pic' },
        thumbBox(key, show.region || null, 76),
        h('figcaption', { class: 'v-vis-cap', text: show.kind === 'picture' ? (show.caption || W.show.noCaption) : show.label })));
  }

  function renderMoment(m, idx) {
    const whyText = m.whyText;
    const badges = [];
    if (m.aboutName) badges.push(h('span', { class: 'v-vis-badge', text: `${W.meta.about} ${m.aboutName}` }));
    if (m.aboutNotShown) badges.push(h('span', { class: 'v-vis-badge warn', text: W.meta.aboutNotShown(m.aboutNotShown) }));
    for (const intro of m.intents.intros) badges.push(h('span', { class: 'v-vis-badge intro', text: `${W.meta.intro} ${intro.text}` }));
    if (m.intents.points.length) {
      badges.push(h('span', { class: 'v-vis-badge', text: `${W.meta.point} ${m.intents.points.map((p) => p.text).join(', ')}` }));
    }
    for (const rd of m.intents.reads) badges.push(h('span', { class: 'v-vis-badge', text: `${W.meta.read} ${rd.text}` }));
    for (const lb of m.intents.labels) badges.push(h('span', { class: 'v-vis-badge', text: `${W.meta.labels} ${lb}` }));
    for (const nm of m.intents.numbers) badges.push(h('span', { class: 'v-vis-badge', text: `${W.meta.number} ${nm}` }));

    const notFoundBlock = m.show.kind === 'want_none'
      ? h('div', { class: 'v-vis-notfound-box' },
          h('div', null, h('b', { text: W.show.notFoundBadge + ': ' }), m.show.subjectName),
          h('div', { class: 'v-vis-tried' },
            h('span', { class: 'muted', text: W.show.triedLabel }),
            ...(m.show.tried.length
              ? m.show.tried.map((q) => h('span', { class: 'v-vis-tried-item', text: q }))
              : [h('span', { class: 'muted', text: W.show.triedNone })])),
          h('div', { class: 'v-vis-fallback' },
            thumbBox(m.show.fallback?.assetKey || picks?.picks?.main_asset, m.show.fallback?.region || null, 44),
            h('span', null, h('b', { text: W.show.fallbackLabel + ' ' }), m.show.fallback?.label || W.show.whole)))
      : m.show.kind === 'want_open'
        ? h('div', { class: 'v-vis-notfound-box' },
            h('div', null, h('b', { text: W.show.openWantedBadge + ': ' }), m.show.subjectName),
            h('div', { class: 'v-vis-fallback' },
              h('span', null, h('b', { text: W.show.fallbackLabel + ' ' }), m.show.fallback?.label || W.show.whole)))
        : null;

    const headBits = [W.momentNo(idx + 1)];
    if (m.timeText) headBits.push(m.timeText);
    if (m.durText) headBits.push(m.durText);
    if (m.moveLabel) headBits.push(m.moveLabel);

    return h('div', { class: 'v-vis-mom' + (m.show.notFound ? ' not-found' : '') },
      renderShowVisual(m.show),
      h('div', { class: 'v-vis-info' },
        h('div', { class: 'v-vis-mhead', text: headBits.join(' · ') }),
        m.wordsText ? h('div', { class: 'v-vis-mwords', text: `“${m.wordsText}”` }) : null,
        badges.length ? h('div', { class: 'v-vis-badges' }, ...badges) : null,
        notFoundBlock,
        whyText ? h('div', { class: 'v-vis-why' }, h('b', { text: W.meta.why + ' ' }), whyText) : null));
  }

  function renderLine(line) {
    return h('li', { class: 'v-vis-line' + (line.hasNotFound ? ' has-missing' : ''), 'data-line': line.id },
      h('div', { class: 'v-vis-line-head' },
        h('span', { class: 'v-vis-lno', text: W.lineNo(line.number) }),
        line.timeText ? h('span', { class: 'v-vis-ltime mono', text: line.timeText }) : null,
        h('span', { class: 'v-vis-lcount', text: W.lineMoments(line.moments.length) })),
      h('div', { class: 'v-vis-ltext', text: line.text }),
      line.moments.length
        ? h('div', { class: 'v-vis-moments' }, ...line.moments.map((m, i) => renderMoment(m, i)))
        : h('div', { class: 'muted', text: W.noMoments }));
  }

  function renderChapter(ch) {
    const isOpen = !collapsed.has(ch.id);
    return h('section', { class: 'v-vis-chap', 'data-chapter': ch.id },
      h('div', { class: 'v-vis-chhead' },
        h('button', {
          type: 'button',
          class: 'v-vis-chbtn',
          'aria-expanded': String(isOpen),
          title: isOpen ? W.collapse : W.expand,
          onclick: () => { if (collapsed.has(ch.id)) collapsed.delete(ch.id); else collapsed.add(ch.id); paintBody(); },
        }, h('span', { text: isOpen ? '▾' : '▸' }), h('span', { text: ch.title })),
        h('button', {
          type: 'button',
          class: 'small',
          title: W.selectAllHint,
          text: W.selectAll,
          onclick: () => {
            sel = selectChapter(sel, ch.id, ch.lineIds, vm.order);
            paintSelection();
            visualBox.updateScope();
          },
        })),
      h('ul', { class: 'v-vis-lines', hidden: isOpen ? null : true }, ...ch.lines.map(renderLine)));
  }

  function paintTop() {
    if (dead) return;
    const planAct = findStateAction(state, 'visual.plan');
    const approveAct = findStateAction(state, 'picks.approve');
    const cancelAct = findStateAction(state, 'picks.cancel');
    const approved = Boolean(picks?.approved || state?.approvals?.picks);
    const counts = vm?.counts || { moments: 0, borrowed: 0, notFound: 0, topRegions: [] };
    const busyPlan = Boolean(planJobId && (!planJob || ACTIVE.has(planJob.state)));

    const actEls = [];
    if (planAct) {
      const label = busyPlan ? W.actions.planning : (visualDoc ? W.actions.replan : W.actions.plan);
      const hint = !planAct.ready ? needsHint(planAct.needs) : '';
      actEls.push(h('button', {
        type: 'button',
        id: 'vis-plan-btn',
        class: visualDoc ? '' : 'primary',
        text: label,
        title: hint,
        disabled: busyPlan || !planAct.ready ? true : null,
        onclick: () => startPlan(planAct),
      }));
    }
    if (busyPlan && (cancelAct || planJobId)) {
      actEls.push(h('button', { type: 'button', class: 'small', text: W.actions.cancel, onclick: cancelPlan }));
    }
    if (approved) {
      actEls.push(h('span', { class: 'badge ok', id: 'vis-approved', text: W.actions.approved }));
    } else if (approveAct) {
      const hint = !approveAct.ready ? needsHint(approveAct.needs) : '';
      actEls.push(h('button', {
        type: 'button',
        id: 'vis-approve-btn',
        class: approveAct.ready ? 'primary' : 'blocked',
        text: busyApprove ? W.actions.approving : W.actions.approve,
        title: hint,
        disabled: busyApprove || !approveAct.ready ? true : null,
        onclick: () => doApprove(approveAct),
      }));
    }

    const regRow = counts.topRegions.length
      ? h('div', { class: 'v-vis-regions' },
          h('span', { text: W.counts.topRegionsLead }),
          ...counts.topRegions.map((r) => h('span', { class: 'v-vis-regchip', text: W.counts.regionCount(r.name, r.count) })))
      : null;

    const progRow = busyPlan
      ? h('div', { class: 'v-vis-prog', role: 'status' },
          h('progress', { max: 1, value: Number.isFinite(planJob?.progress) ? planJob.progress : 0 }),
          h('span', { text: W.actions.planning }))
      : null;

    topEl.replaceChildren(...kids(
      h('h1', { class: 'v-vis-title', text: W.title }),
      h('span', { class: 'v-vis-project', title: shell?.pipeline?.title || pid, text: shell?.pipeline?.title || pid }),
      h('div', { class: 'v-vis-counts' },
        h('span', { class: 'v-vis-stat', text: W.counts.moments(counts.moments) }),
        h('span', { class: 'v-vis-stat', text: W.counts.borrowed(counts.borrowed) }),
        counts.notFound
          ? h('button', { type: 'button', class: 'v-vis-stat warn', id: 'vis-notfound-btn', text: W.counts.notFound(counts.notFound), onclick: jumpNotFound })
          : h('span', { class: 'v-vis-stat ok', text: W.counts.allFound })),
      h('div', { class: 'v-vis-acts' }, ...actEls),
      regRow,
      progRow));
  }

  function paintBody() {
    if (dead) return;
    bodyEl.dataset.hasBox = visualEditAction(state) ? '1' : '0';
    if (!visualDoc || !vm?.chapters?.length) {
      scrollEl.replaceChildren(h('div', { class: 'v-vis-empty', text: W.empty }));
      return;
    }
    const keep = scrollEl.scrollTop;
    scrollEl.replaceChildren(...vm.chapters.map(renderChapter));
    scrollEl.scrollTop = keep;
    paintSelection();
  }

  function paintSelection() {
    const on = new Set(sel.ids);
    for (const el of scrollEl.querySelectorAll('.v-vis-line')) {
      el.classList.toggle('sel', on.has(el.dataset.line));
    }
  }

  function jumpNotFound() {
    if (!vm?.notFoundLineIds?.length) return;
    const ids = vm.notFoundLineIds;
    const i = lastNotFound ? ids.indexOf(lastNotFound) : -1;
    const target = ids[(i + 1) % ids.length];
    lastNotFound = target;
    for (const ch of vm.chapters) {
      if (ch.lineIds.includes(target) && collapsed.delete(ch.id)) paintBody();
    }
    sel = { ids: [target], anchor: target, chapter: null };
    paintSelection();
    visualBox.updateScope();
    scrollEl.querySelector(`.v-vis-line[data-line="${CSS.escape(target)}"]`)?.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }

  scrollEl.addEventListener('click', (e) => {
    const lineEl = e.target.closest?.('.v-vis-line');
    if (!lineEl || !vm) return;
    sel = applyClick(sel, lineEl.dataset.line, { shift: e.shiftKey, toggle: e.ctrlKey || e.metaKey }, vm.order);
    paintSelection();
    visualBox.updateScope();
  });

  async function startPlan(action) {
    if (planJobId || !action?.ready) return;
    if (visualDoc) {
      const ok = await confirmDialog(W.actions.confirmReplanMsg, { title: W.actions.confirmReplanTitle, ok: W.actions.confirmReplanOk });
      if (!ok) return;
    }
    try {
      const res = await api.send(action.method || 'POST', action.path, action.body || {});
      planJobId = res?.job_id || null;
      planJob = planJobId ? { id: planJobId, state: 'queued', progress: 0 } : null;
      paintTop();
      if (planJobId) pollPlan();
      else await reloadAll();
    } catch (e) {
      toast(W.actions.planFailed + describeError(e).text, 'err', 8000);
    }
  }

  async function cancelPlan() {
    if (!planJobId) return;
    try { await api.post(`/api/longjobs/${encodeURIComponent(planJobId)}/cancel`, {}); } catch { /* ignore */ }
  }

  async function pollPlan() {
    if (dead || !planJobId) return;
    try {
      const j = await api.get(`/api/longjobs/${encodeURIComponent(planJobId)}`);
      if (dead) return;
      planJob = j;
      if (ACTIVE.has(j.state)) {
        paintTop();
        planTimer = setTimeout(pollPlan, 1200);
        return;
      }
      planJobId = null; planJob = null;
      if (j.state === 'done') toast(W.actions.planDone, 'ok');
      else if (j.state === 'cancelled') toast(W.actions.planCancelled, 'warn');
      else toast(W.actions.planFailed + jobErrorText(j).text, 'err', 8000);
      await reloadAll();
      shell?.refreshPipeline?.();
    } catch {
      if (!dead) planTimer = setTimeout(pollPlan, 1500);
    }
  }

  async function doApprove(action) {
    if (busyApprove || !action?.ready) return;
    busyApprove = true; paintTop();
    try {
      await api.send(action.method || 'POST', action.path, action.body || { rev: picks?.rev });
      toast(W.actions.approvedOk, 'ok');
      await reloadAll();
      shell?.refreshPipeline?.();
    } catch (e) {
      toast(describeError(e).text, 'err', 8000);
    } finally {
      busyApprove = false;
      paintTop();
    }
  }

  async function reloadAll() {
    const [p, v, st, w] = await Promise.all([
      api.get(`${P}/picks`).catch(() => picks),
      api.get(`${P}/visual`).catch(() => ({ visual: visualDoc })),
      api.get(`${P}/state`).catch(() => state),
      api.get(`${P}/visual/words`).catch(() => wordsData),
    ]);
    if (dead) return;
    picks = p;
    visualDoc = v?.visual || null;
    state = st;
    wordsData = w;
    vm = buildVisualScriptView({
      visual: visualDoc,
      picks: picks?.picks || null,
      narration: picks?.narration || null,
      words: wordsData?.words || [],
    });
    sel = pruneSelection(sel, vm.order, vm.chapterLines);
    if (!sel.ids.length && vm.order.length) sel = { ids: [vm.order[0]], anchor: vm.order[0], chapter: null };
    visualBox.updateState(state);
    paintTop();
    paintBody();
  }

  scope?.add?.(() => { dead = true; clearTimeout(planTimer); visualBox.unmount(); });

  try {
    wordsData = await api.get(`${P}/visual/words`).catch(() => ({ words: [] }));
  } catch {
    wordsData = { words: [] };
  }
  if (!dead) {
    vm = buildVisualScriptView({
      visual: visualDoc,
      picks: picks?.picks || null,
      narration: picks?.narration || null,
      words: wordsData?.words || [],
    });
    if (!sel.ids.length && vm.order.length) sel = { ids: [vm.order[0]], anchor: vm.order[0], chapter: null };
    const activePlan = (state?.jobs || []).find((j) => j.kind === 'picks' && ACTIVE.has(j.state));
    if (activePlan) { planJobId = activePlan.id; planJob = activePlan; pollPlan(); }
    paintTop();
    paintBody();
  }

  return {
    isDirty: () => false,
    pipelineChanged: () => { reloadAll().catch(() => {}); },
    unmount() { dead = true; clearTimeout(planTimer); visualBox.unmount(); root.remove(); },
  };
}
