---
name: bti-title
description: The title of the video, a small part of step 2 of Behind the Image. Use when the narration is approved and the project has no title yet (`bti status <project>` says `title: none yet`), when the narration changed after an agent wrote the title (`stale`), or when the owner asks for another title.
---

# The video's title (step 2, after the narration)

Read `AGENTS.md` first (the rules, the exit codes). This document is for the title of the video. It is a small part of the step `script`: it comes after the gate `narration` and before the voice.

## Goal

One line that a stranger reads before deciding to watch, and that the video shows on screen under the channel's name after the cold open (the beat `ID-BRAND-03`, written by a sweep of light). It must make that
person want the answer by naming, in words anyone can picture, the most surprising TRUE thing the video shows. An agent reads the approved narration and writes it by a written skill
(`skills/title/TASK.template.md`, the task the agent itself reads); you start that job, read what it proposed, and leave the choice to the owner when the owner has a view.

## What it needs and what it gives

- Needs: the approved narration (gate `narration`). Setting a title by hand (`title.set`) needs nothing: it may be done at any time.
- Gives: the document `projects/<project>/title.json` (never edit it): the title in use (`text`, who chose it, when, `source`: `agent` or `person`), the candidates the agent returned (`text`, `form`, the narration `lines`
  that make it true, `scores`, a Vietnamese `reason` for the owner), the narration revision it was written from, and the titles used before. Its state is `none`, `done` or `stale`: `stale` means an agent's title was
  written from another narration than the one approved now. A title SET by a person or an operator is never stale, and the automatic run never writes over it; only a generation asked for by hand does (the old one goes to
  the history).
- Used by: the storyboard (a full draft writes it into the storyboard's own `video_title` field; setting or writing a title while a storyboard exists applies the identity again with it, so the storyboard's revision changes and its approval stops
  standing), the export's description (its first line), the output folder (`README.md`, `state.json`, `2_script/title.md` with every candidate and its reason) and the page of step 2.
