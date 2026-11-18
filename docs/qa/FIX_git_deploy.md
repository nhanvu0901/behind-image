# FIX_git_deploy: deploy by git (push, then fast-forward on the server)

## Files
- `tools/deploy/git_deploy.sh` (new, Mac): `[--restart] [--check]`. Refuses (exit 2, nothing pushed) on uncommitted tracked changes, no upstream, an upstream with another name, detached HEAD. Without `--check`: `git push <remote> refs/heads/<branch>:refs/heads/<branch>` (never forced, no tags). Copies `git_update.ps1` to `_deploy\git_update-<id>.ps1`, runs it with `-Root -Branch -Commit [-Restart] [-Check]`, passes its exit code on.
- `tools/deploy/git_update.ps1` (new, server): lock, fetch, refusals (exit 30 no .git, 31 wrong branch, 32 tracked files modified, 33 not fast-forward, 34 fetch failed / branch missing), incoming report, `-Check` stop, optional stop, `merge --ff-only`, venv step, optional start, `run\last_deploy.txt`. Exit 36 when the server ends on another commit than `-Commit`; 11 for any other failure; 20 lock timeout. An app it stopped is always started again in `finally`.
- `tools/deploy/deploy_windows.sh`: guard (refuses with exit 3 when the server folder has `.git`, or when it cannot tell; not for `--pack-only`, `--data-only`, `--force-tar`); new `--data-only` (empty code archive plus data archive, because `remote_update.ps1` always unpacks a code archive) and `--force-tar`; header updated.
- `docs/WINDOWS.md`: command rows and the paragraphs under them replaced. `docs/APP_GUIDE.md` does not name the deploy: unchanged. `remote_test.sh` untouched (marked retired in the docs).

## Bug found and fixed while testing (important)
My first version had a helper `function Git { & git ... }`. PowerShell names are case-insensitive, so `git` called the function itself: endless recursion, the powershell process grew to about 13 GB (and a second one to about 2.8 GB) on the production server before I killed both (`taskkill` on exactly those two pids, which I had checked to be my `git_update-gdtest-*.ps1` runs). The app on 8560 kept listening, free memory went back to about 22 GB. The helper is now `GitR` calling `git.exe`, with a comment. No other test run had this problem.

## Checks
- `bash -n` on both shell scripts: ok. PowerShell parser on the server: 0 errors (the first parse found `$remoteRef:` inside a string; fixed with `${remoteRef}:`).
- Six cases on the throwaway clone `D:\code\behind-the-image\run\gitdeploy-test` (deleted afterwards, with my temporary scripts in `_deploy`): see the final report of the worker for the printed outputs; summary: wrong branch exit 31, `-Check` exit 0 (25 files incoming, 15 app files, nothing changed), locally modified file exit 32 (listed `M tools/deploy/lib.sh`), local commit exit 33, nothing incoming exit 0, fast-forward with `-Commit` exit 0 and `last_deploy.txt` = `id=git-f19062d ... data=False`.
- A stale `deploy.lock` left by a killed run made the next run print `waiting for deploy.lock (...)` every 5 s and continue the moment the lock was removed: lock waiting works.
- `git_deploy.sh --check` on the real folder (run from a clean clone of the Mac repo at `f19062d`, because the Mac tree has `deploy_windows.sh` modified): `server HEAD: f19062d  origin/build/pipeline: f19062d  incoming files: 0`, exit 0. On the Mac checkout itself it correctly refuses (modified tracked file), exit 2.
- Guard: `deploy_windows.sh` on the real folder and on the clone: `REFUSED ... git checkout`, exit 3, before anything is packed or copied. `--pack-only` still works (1009 files, 8.7 MB). `--data-only --pack-only` packs an empty code archive plus the data archive.

## Not tested
- Every `-Restart` line of `git_update.ps1` (stop_app/start_app calls, the `$stopped` recovery in `finally`, the "THE APP IS DOWN" message). Note `stop_app.ps1` and `start_app.ps1` have `D:\code\behind-the-image` written in them, they ignore `-Root`.
- The venv step (`-NoVenv` was used on the clone), including a `requirements.txt` change.
- `git_deploy.sh` without `--check` (the push) and with `--restart`; the exit-36 path; the "origin is not the commit asked for" NOTE.
- `deploy_windows.sh --data-only` without `--pack-only` (copy and unpack on the server): an empty `.tgz` was created on the Mac and read by tar there, but the server's `tar -xzf` of the empty archive was not tried.

## Found, not asked for
- `.scratch/deploy/out/code_files.txt` is overwritten by every pack (pre-existing behaviour).
- `deploy_windows.sh --data-only --pack-only` really packs the 700 MB data archive; I deleted the archives I made.
- `remote_test.sh --no-sync` still works on the git checkout (no deploy), only the syncing form is refused by the guard.

## After the worker's report (coordinator, 2026-11-18)
- `git_update.ps1` now checks the exit code of `start_app.ps1` after a deploy with `-Restart`: when the app does not come back it
  prints `THE APP IS DOWN ...` and exits 12 (before, the deploy ended with exit 0). Parsed on the server: 0 errors. Not run for real.
- The server was checked after the runaway test processes: 21.5 GB free, no process left, the app answered in 30 ms, no lock, the
  test clone gone, the checkout clean.
