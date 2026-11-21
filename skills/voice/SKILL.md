---
name: bti-voice
description: Step 3 of Behind the Image, the voice (the approved narration read aloud and timed word by word). Use when `bti status <project>` shows the step `voice` as current.
---

# Step 3: the voice

Read `AGENTS.md` first (the rules, the exit codes). This is the most expensive step of the first half: about an hour of the server's machine time for a 12-minute video.

## Goal

A narration read aloud as one audio file, with the time of every word, so that the storyboard can start a picture on the word that names it.

## What it needs and what it gives

- Needs: the narration approved (gate `narration`) and still matching (a changed narration makes the voice out of date: `voice_done` is unmet).
- Gives: the audio mix and `timing.json` (every word with its start and end). Step 5 reads both; the export mixes the audio into the video.
- Steps 3 and 4 open together: the picture step (`picks`) can be worked while the voice runs.

## The actions it uses

<!-- BEGIN GENERATED: actions -->
| id | step | page button | gate | cost | long job |
|---|---|---|---|---|---|
| `voice.generate` | voice | Tạo giọng đọc |  | machine_time: about 1 hour | yes |
| `voice.cancel` | voice | Dừng |  |  |  |
<!-- END GENERATED: actions -->

`voice.generate` takes `{"scope": "changed"}` (the default: only the sentences that are new or changed) or `{"scope": "all"}` (`--set scope=all`: read everything again). It answers with a
job. The server reads the narration in parts of about 20 minutes, one at a time; a part that waits for the machine says so in the job line. While it runs, `bti job <id> --cancel` stops it:
the sentences already read are kept and the next `voice.generate` goes on from there. Starting a second voice job while one runs is refused (`no_running_job`, exit 5).

## A worked session

Fixture project `arn` (the narration is approved; the voice job here is a stand-in that ends at once, the real one prints a line each time something changes and takes about an hour).

```text
# fixture: book narration_approved
$ bti status arn
project: arn   stage: script   current step: voice (Giọng đọc)
automatic running: off (an agent approves no gate; the owner approves on the page or turns it on there)
approvals: outline human; narration human; picks -; storyboard -
...
next: bti do arn voice.generate --yes-cost --wait   (Tạo giọng đọc)
$ bti do arn voice.generate
a person is needed: cost_not_confirmed
  detail: voice.generate costs machine_time (about 1 hour).
  fix: Run it again with --yes-cost when the owner asked for this work.
(exit 3)
$ bti do arn voice.generate --yes-cost --wait
started job <job> (voice.generate)
...
done: <any>
```

`--yes-cost` is your confirmation that the owner asked for this work and allowed the spending; without it, or when the owner did not allow `machine_time` spending for the project, the command stops with exit 3 and
sends nothing. If your harness cuts a command short, start without `--wait` and follow with `bti job <id> --wait` (add `--max-wait 600` to come back every ten minutes: exit 5 means "still running").

## What a good result is

- The step is `done` in `bti status` and `voice.generate` is no longer the advancing action; `timing.json` exists (a project without it is repaired by `voice.generate`).
- Numbers, years, centuries, money, percentages, abbreviations and Roman numerals are spoken as words by the server. A proper name that is read wrongly is the owner's to fix in the pronunciation table on the page; tell the owner which word.
- No subtitle is drawn into the picture at any step: the voice step puts no text on the screen.
- **Two silences are the project's own** (`PUT /api/projects/{pid}/voice/settings`): `lead`, the silence before the first word (0.2 to 15 s), and `title`, the silence that holds the channel-name beat (3 to 30 s). A project the app creates has 5.0 and 10.2 s (the whole painting is shown before the first word, then the channel name with the video's title); an older project keeps 0.35 and 6.2 s until the owner asks for the new opening. `GET .../voice` shows the values in force and whether they are the project's own (`silence`). Changing either makes the voice `stale` (`mix_settings_changed`); `voice.generate` with scope `changed` then only assembles and aligns again (a few minutes, no sentence is spoken again) and every word moves later.
- **After the voice was made again, fit the storyboard to it.** The cards, the channel-name beat and the end of the video of an existing storyboard are anchored by absolute time and do not move with the words: `bti status` lists `storyboard.retime` ("Khớp lại với giọng đọc") as the next command; run `bti do <project> storyboard.retime` (step 5, `skills/storyboard/SKILL.md`). Approving the storyboard and the export are refused (`storyboard_off_voice`) until it is done. This holds after a single sentence read again too.
- If the machine has no word aligner the word times are spread evenly inside each sentence (the page says so): the start and end of a sentence are exact, the words in between are not. Say so to the owner before step 5.

## The refusals you will meet

| code | what to do |
|---|---|
| `narration_not_approved`, `narration_missing` | Approve the narration first (step 2). |
| `no_running_job`, `voice_busy` (exit 5) | A voice job already runs: `bti job <id> --wait` or cancel it. |
| `voice_worker_failed`, `voice_chunks_failed`, `voice_chunks_missing`, `voice_align_failed`, `voice_assemble_failed` (exit 5) | The server stopped part way: call `voice.generate` again, the finished sentences are kept. If it repeats, stop and tell the owner. |
| `interrupted` (exit 5) | The server restarted while the job ran: start it again. |
| `voice_not_configured` | This machine cannot make a voice (no voice worker): stop and tell the owner. |
| `nothing_to_say` | The narration has no sentence to speak: go back to step 2. |
| `cost_not_confirmed`, `spend_not_allowed` (exit 3) | A cost needs `--yes-cost` and the owner's permission: ask. |