- The draft waits for it: `draft.start` says `title_done` in its `needs` while the title is `none` or `stale` and an agent could write it (without a title the beat shows the painting's title, and `bti status` warns once).
- The automatic run takes `title.generate` by itself, before the voice. Nobody approves a title: there is no gate.

## The actions it uses

<!-- BEGIN GENERATED: actions -->
| id | step | page button | gate | cost | long job |
|---|---|---|---|---|---|
| `title.generate` | script | Viết tựa video |  | model: about 1 minute | yes |
| `title.set` | script | Đặt tựa video |  |  |  |
| `title.cancel` | script | Dừng |  |  |  |
<!-- END GENERATED: actions -->

`title.generate` takes an optional `note` (`--set note="..."`, at most 600 characters): the owner's wish for this title in their own words ("make it about the mirror, not the ring"). The agent sees it at the top of its task. Do not put
rules there (they are in the task) and never put a remark meant for the owner: the agent may use it in the title.

`title.set` takes `--set text="..."`: one line of at most 60 characters. It checks the length and that it is one line, and nothing else: a person may write what they want. To take a candidate of the agent as it is, give its text
(`GET /api/projects/{pid}/title` lists the candidates with their number, `candidates[n-1]`); the route also takes `{"base_rev", "option": n}` in a body of its own (`--body FILE`).

## A worked session

Fixture project `arn` (the narration is approved; the agent here is a test double that ends at once and writes a prepared answer, the real one takes about a minute and its candidates differ).

```text
# fixture: book narration_approved title
$ bti status arn
...
title: none yet (title.generate has an agent write one once the narration is approved; title.set sets your own)
...
next: bti do arn title.generate --yes-cost --wait   (Viết tựa video)
$ bti do arn title.generate
a person is needed: cost_not_confirmed
  detail: title.generate costs model (about 1 minute).
  fix: Run it again with --yes-cost when the owner asked for this work.
(exit 3)
$ bti do arn title.generate --yes-cost --wait --set note="make it about the saint, not the ring"
started job <job> (title.generate)
...
done: {"title":"The Saint Who Was Also an Advertisement","candidates":2,"sentence":"Agent đã viết 2 tựa và chọn: \"The Saint Who Was Also an Advertisement\"."}
$ bti status arn
...
title: "The Saint Who Was Also an Advertisement" (agent:mock, done)
...
$ bti do arn title.set --set text="Why Is a Saint Weighing a Ring?"
ok: title.set
{"rev":"<rev>","state":"done","title":{"text":"Why Is a Saint Weighing a Ring?","by":"cli:bti","at":"<time><any>
$ bti status arn
...
title: "Why Is a Saint Weighing a Ring?" (cli:bti, done)
...
```

Read the answer of `GET /api/projects/{pid}/title` to see the candidates (each has its `text`, `form`, the narration `lines` that make it true, `scores` and a Vietnamese `why`); `bti` prints no documents. A title set by hand
stays in use when the narration changes; ask `title.generate` again (by hand) to replace it with the agent's.

## What a good title is

Taken from the task the agent reads (`skills/title/TASK.template.md`, which is also what the program checks):

- It makes a stranger want the answer. It names, in words anyone can picture, the most surprising TRUE thing the video shows, and the video must keep that promise.
- Every word is true to the narration. Each candidate cites the narration lines that make it true; "may", "probably" and "one reading sees" are never stated as facts (a question or "might" keeps it honest), and a title true to the
  letter that leaves a false picture is struck.
- It has at least one thing a person can picture (a saint, a ring, a mirror, a shop sign), not two abstract labels set against each other.
- It stands alone: no painter's name, no painting's title, no date is needed to understand it (the small line under it carries those, and the program writes it).
- It opens a gap and does not close it: it never fits any video ("The Hidden Meaning", "A Closer Look", "The Story Behind ...", "... Explained", "The Truth About ...").
- No borrowed excitement ("shocking", "secret", "insane", "you won't believe", "nobody knows", "the first", "the only", "the most"), unless the narration itself says exactly that and gives its reason.
- 28 to 55 characters is best and 60 is the limit (a phone cuts longer ones), nine words at most, Title Case, one line, no colon and second half, no brackets, no emoji, no word in capitals, at most one question mark.
- At least twelve candidates are written, in at least five forms (the contradiction, the question, the thing hidden in plain sight, what it really is, the object with a past, the hard number); the five to eight best are kept, the
  best first, each scored on `curiosity`, `concrete`, `central` and `clear`. A first choice that scores under 4 on `central` would promise a sentence, not the video.
- Two real verdicts of the owner: "A Prayer or a Shop Sign?" was rejected ("not intriguing or interesting or capture the essence of the video": two labels, nothing one can picture), "The Saint Who Was Also an Advertisement" was
  accepted (two concrete things that contradict each other, true to the narration, the video's own answer in one line).
- The reasons (`why`) are Vietnamese, one short sentence each: the owner reads them on the page.

You do not write titles yourself unless the owner dictates one: you start the job, read the candidates, and tell the owner the first choice and the others. The owner picks on the page, or tells you which one to set with `title.set`.

## The refusals you will meet

| code | what to do |
|---|---|
| `narration_not_approved` (409) | The title is written from the approved narration: approve it first (the owner, or `bti approve <project> narration` when the owner allowed it). |
| `no_running_job`, `agent_job_running`, `longjob_running` (exit 5) | An agent job of this project runs (the pictures agent, a prompt-box turn, a draft, an automatic run or a title job): `bti job <id> --wait`, then go on. |
| `agent_unavailable`, `agy_auth`, `claude_auth`, `agy_missing`, `claude_missing` | The agent cannot run on the server: tell the owner; do not try another agent yourself. |
| `agy_rate_limit`, `claude_rate_limit` (exit 5) | The quota is used up: call again after `retry_after_seconds`; the owner may switch agent on the page. |
| `title_no_output`, `title_limit` | The agent's file was still wrong after the one repair round, or it ran out of time or steps: call `title.generate` again (a note that names what you want helps), or tell the owner. Nothing was written. |
| `title_tampered` | The agent changed files outside its work folder; its answer was thrown away: check the project, then call again. |
| `title_too_long`, `title_not_one_line`, `title_invalid` (422) | `title.set` takes one line of text of at most 60 characters. |
| `title_option_unknown`, `title_choice_needed` (422) | Send exactly one of `text` and `option` (the number, from 1, of a candidate listed by GET .../title). |
| `title_note_too_long`, `title_note_invalid` (422) | The `note` is at most 600 characters of text. |
| `stale_revision` (exit 5) | The title changed under you: `bti` reads the revision itself, so call the same command again. |
