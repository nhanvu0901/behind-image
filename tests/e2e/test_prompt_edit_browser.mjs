// E2E Browser Test for Prompt-based Video Editing (Section 7.4)
// Run: node tests/e2e/test_prompt_edit_browser.mjs [--base http://127.0.0.1:8565]
import { launchChrome, sleep } from './shell_library_script/lib.mjs';
import fs from 'node:fs';

const args = process.argv.slice(2);
let base = 'http://127.0.0.1:8565';
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--base' && args[i + 1]) {
    base = args[++i];
  }
}

const fakeFetchScript = `(() => {
  const origFetch = window.fetch;

  window.__resetFixture = () => {
    localStorage.removeItem('__interceptedCalls');
    localStorage.removeItem('__fixtureState');
  };

  window.__setFixture = (obj) => {
    const cur = JSON.parse(localStorage.getItem('__fixtureState') || '{}');
    const next = { ...cur, ...obj };
    localStorage.setItem('__fixtureState', JSON.stringify(next));
  };

  window.__getFixture = () => {
    return JSON.parse(localStorage.getItem('__fixtureState') || '{}');
  };

  window.__getIntercepted = () => {
    return JSON.parse(localStorage.getItem('__interceptedCalls') || '[]');
  };

  window.fetch = async function(url, opts = {}) {
    const u = typeof url === 'string' ? url : (url.url || String(url));
    const method = (opts.method || 'GET').toUpperCase();
    const fix = JSON.parse(localStorage.getItem('__fixtureState') || '{}');

    // 1. POST /api/projects/:pid/draft/edit
    if (u.match(/\\/api\\/projects\\/[^/]+\\/draft\\/edit(\\?|$)/) && method === 'POST') {
      const body = opts.body ? JSON.parse(opts.body) : {};
      const calls = JSON.parse(localStorage.getItem('__interceptedCalls') || '[]');
      calls.push({ type: 'edit_submit', url: u, method, body, time: Date.now() });
      localStorage.setItem('__interceptedCalls', JSON.stringify(calls));

      const jobId = fix.nextJobId || ('fake_job_' + Date.now().toString(16));
      const turnId = fix.nextTurnId || ('turn_' + Date.now().toString(16));

      const isTerminal = fix.terminalImmediately !== false;
      const thread = fix.thread || [];
      thread.push({
        id: turnId,
        at: new Date().toISOString(),
        instruction: body.instruction,
        scope: body.scope,
        scope_words: body.scope?.shots ? (body.scope.shots.length + ' shot đang chọn') : (body.scope?.chapter || 'cả video'),
        model: body.model || 'gemini-3.8-flash',
        base_rev: body.base_rev,
        status: isTerminal ? 'done' : 'running',
        job_id: jobId,
        proposal_id: isTerminal ? 'prop_fake_001' : null,
        notes: '',
        error: null,
      });
      fix.thread = thread;
      fix.activeJobId = isTerminal ? null : jobId;
      if (!fix.jobs) fix.jobs = {};
      fix.jobs[jobId] = {
        id: jobId,
        state: isTerminal ? 'done' : 'running',
        progress: isTerminal ? 1.0 : 0.5,
        result: isTerminal ? { proposal_id: 'prop_fake_001' } : null,
        meta: { mode: 'edit' }
      };
      localStorage.setItem('__fixtureState', JSON.stringify(fix));

      return new Response(JSON.stringify({ job_id: jobId, turn_id: turnId }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // 2. GET /api/projects/:pid/draft/thread
    if (u.match(/\\/api\\/projects\\/[^/]+\\/draft\\/thread(\\?|$)/) && method === 'GET') {
      const thread = fix.thread || [];
      const activeJobId = fix.activeJobId || null;
      return new Response(JSON.stringify({ turns: thread, active_job_id: activeJobId }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // 3. DELETE /api/projects/:pid/draft/thread
    if (u.match(/\\/api\\/projects\\/[^/]+\\/draft\\/thread(\\?|$)/) && method === 'DELETE') {
      if (fix.activeJobId) {
        return new Response(JSON.stringify({ code: 'busy', message: 'a draft is already running' }), {
          status: 409,
          headers: { 'Content-Type': 'application/json' }
        });
      }
      fix.thread = [];
      localStorage.setItem('__fixtureState', JSON.stringify(fix));
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // 4. GET /api/longjobs/:jid
    if (u.match(/\\/api\\/longjobs\\/([^/?]+)(\\?|$)/) && !u.includes('/cancel') && method === 'GET') {
      const m = u.match(/\\/api\\/longjobs\\/([^/?]+)(\\?|$)/);
      const jid = m ? m[1] : '';
      const job = (fix.jobs && fix.jobs[jid]) || {
        id: jid,
        state: fix.jobState || 'done',
        progress: 1.0,
        result: { proposal_id: 'prop_fake_001' },
        meta: { mode: 'edit' }
      };
      return new Response(JSON.stringify(job), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // 5. POST /api/longjobs/:jid/cancel
    if (u.match(/\\/api\\/longjobs\\/([^/?]+)\\/cancel(\\?|$)/) && method === 'POST') {
      const m = u.match(/\\/api\\/longjobs\\/([^/?]+)\\/cancel(\\?|$)/);
      const jid = m ? m[1] : '';
      const calls = JSON.parse(localStorage.getItem('__interceptedCalls') || '[]');
      calls.push({ type: 'job_cancel', url: u, method, jid, time: Date.now() });
      localStorage.setItem('__interceptedCalls', JSON.stringify(calls));

      if (!fix.jobs) fix.jobs = {};
      fix.jobs[jid] = { id: jid, state: 'cancelled' };
      (fix.thread || []).forEach(t => {
        if (t.job_id === jid) {
          t.status = 'error';
          t.error = 'cancelled';
        }
      });
      fix.activeJobId = null;
      localStorage.setItem('__fixtureState', JSON.stringify(fix));

      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // Storyboard save tracking
    if (u.match(/\\/api\\/projects\\/[^/]+\\/storyboard(\\?|$)/) && (method === 'PUT' || method === 'POST')) {
      const calls = JSON.parse(localStorage.getItem('__interceptedCalls') || '[]');
      calls.push({ type: 'storyboard_save', url: u, method, time: Date.now() });
      localStorage.setItem('__interceptedCalls', JSON.stringify(calls));
    }

    return origFetch.apply(this, arguments);
  };
})();`;

