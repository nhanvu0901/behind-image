---
name: bti-script
description: Step 2 of Behind the Image, the script of one painting (outline, then narration). Use when `bti status <project>` shows the step `script` as current.
---

# Step 2: the script (outline, then narration)

Read `AGENTS.md` first (the rules, the exit codes). This document is for the step `script` of a project made from a book.

## Goal

An approved **outline** and an approved **narration**: the spoken text of a video of 10 minutes or more about one painting, written only from the
project's book sources. A model writes both; you start the job, read the result, fix what is wrong, and ask for the gate when it is good.

## What it needs and what it gives

- Needs: a project made from a book (step `artwork` done). Its sources are numbered paragraphs (`PAY-07`, `HOD-02`, ...) that the outline cites.
- Gives: the outline (the question the video answers, three openings, a table of facts that each cite source paragraphs with a certainty and the
  contradictions between the books, and the chapters with their word budgets) and the narration (the chapters as lines, each line one stretch of
  spoken text with a `show` hint for the picture step). You never edit the files; the gates `outline` and `narration` record who approved them.
- Unlocks: steps 3 (`voice`) and 4 (`picks`), once the narration is approved.

## The actions and operations it uses

<!-- BEGIN GENERATED: actions -->
| id | step | page button | gate | cost | long job |
|---|---|---|---|---|---|
| `outline.generate` | script | Lập dàn ý |  | model: a few minutes | yes |
| `outline.import` | script | Dán dàn ý |  |  |  |
| `outline.approve` | script | Duyệt dàn ý | yes |  |  |
| `narration.generate` | script | Viết lời dẫn |  | model: a few minutes | yes |
| `narration.import` | script | Dán lời dẫn |  |  |  |
| `narration.ops` | script | Sửa lời dẫn |  |  |  |
| `narration.approve` | script | Duyệt lời dẫn | yes |  |  |
| `outline.cancel` | script | Dừng |  |  |  |
| `narration.cancel` | script | Dừng |  |  |  |
<!-- END GENERATED: actions -->

The narration has its own small operations (`narration.ops`, body `{"base_rev": <rev of GET /api/projects/{pid}/narration>, "ops": [...]}`): `split` (a line at a word),
`merge` (a line into the one before), `drop`, `insert`, `move`, `drop_chapter`, `add_chapter` and `order_like_outline`. They are not the operations of `bti ops` (that command is for the picks
and the storyboard). To read a document use the GET routes (`GET /api/projects/{pid}/outline`, `GET /api/projects/{pid}/narration`: the answers carry `rev`, `issues` and, for the narration,
`stats`); `bti` itself prints no documents.

## A worked session

Fixture project `arn` (a copy of the sample book project; the model is a test double, so the text it writes is a placeholder). The owner turns automatic running on on the page between two commands.

```text
# fixture: book new
$ bti status arn
project: arn   stage: selected   current step: script (Kịch bản)
automatic running: off (an agent approves no gate; the owner approves on the page or turns it on there)
approvals: outline -; narration -; picks -; storyboard -
...
next: bti do arn outline.generate --yes-cost --wait   (Lập dàn ý)
$ bti do arn outline.generate
a person is needed: cost_not_confirmed
  detail: outline.generate costs model (a few minutes).
  fix: Run it again with --yes-cost when the owner asked for this work.
(exit 3)
$ bti do arn outline.generate --yes-cost --wait
started job <job> (outline.generate)
...
done: {"rev":"<rev>","issues":[]}
$ bti approve arn outline
a person is needed: gate_needs_human (HTTP 403)
  detail: The outline gate can only be approved by the owner: automatic running is off for this project.
  fix: Ask the owner to approve this gate on the page, or to turn automatic running on for this project and allow the gate (the switch on the page, PUT /api/projects/arn/auto), then call again.
(exit 3)
# owner: auto on
$ bti approve arn outline
approved outline as cli:bti
$ bti do arn narration.generate --yes-cost --wait
started job <job> (narration.generate)
...
done: {"written":["c01","c02","c03","c04","c05","c06"],"skipped":[],"rev":"<rev>"}
$ bti approve arn narration
approved narration as cli:bti
$ bti status arn
project: arn   stage: script   current step: voice (Giọng đọc)
automatic running: on (an agent may approve: outline, narration, picks, storyboard; may confirm: model, machine_time; paid never)
approvals: outline cli:bti; narration cli:bti; picks -; storyboard -
...
next: bti do arn voice.generate --yes-cost --wait   (Tạo giọng đọc)
```

To change something, run the generator again with a note (`bti do arn outline.generate --yes-cost --wait --set notes="fewer facts about the patron"`), redo only some chapters
(`bti do arn narration.generate --yes-cost --wait --set 'chapters=["c02"]' --set notes="shorter, less biography"`; a line the owner locked needs `--set force=true` or an unlock first), or
replace text with `outline.import` / `narration.import` (`--set text=...`; for the narration `--set merge=true` replaces only the chapters that are in the pasted text).

## What a good result is

Take the numbers from `docs/APP_GUIDE.md` (sections 5.1 to 5.5); the page shows the same checks.

- **Length.** The video is 10 minutes or more: at the reading speed of 2.41 words per second that is at least about 1,450 words. The target is the project's word count (the brief options); under 70% of it is an error (`words_under`), more than 15% away from it a warning.
- **Only spoken words.** No markup, no source codes (`PAY-07`), no fact codes (`f03`), no brackets, bullets or `;`, `:`, `( )` and dashes (the voice cannot pause on them). A line is at most 90 words: split longer ones.
- **Rhythm.** Median sentence 12 to 22 words; 90% of the sentences at most 32 words; no more than a quarter over 25 and no more than 5% under 4; short and long sentences alternate.
- **Every claim has a source.** A fact cites at least one source paragraph that exists. Where the books disagree the outline says what each one says (`conflict`); the owner decides, you never pick a side. Machine-translated sources are not facts.
- **A hook first.** The outline carries the main question and three candidate openings; the video opens with one of them (the cold open states the question) and the facts that answer it come before the biography.
- **Each line says what to show.** The `show` hint of a line ("the mirror; the writing above it") is what the picture step works from; a line with none is a warning (`no_show`).
- **Overlap with the books** is only information (the owner decided copyright is not a blocker), but a line that copies a sentence of a book is a poor line: write it again in your own words.

## The refusals you will meet

| code | what to do |
|---|---|
| `outline_has_errors`, `narration_has_errors` | Read `issues` (and `chapter_diff` for the narration), fix them (regenerate with a note, or import corrected text), then approve again. |
| `outline_not_approved`, `outline_stale`, `outline_missing` | The narration follows the approved outline: approve the outline (again) first. |
| `locked_beats` | The owner locked lines the new text would replace: leave them, or `--set force=true` only when the owner said so. |
| `model_job_busy`, `no_running_job` (exit 5) | A model job runs for this project: `bti job <id> --wait`, then go on. |
| `agent_unavailable`, `agy_auth`, `claude_auth` | The agent cannot run on the server (not signed in): tell the owner; do not try another agent yourself. |
| `agy_rate_limit`, `claude_rate_limit` (exit 5) | The quota is used up: call again after `retry_after_seconds`; the owner may switch agent on the page. |
| `outline_unreadable`, `narration_unreadable` | A pasted text could not be read (nothing was overwritten): correct it as `issues` say and import again. |
| `stale_revision` (exit 5) | The document changed under you: read it again and repeat the change on the new revision. |
| `gate_needs_human` (exit 3) | The owner has not allowed you to approve this gate: stop and ask. |
