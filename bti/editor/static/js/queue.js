// A queue that runs async jobs one after another. Everything that changes a draft on the server goes through ONE
// queue, so a request is never sent before the previous answer has updated the revision it depends on.
// A job that throws rejects its own promise only; the queue keeps going.
export function createQueue({ onBusy } = {}) {
  let tail = Promise.resolve(), pending = 0;
  const q = {
    get pending() { return pending; },
    get busy() { return pending > 0; },
    /** Run fn() after everything queued before it. Resolves/rejects with fn's result. */
    run(fn) {
      pending++; if (pending === 1) onBusy?.(true);
      const p = tail.then(() => fn());
      tail = p.then(() => {}, () => {}).then(() => { pending--; if (pending === 0) onBusy?.(false); });
      return p;
    },
    /** Resolves when everything queued so far has finished. */
    idle() { return tail; },
  };
  return q;
}