async function main() {
  console.log('== Starting Prompt Edit Browser E2E Test against:', base, '==');
  const br = await launchChrome({ width: 1700, height: 1000 });
  const page = await br.newPage();

  let failed = 0;
  const testResults = [];

  const check = async (id, title, fn) => {
    let ok = false, note = '';
    try {
      const r = await fn();
      ok = r === true;
      note = ok ? '' : String(r);
    } catch (e) {
      note = 'ERROR: ' + String(e.message || e).slice(0, 300);
    }
    const line = `${ok ? 'PASS' : 'FAIL'} [${id}] ${title}${note ? ' -> ' + note : ''}`;
    console.log(line);
    testResults.push(line);
    if (!ok) failed++;
  };

  try {
    // Add fake fetch script to run on all documents and survive reloads
    await page.send('Page.addScriptToEvaluateOnNewDocument', { source: fakeFetchScript });

    const editUrl = `${base}/#/project/arnolfini/edit`;
    console.log('== Navigating to', editUrl, '==');
    await page.goto(editUrl, 2500);

    // Wait for store, storyboard draft and prompt edit container to mount
    for (let i = 0; i < 40; i++) {
      const ready = await page.eval(`(() => {
        const pe = document.querySelector('.prompt-edit');
        const st = window.__bti?.store;
        const ta = document.querySelector('.prompt-instruction');
        return !!(pe && st && st.draft && st.draft.shots?.length && ta);
      })()`).catch(() => false);
      if (ready) break;
      await sleep(300);
    }

    // Reset fixture
    await page.eval(`window.__resetFixture()`);

    // =========================================================================
    // Check 1: Multi-shot selection through panel controls & POST payload
    // =========================================================================
    await check('R7-01', 'select two unlocked shots through panel controls, enter prompt, assert captured POST payload', async () => {
      await page.eval(`window.__setFixture({ terminalImmediately: true })`);

      // Ensure scope is 'shots'
      await page.eval(`(() => {
        const scopeSel = document.querySelector('.prompt-scope');
        if (scopeSel && scopeSel.value !== 'shots') {
          scopeSel.value = 'shots';
          scopeSel.dispatchEvent(new Event('change', { bubbles: true }));
        }
      })()`);
      await sleep(200);

      // Inspect available unlocked shots from store.draft.shots
      const shotInfo = await page.eval(`(() => {
        const st = window.__bti.store;
        const allShots = st.draft?.shots || [];
        const unlocked = allShots.filter(s => !s.locked).map(s => s.id);
        return { unlocked, total: allShots.length };
      })()`);

      if (shotInfo.unlocked.length < 2) {
        return `Not enough unlocked shots in project: ${JSON.stringify(shotInfo)}`;
      }

      const shot1 = shotInfo.unlocked[0];
      const shot2 = shotInfo.unlocked[1];

      // Select first shot via store
      await page.eval(`window.__bti.store.select(${JSON.stringify(shot1)})`);
      await sleep(200);

      // Select second shot via .prompt-add-shot select dropdown
      const added = await page.eval(`(() => {
        const addSel = document.querySelector('.prompt-add-shot');
        if (!addSel) return false;
        addSel.value = ${JSON.stringify(shot2)};
        addSel.dispatchEvent(new Event('change', { bubbles: true }));
        return true;
      })()`);
      if (!added) return 'Could not find .prompt-add-shot select';
      await sleep(200);

      // Check chips count
      const chipsState = await page.eval(`(() => {
        const chips = Array.from(document.querySelectorAll('.prompt-shot-chip')).map(c => c.textContent.trim());
        return { chips, count: chips.length };
      })()`);

      if (chipsState.count < 2) {
        return `Expected at least 2 chips, found: ${JSON.stringify(chipsState)}`;
      }

      // Enter prompt text
      const promptText = 'Làm mượt chuyển cảnh giữa hai shot này và giảm rung';
      await page.eval(`(() => {
        const ta = document.querySelector('.prompt-instruction');
        ta.value = ${JSON.stringify(promptText)};
        ta.dispatchEvent(new Event('input', { bubbles: true }));
      })()`);
      await sleep(200);

      // Click send button
      await page.click('.prompt-btn-submit');
      await sleep(500);

      // Verify captured POST call
      const captured = await page.eval(`window.__getIntercepted()`);
      const editCall = captured.find((c) => c.type === 'edit_submit');
      if (!editCall) return 'No edit_submit call was intercepted';

      const body = editCall.body;
      if (body.instruction !== promptText) {
        return `Instruction mismatch: expected "${promptText}", got "${body.instruction}"`;
      }
      if (!body.scope?.shots || !Array.isArray(body.scope.shots)) {
        return `Scope shots missing or not array: ${JSON.stringify(body.scope)}`;
      }
      if (!body.scope.shots.includes(shot1) || !body.scope.shots.includes(shot2)) {
        return `Selected shots ${shot1}, ${shot2} not in payload: ${JSON.stringify(body.scope.shots)}`;
      }
      if (typeof body.base_rev !== 'string' || !body.base_rev) {
        return `base_rev missing in payload: ${JSON.stringify(body)}`;
      }

      return true;
    });

    // =========================================================================
    // Check 2: Chapter scope with missing legacy ID fallback (c01/c02) & All scope
    // =========================================================================
    await check('R7-02', 'chapter scope normalizes missing id to c01/c02 derived from index; all scope sends {all: true}', async () => {
      await page.eval(`window.__resetFixture(); window.__setFixture({ terminalImmediately: true })`);

      // 1. Wait for submit button to be active
      for (let i = 0; i < 20; i++) {
        const ready = await page.eval(`(() => {
          const btn = document.querySelector('.prompt-btn-submit');
          return btn && !btn.disabled;
        })()`);
        if (ready) break;
        await sleep(150);
      }

      // Switch scope to 'chapter'
      await page.eval(`(() => {
        const scopeSel = document.querySelector('.prompt-scope');
        scopeSel.value = 'chapter';
        scopeSel.dispatchEvent(new Event('change', { bubbles: true }));
      })()`);
      await sleep(200);

      // Send prompt for chapter
      await page.eval(`(() => {
        const ta = document.querySelector('.prompt-instruction');
        ta.value = 'Sửa nhịp điệu chương';
        ta.dispatchEvent(new Event('input', { bubbles: true }));
      })()`);
      await sleep(150);

      await page.click('.prompt-btn-submit');
      await sleep(400);

      let captured = await page.eval(`window.__getIntercepted()`);
      let editCall = captured.filter((c) => c.type === 'edit_submit').pop();
      if (!editCall) return 'No chapter edit call captured';

      // Assert normalized ID is 'c01' (derived from index 0 of timing.chapters, NEVER chapter name 'COLD_OPEN')
      if (editCall.body.scope?.chapter !== 'c01') {
        return `Chapter ID was not normalized to c01: ${JSON.stringify(editCall.body.scope)}`;
      }

      // Wait for submit button to re-enable
      for (let i = 0; i < 20; i++) {
        const ready = await page.eval(`(() => {
          const btn = document.querySelector('.prompt-btn-submit');
          return btn && !btn.disabled;
        })()`);
        if (ready) break;
        await sleep(150);
      }

      // 2. Switch scope to 'all'
      await page.eval(`(() => {
        const scopeSel = document.querySelector('.prompt-scope');
        scopeSel.value = 'all';
        scopeSel.dispatchEvent(new Event('change', { bubbles: true }));
      })()`);
      await sleep(200);

      await page.eval(`(() => {
        const ta = document.querySelector('.prompt-instruction');
        ta.value = 'Sửa toàn bộ video';
        ta.dispatchEvent(new Event('input', { bubbles: true }));
      })()`);
      await sleep(150);

      await page.click('.prompt-btn-submit');
      await sleep(400);

      captured = await page.eval(`window.__getIntercepted()`);
      editCall = captured.filter((c) => c.type === 'edit_submit').pop();
      if (!editCall) return 'No all-scope edit call captured';

      if (!editCall.body.scope?.all) {
        return `Expected scope { all: true }, got: ${JSON.stringify(editCall.body.scope)}`;
      }

      return true;
    });

    // =========================================================================
    // Check 3: Unsaved draft changes prompt save dialog and update base_rev
    // =========================================================================
    await check('R7-03', 'unsaved changes trigger confirmation dialog, save executes before edit POST with updated rev', async () => {
      await page.eval(`window.__resetFixture(); window.__setFixture({ terminalImmediately: true })`);

      // Make a harmless in-memory commit to mark store dirty/unsaved
      await page.eval(`(() => {
        const st = window.__bti.store;
        st.commit('test_unsaved_marker', (d) => {
          if (d.shots && d.shots[0]) {
            d.shots[0].note = 'e2e_unsaved_marker_' + Date.now();
          }
        });
      })()`);

      const isUnsaved = await page.eval(`window.__bti.store.snap() !== window.__bti.store.savedSnap`);
      if (!isUnsaved) return 'Store was not marked unsaved';

      // Enter prompt
      await page.eval(`(() => {
        const ta = document.querySelector('.prompt-instruction');
        ta.value = 'Sửa shot sau khi đã lưu';
        ta.dispatchEvent(new Event('input', { bubbles: true }));
      })()`);
      await sleep(150);

      // Click submit -> Confirmation modal should pop up
      await page.click('.prompt-btn-submit');
      await sleep(350);

      // Check if modal dialog appeared
      const hasDialog = await page.eval(`(() => {
        const dlg = document.querySelector('.modal.ask');
        return !!dlg;
      })()`);
      if (!hasDialog) return 'Confirmation dialog did not appear for unsaved draft';

      // Click primary button ("Lưu và tiếp tục")
      await page.click('.modal.ask footer button.primary');
      await sleep(800);

      // Verify call sequence: save happened before edit
      const calls = await page.eval(`window.__getIntercepted()`);
      const saveIdx = calls.findIndex((c) => c.type === 'storyboard_save');
      const editIdx = calls.findIndex((c) => c.type === 'edit_submit');

      if (saveIdx === -1) return 'Storyboard save was not executed';
      if (editIdx === -1) return 'Edit POST was not executed';
      if (saveIdx > editIdx) return `Save (idx ${saveIdx}) did not happen before edit (idx ${editIdx})`;

      const editCall = calls[editIdx];
      if (typeof editCall.body.base_rev !== 'string' || !editCall.body.base_rev) {
        return `Resulting base_rev missing in edit call: ${JSON.stringify(editCall.body)}`;
      }

      return true;
    });

    // =========================================================================
    // Check 4: Running edit fixture, reload page, progress & cancel
    // =========================================================================
    await check('R7-04', 'active running edit reconnects on reload, displays progress and cancel button, click cancel terminates', async () => {
      const activeJobId = 'job_running_fixture_99';
      await page.eval(`(() => {
        window.__resetFixture();
        window.__setFixture({
          terminalImmediately: false,
          activeJobId: ${JSON.stringify(activeJobId)},
          thread: [{
            id: 'turn_active_01',
            at: new Date().toISOString(),
            instruction: 'Yêu cầu đang chạy dở dang',
            scope: { kind: 'all' },
            scope_words: 'cả video',
            model: 'gemini-3.8-flash',
            base_rev: 'rev_active_01',
            status: 'running',
            job_id: ${JSON.stringify(activeJobId)},
            proposal_id: null,
            notes: '',
            error: null
          }],
          jobs: {
            ${activeJobId}: {
              id: ${JSON.stringify(activeJobId)},
              state: 'running',
              progress: 0.45,
              meta: { mode: 'edit' }
            }
          }
        });
      })()`);

      // Reload page via Page.reload to test reconnection
      await page.send('Page.reload');
      await sleep(1500);
      await page.idle();

      // Wait for prompt edit and check cancel button
      let foundCancel = false;
      for (let i = 0; i < 30; i++) {
        const hasCancel = await page.eval(`(() => {
          const btn = document.querySelector('.prompt-btn-cancel');
          return btn && btn.offsetWidth > 0;
        })()`).catch(() => false);
        if (hasCancel) {
          foundCancel = true;
          break;
        }
        await sleep(200);
      }

      if (!foundCancel) {
        const domDump = await page.eval(`(() => {
          const box = document.querySelector('.prompt-progress-container');
          return box ? box.innerHTML : 'no box';
        })()`);
        return `Reconnection failed, cancel button not visible after reload. Progress container HTML: ${domDump}`;
      }

      // Click cancel button
      await page.click('.prompt-btn-cancel');
      await sleep(600);

      // Check intercepted cancel call
      const calls = await page.eval(`window.__getIntercepted()`);
      const cancelCall = calls.find((c) => c.type === 'job_cancel');
      if (!cancelCall) return 'Job cancel POST was not intercepted';
      if (cancelCall.jid !== activeJobId) {
        return `Cancel called with wrong jid: expected ${activeJobId}, got ${cancelCall.jid}`;
      }

      // Thread reconciles: badge becomes "Đã hủy"
      const threadBadge = await page.eval(`(() => {
        const badge = document.querySelector('.prompt-turn-card .chip');
        return badge ? badge.textContent.trim() : null;
      })()`);

      if (!threadBadge || !threadBadge.includes('Đã hủy')) {
        return `Turn badge after cancel expected 'Đã hủy', got: '${threadBadge}'`;
      }

      return true;
    });

    // =========================================================================
    // Check 5: Text preservation across updates and clean unmount
    // =========================================================================
    await check('R7-05', 'textarea preserves text across scope/thread updates, clean unmount on navigation', async () => {
      const sampleText = 'Văn bản bảo toàn nguyên vẹn khi đổi phạm vi';
      await page.eval(`(() => {
        const ta = document.querySelector('.prompt-instruction');
        ta.value = ${JSON.stringify(sampleText)};
        ta.dispatchEvent(new Event('input', { bubbles: true }));
      })()`);
      await sleep(150);

      // Switch scope back and forth
      await page.eval(`(() => {
        const scopeSel = document.querySelector('.prompt-scope');
        scopeSel.value = 'all';
        scopeSel.dispatchEvent(new Event('change', { bubbles: true }));
        scopeSel.value = 'shots';
        scopeSel.dispatchEvent(new Event('change', { bubbles: true }));
      })()`);
      await sleep(200);

      const taVal = await page.eval(`document.querySelector('.prompt-instruction').value`);
      if (taVal !== sampleText) {
        return `Textarea lost value: expected "${sampleText}", got "${taVal}"`;
      }

      // Navigate away to test clean unmount
      await page.goto(`${base}/#/library`, 1500);
      await sleep(300);

      const peAfterNav = await page.eval(`document.querySelector('.prompt-edit')`);
      if (peAfterNav !== null) {
        return 'Prompt edit panel was not cleanly unmounted on navigation';
      }

      // Return to edit view for screenshots
      await page.goto(editUrl, 2000);
      for (let i = 0; i < 40; i++) {
        const ready = await page.eval(`(() => {
          const pe = document.querySelector('.prompt-edit');
          const stage = document.querySelector('#stage');
          const btn = document.querySelector('.prompt-btn-submit');
          return pe && stage && btn && btn.offsetWidth > 0;
        })()`).catch(() => false);
        if (ready) break;
        await sleep(200);
      }
      return true;
    });

    // =========================================================================
    // Screenshots at 1700x1000 and 1280x720
    // =========================================================================
    console.log('== Capturing required responsive screenshots ==');
    // 1700x1000
    const shot1 = '/tmp/prompt-edit-ui-1700x1000.png';
    await page.shot(shot1);
    console.log('Screenshot 1700x1000 saved to:', shot1, 'size:', fs.statSync(shot1).size);

    // 1280x720
    await page.resize(1280, 720);
    await sleep(500);

    const dims720 = await page.eval(`(() => {
      const stage = document.querySelector('#stage');
      const btn = document.querySelector('.prompt-btn-submit');
      return {
        stageH: Math.round(stage?.getBoundingClientRect().height || 0),
        stageW: Math.round(stage?.getBoundingClientRect().width || 0),
        btnVisible: btn ? (btn.offsetWidth > 0 && btn.offsetHeight > 0) : false
      };
    })()`);

    console.log('DOM metrics at 1280x720:', JSON.stringify(dims720));
    if (dims720.stageH < 120) {
      console.warn(`WARNING: #stage height at 1280x720 is ${dims720.stageH}px (< 120px)`);
    }

    const shot2 = '/tmp/prompt-edit-ui-1280x720.png';
    await page.shot(shot2);
    console.log('Screenshot 1280x720 saved to:', shot2, 'size:', fs.statSync(shot2).size);

  } catch (err) {
    console.error('Fatal Browser E2E Error:', err);
    failed++;
  } finally {
    br.close();
  }

  console.log('\n======================================================');
  console.log(`E2E BROWSER TEST SUMMARY: ${testResults.length - failed} PASSED, ${failed} FAILED`);
  console.log('======================================================');
  if (failed > 0) {
    process.exit(1);
  }
}

main();
