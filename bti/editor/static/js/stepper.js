// The stepper across the top: one chip per step of the pipeline. The states come from the server
// (GET /api/projects/{pid}/pipeline); this file only decides how a state looks and what a click does.
import { h } from './util.js';
import { STEP_STATE } from './labels.js';

/** What a step looks like and whether it opens. `active` = the step whose view is open. */
export function stepView(step, { active = false, current = null } = {}) {
  const at = step.id === current;
  const openable = step.state !== 'locked';
  const cls = ['step', 'st-' + step.state, active ? 'active' : '', at ? 'at' : '', openable ? '' : 'disabled'].filter(Boolean).join(' ');
  const state = step.state === 'available' && at ? 'current' : step.state;
  const tag = at && step.state === 'not_built' ? `${STEP_STATE.not_built}, ở đây` : STEP_STATE[state] || state;
  const title = [step.label, step.reason || step.detail].filter(Boolean).join(': ');
  return { cls, openable, tag, title };
}

/** First step after `fromId` that can be opened (everything but locked). null when there is none. */
export function nextOpenable(steps, fromId) {
  const i = steps.findIndex((s) => s.id === fromId);
  return steps.slice(i + 1).find((s) => s.state !== 'locked') || null;
}

/** The step to land on when a project is opened without a step. */
export const landing = (pipeline) => pipeline.current || pipeline.steps.find((s) => s.state !== 'locked')?.id || 'artwork';

export function renderStepper(el, pipeline, activeId, onGo) {
  el.replaceChildren(...pipeline.steps.map((s) => {
    const v = stepView(s, { active: s.id === activeId, current: pipeline.current });
    return h('button', { class: v.cls, type: 'button', title: v.title, 'data-step': s.id, 'aria-disabled': v.openable ? null : 'true', 'aria-current': s.id === activeId ? 'step' : null,
      onclick: () => onGo(s, v) },
      h('span', { class: 'num', text: s.state === 'done' ? '✓' : String(s.n) }),
      h('span', { class: 'lbl' }, h('span', { class: 'nm', text: s.label }), h('span', { class: 'tg', text: v.tag })));
  }));
}
