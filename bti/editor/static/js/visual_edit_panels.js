// Visual tabs added to Step 5 ("Dựng hình") for projects on the visual path:
// 1. Composed shots (existing sbsimple list with each shot's moment words)
// 2. Composer's notes in plain Vietnamese sentences grouped by kind
// 3. Quality scorecard table + contact sheets (same formatting as views/export.js)
// 4. Viewer review remaining findings
import { api } from './api.js';
import { h, kids, toast } from './util.js';
import { describeError } from './errmsg.js';
import { SCORECARD_LABELS, VISUAL_PAGE_LABELS as VL } from './labels.js';
import { scorecardRows, scorecardSummaryText } from './scorecardlogic.js';
import { groupComposeNotes, extractReviewFindings } from './visualedit_logic.js';

function ensureCss() {
  if (document.querySelector('link[data-visual-css]')) return;
  const l = h('link', { rel: 'stylesheet', href: new URL('../css/visual.css', import.meta.url).href });
  l.dataset.visualCss = '1';
  document.head.append(l);
}

export function mountVisualEditPanels({ col, pid, scope, visual = null, storyboard = null, timing = null, issues = [], onSelectShot = null } = {}) {
  ensureCss();
  const W = VL.step5;
  let dead = false, activeTab = 'shots';
  let curSb = storyboard, curIssues = issues, scorecard = null, scorecardBusy = false, reviewReport = null, picksDoc = null;

  const tabsEl = h('div', { class: 've-tabs', role: 'tablist' });
  const shotsHost = h('div', { class: 've-shots-host' });
  const notesPanel = h('div', { class: 've-panel', hidden: true });
  const scorePanel = h('div', { class: 've-panel', hidden: true });
  const reviewPanel = h('div', { class: 've-panel', hidden: true });

  // Move any existing simple shot list elements into shotsHost, or prepare the container
  while (col.firstChild) shotsHost.append(col.firstChild);
  col.append(tabsEl, shotsHost, notesPanel, scorePanel, reviewPanel);

  const P = `/api/projects/${encodeURIComponent(pid)}`;

  function setTab(k) {
    activeTab = k;
    shotsHost.hidden = k !== 'shots';
    notesPanel.hidden = k !== 'notes';
    scorePanel.hidden = k !== 'scorecard';
    reviewPanel.hidden = k !== 'review';
    renderTabs();
  }

  function currentNotes() {
    return groupComposeNotes(curSb?.compose_notes || [], {
      visual,
      storyboard: curSb,
      narration: picksDoc?.narration || null,
      timingBeats: timing?.beats || [],
    });
  }

  function currentFindings() {
    return extractReviewFindings({
      issues: curIssues,
      reviewReport,
      shots: curSb?.shots || [],
    });
  }

  function renderTabs() {
    if (dead) return;
    const notesGroups = currentNotes();
    const notesTotal = notesGroups.reduce((sum, g) => sum + g.items.length, 0);
    const findings = currentFindings();
    const sc = scorecard?.scorecard;
    const scSummary = sc?.summary ? `${sc.summary.passed || 0}/${(sc.summary.passed || 0) + (sc.summary.failed || 0)}` : '';
    const defs = [
      ['shots', W.tabs.shots((curSb?.shots || []).length)],
      ['notes', W.tabs.notes(notesTotal)],
      ['scorecard', W.tabs.scorecard(scSummary)],
      ['review', W.tabs.review(findings.length)],
    ];
    tabsEl.replaceChildren(...defs.map(([k, label]) => h('button', {
      type: 'button',
      role: 'tab',
      'aria-selected': String(activeTab === k),
      class: 've-tab' + (activeTab === k ? ' on' : ''),
      'data-vtab': k,
      text: label,
      onclick: () => setTab(k),
    })));
  }

  function renderNotes() {
    if (dead) return;
    const groups = currentNotes();
    notesPanel.replaceChildren(...kids(
      h('h3', { text: W.notesTitle }),
      h('div', { class: 'muted', text: W.notesHint }),
      groups.length
        ? h('div', { class: 've-notes-groups' }, ...groups.map((g) => h('div', { class: 've-note-group' },
            h('h4', { text: g.title }),
            h('ul', { class: 've-note-list' }, ...g.items.map((it) => h('li', { class: 've-note-item' },
              h('span', { text: it.sentence }),
              it.shotId ? h('button', { type: 'button', class: 'small', text: W.jumpShot, onclick: () => { setTab('shots'); onSelectShot?.(it.shotId); } }) : null))))))
        : h('div', { class: 'muted', text: W.notesEmpty })));
  }

  async function makeScorecard() {
    if (scorecardBusy || dead) return;
    scorecardBusy = true; renderScorecard();
    try {
      scorecard = await api.post(`${P}/scorecard/make`, {});
      toast(SCORECARD_LABELS.doneToast, 'ok');
    } catch (e) {
      toast(describeError(e).text, 'err', 9000);
    } finally {
      if (!dead) { scorecardBusy = false; renderScorecard(); renderTabs(); }
    }
  }

  function renderScorecard() {
    if (dead) return;
    const data = scorecard;
    if (!data) {
      scorePanel.replaceChildren(h('div', { class: 'muted', text: SCORECARD_LABELS.empty }));
      return;
    }
    const sc = data.scorecard;
    const rows = sc ? scorecardRows(sc) : [];
    const sheets = data.sheets || [];
    const btnText = scorecardBusy ? SCORECARD_LABELS.making : (data.exists ? SCORECARD_LABELS.remake : SCORECARD_LABELS.make);
    scorePanel.replaceChildren(...kids(
      h('div', { class: 'ex-score-head' },
        h('h3', { text: SCORECARD_LABELS.title }),
        h('button', { type: 'button', id: 've-scorecard-make', text: btnText, disabled: scorecardBusy || !data.ready ? true : null, onclick: makeScorecard })),
      data.stale ? h('div', { class: 'hint warn', text: SCORECARD_LABELS.stale }) : null,
      !data.ready && !data.exists ? h('div', { class: 'muted', text: SCORECARD_LABELS.notReady }) : null,
      sc ? h('div', { class: 'muted', text: scorecardSummaryText(sc) })
        : (data.ready ? h('div', { class: 'muted', text: SCORECARD_LABELS.empty }) : null),
      rows.length ? h('table', { class: 'ex-card ex-scorecard' },
        h('thead', null, h('tr', null,
          h('th', { text: SCORECARD_LABELS.col.metric }),
          h('th', { text: SCORECARD_LABELS.col.value }),
          h('th', { text: SCORECARD_LABELS.col.target }),
          h('th', { text: SCORECARD_LABELS.col.status }))),
        h('tbody', null, ...rows.map((r) => h('tr', { class: 'sc-' + r.status },
          h('th', null, h('div', { text: r.label }), r.detail ? h('div', { class: 'muted ex-score-detail', text: r.detail }) : null),
          h('td', { text: r.valueText }),
          h('td', { class: 'muted', text: r.targetText }),
          h('td', null, h('span', { class: 'badge ' + r.status, text: r.statusText })))))) : null,
      sheets.length ? h('div', null,
        h('h3', { text: SCORECARD_LABELS.sheetsTitle }),
        h('div', { class: 'muted', text: SCORECARD_LABELS.sheetsHint }),
        h('div', { class: 'ex-sheets' }, ...sheets.map((sh, i) => {
          const href = api.url(sh.url);
          const cap = SCORECARD_LABELS.sheetTile(i + 1, sh.shots?.[0], sh.shots?.[1]);
          return h('a', { class: 'ex-sheet', href, target: '_blank', rel: 'noopener', title: cap },
            h('img', { src: href, loading: 'lazy', alt: cap }),
            h('span', { text: cap }));
        }))) : null));
  }

  function renderReview() {
    if (dead) return;
    const findings = currentFindings();
    const rounds = reviewReport?.rounds;
    reviewPanel.replaceChildren(...kids(
      h('h3', { text: W.reviewTitle }),
      Number.isFinite(rounds) ? h('div', { class: 'muted', text: W.reviewRounds(rounds) }) : null,
      findings.length
        ? h('ul', { class: 've-review-list' }, ...findings.map((f) => h('li', { class: 've-review-item' },
            h('span', { text: f.text }),
            f.shotId ? h('button', { type: 'button', class: 'small', text: W.jumpShot, onclick: () => { setTab('shots'); onSelectShot?.(f.shotId); } }) : null)))
        : h('div', { class: 'muted', text: reviewReport ? W.reviewEmpty : W.reviewNotRun })));
  }

  function renderAll() {
    renderTabs();
    renderNotes();
    renderScorecard();
    renderReview();
  }

  async function loadExtras() {
    const [sc, th, pk] = await Promise.all([
      api.get(`${P}/scorecard`).catch(() => null),
      api.get(`${P}/draft/thread`).catch(() => null),
      api.get(`${P}/picks`).catch(() => null),
    ]);
    if (dead) return;
    scorecard = sc;
    reviewReport = th?.review || null;
    picksDoc = pk;
    renderAll();
  }

  scope?.add?.(() => { dead = true; });
  renderAll();
  loadExtras();

  return {
    shotsHost,
    refresh({ storyboard: nextSb = curSb, issues: nextIssues = curIssues } = {}) {
      curSb = nextSb;
      curIssues = nextIssues;
      loadExtras();
    },
    setTab,
    unmount() { dead = true; },
  };
}
