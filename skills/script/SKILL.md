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
  contradictions between the books, the chapters with their word budgets, and at most three `NOTE` lines: remarks of the model to the owner, kept
  apart from the facts) and the narration (the chapters as lines, each line one stretch of spoken text with a `show` hint for the picture step).
  You never edit the files; the gates `outline` and `narration` record who approved them.
- The voice: the narration is told by a narrator to a viewer who has never heard of the books. It names no author of a source and never says "the
  books" or "the sources"; a disagreement is told as two readings of one object. The fact table keeps who said what. Do not ask for this in a note: it
  is in the prompt, and a note such as "fewer author names" is weaker than the rule (none).
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

The `notes` of `narration.generate` (and of `outline.generate`) are the owner's instruction for THIS run, put at the top of the prompt where they override the model's taste: what to
shorten, which object to dwell on, which dispute to drop. They do not change the rules of the prompt (no author names, a budget is a ceiling, one sentence limit), so do not repeat those
rules there, and never put in a note a remark meant for the owner: whatever is in the note may end up in the narration. When a note names a number, name the number ("at most 230 words").

A narration that is too long. Each chapter's budget is a ceiling in the prompt. A chapter that still comes out more than 10% over its budget is written again by the job itself, once, with a
note that says how many words to cut and shows the model its own text (at most 4 chapters per job; each one is **one model call more**, so a whole narration is 6 to 8 calls and at most 4 more).
The job says so: the chapter's line in the progress reads `đã cắt từ 310 xuống 247 từ (ngân sách 250)`, and the job's `result` carries `"shortened": [{"chapter": "c02", "words": 310,
"budget": 250, "after": 247, "kept": "rewrite"}]`; `"kept": "first"` with a `why` means the rewrite failed, could not be used or was not nearer to the budget, and the first text stayed. What is
still over then is the ordinary warning (`chapter_off_budget` at 30% off, `words_off_target` at 15% off the target). Then, in this order: (1) `narration.generate` again for only the chapters
that are over, with a note that names the number; (2) `narration.ops` (`drop` a line, `merge` two) for the last few words; (3) only when the target itself was wrong, change the target of words in the brief options and
make the outline again. Do not approve a narration more than 15% over its target: the voice is about an hour of machine time and reads every word.

## What a good result is

Take the numbers from `docs/APP_GUIDE.md` (sections 5.1 to 5.5); the page shows the same checks.

- **Length.** The video is 10 minutes or more: at the reading speed of 2.41 words per second that is at least about 1,450 words. The target is the project's word count (the brief options); under 70% of it is an error (`words_under`), more than 15% away from it a warning.
- **Only spoken words.** No markup, no source codes (`PAY-07`), no fact codes (`f03`), no brackets, bullets or `;`, `:`, `( )` and dashes (the voice cannot pause on them). A line is at most 90 words: split longer ones.
- **Rhythm.** Median sentence 12 to 22 words; **no sentence over 25 words** (the one limit: the prompts say it, `long_sentence` warns above it, the bench uses it); no more than 5% under 4; short and long sentences alternate.
- **A narrator, not a review of books.** No line names the author of a source book (`source_author_named`) and none speaks about the sources themselves, "the books", "both books", "the sources", "that passage",
  or carries a remark meant for the owner (`source_talk`). Both warnings STOP an automatic run, because the voice that follows is about an hour: fix the lines first (`narration.generate` for the chapter with a
  note, or `narration.ops`). They look for the surnames of the project's source books as whole words with their capital; "the Book of Exodus", "the books on the table" and "Sir Thomas Hodge" (another
  person who shares a surname) are not hits, but a later bare "Hodge" for that person is: read the line, then fix it or ask the owner.
- **Every claim has a source.** A fact cites at least one source paragraph that exists. Where the books disagree the outline says what each one says (`conflict`, by author or paragraph id, and nothing else); the narration tells it
  as two readings; the owner decides, you never pick a side. Machine-translated sources are not facts, and a restored source is told as one reading, never in its author's name.
- **A fact is not a message.** A remark to the owner ("check this before it is used") does not belong in a fact or its conflict: the narration is written from it and may speak it. That is the warning
  `fact_for_owner` and it stops an automatic run before the outline gate. The model's own remarks to the owner are the `NOTE` lines of the outline, shown among the checks as `outline_note` (a warning that
  does not stop a run; read them before you approve the outline, and tell the owner what they say). The narration never sees them.
- **A hook first.** The outline carries the main question and three candidate openings; the video opens with one of them (the cold open states the question) and the facts that answer it come before the biography.
- **Each line says what to show.** The `show` hint of a line ("the mirror; the writing above it") is what the picture step works from; a line with none is a warning (`no_show`).
- **Overlap with the books** is only information (the owner decided copyright is not a blocker), but a line that copies a sentence of a book is a poor line: write it again in your own words.

## The refusals you will meet

| code | what to do |
|---|---|
| `outline_has_errors`, `narration_has_errors` | Read `issues` (and `chapter_diff` for the narration), fix them (regenerate with a note, or import corrected text), then approve again. |
| a warning `source_author_named`, `source_talk`, `fact_for_owner` stops `bti run` (`quality_warning`) | Not an error: the run waits for you. Regenerate the chapter (or the outline) with a note that names the lines, or fix with `narration.ops`; then run again. |
| `outline_not_approved`, `outline_stale`, `outline_missing` | The narration follows the approved outline: approve the outline (again) first. |
| `locked_beats` | The owner locked lines the new text would replace: leave them, or `--set force=true` only when the owner said so. |
| `model_job_busy`, `no_running_job` (exit 5) | A model job runs for this project: `bti job <id> --wait`, then go on. |
| `agent_unavailable`, `agy_auth`, `claude_auth` | The agent cannot run on the server (not signed in): tell the owner; do not try another agent yourself. |
| `agy_rate_limit`, `claude_rate_limit` (exit 5) | The quota is used up: call again after `retry_after_seconds`; the owner may switch agent on the page. |
| `outline_unreadable`, `narration_unreadable` | A pasted text could not be read (nothing was overwritten): correct it as `issues` say and import again. |
| `stale_revision` (exit 5) | The document changed under you: read it again and repeat the change on the new revision. |
| `gate_needs_human` (exit 3) | The owner has not allowed you to approve this gate: stop and ask. |
