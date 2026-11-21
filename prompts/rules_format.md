<!-- section:outline -->
OUTPUT LAYOUT FOR THE OUTLINE

Write plain text, not JSON, not a table, no code fences. Put a line that says exactly OUTLINE first. Anything above that line is ignored, so keep your notes short. Use exactly these labels, one per line.

OUTLINE

THESIS: one sentence, the question this video answers

HOOKS
h1: first opening line, concrete, something the viewer can look at
h2: second option
h3: third option
HOOK CHOICE: h1

FACTS
f01 | established | PAY-07, HOD-02 | one checkable statement
f02 | disputed | PAY-12, MAD-03 | the statement | conflict: how the sources disagree
f03 | likely | HOD-05 | another statement

CHAPTERS
## c01 COLD OPEN
ROLE: cold_open
CARD: no
BUDGET: 190
PURPOSE: what this chapter does for the argument
FACTS: f01, f03
SHOW: D2; the inscription above the mirror

## c02 THE MERCHANT CITY
ROLE: chapter
CARD: yes
BUDGET: 260
PURPOSE: ...
FACTS: f02
SHOW: the whole painting

NOTE: one sentence for the owner, only when something has to be said that is not a fact or a conflict

TARGET WORDS: 2000

Rules:
- A fact line has four parts separated by |, in this order: id, certainty (established, likely or disputed), the source paragraph ids separated by commas, the claim. A fifth part starting with "conflict:" is added only when sources disagree.
- Chapter ids are c01, c02, ... in order. ROLE is cold_open, chapter or closing. CARD is yes or no (yes means the video shows a chapter card). The first chapter is the cold open and the last is the closing.
- SHOW lists what the camera can point at: named details (D1, D2, ...) from the brief, or plain words.
- Budgets are words of narration and must add up to about TARGET WORDS. A budget is a ceiling: the narration may not pass it.
- NOTE lines (none, or at most three, each one sentence, written after the last chapter) are for the owner and nobody else: the owner reads them with the checks of the outline, and the narrator never sees them. A fact, a conflict and a purpose hold no remark to the owner and no instruction.
<!-- section:script -->
OUTPUT LAYOUT FOR THE NARRATION

Write plain text, not JSON, no tables, no code fences, no preface. Put a line that says exactly FINAL SCRIPT first, then the chapters.

FINAL SCRIPT

## c01 COLD OPEN
Paragraph of narration, one to three sentences, exactly as it will be spoken.
>> facts: f03, f07 | show: the convex mirror; the inscription above it

Next paragraph.
>> facts: f02 | show: the whole painting

## c02 THE MERCHANT CITY
...

Rules:
- A line starting with ## begins a chapter. Copy the chapter id and the title from the outline unchanged.
- Each paragraph is one beat: a blank line before and after, one to three sentences, at most 90 words.
- The line starting with >> after a paragraph is its metadata: the fact ids from the outline that the paragraph rests on, and a short plain-words hint of what is on screen, parts separated by ;. Give both for every beat.
- Spoken words only in the paragraphs. No hook lists, no audit tables, no word counts and no commentary anywhere in the answer. A remark meant for the owner never goes into a paragraph: if one is needed, the beat's >> line may carry it as a last part, note: one short sentence (it is kept as a private note of the line and is not read aloud).
