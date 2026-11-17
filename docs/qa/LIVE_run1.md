# LIVE_run1: the first real whole-chain run (Arnolfini Portrait, project `arnolfini-live`)

Driver: LIVE agent. Server: winbox-lan, app 127.0.0.1:8560, tunnel Mac 8561. Times are Mac local (AST label), server clock differs.
Model runs counted below as `MR-n` (cap 30). Bugs as `LR-nnn`. Approvals on the owner's behalf marked **[APPROVAL-ON-BEHALF]**.

## Timeline
- 00:04 tunnel up, `/api/health` real/real, `/api/models` lists agy models (agy.ok true), including gemini-3.8-flash-high and gemini-pro-orchestrator-g1-pro.
- 00:04 project `arnolfini-live` created from artwork_key `eyck-the-arnolfini-portrait` (3 book sources).
- 00:04:31 **MR-1** outline, `agy:gemini-3.8-flash-high` via `POST /outline/generate`. Done in 2 min 6 s, first attempt, no issues: 8 chapters (c01 cold open ... c08 closing), 33 facts, target 2000 words. The Antigravity stream-json provider worked on the first real call (no fix needed).
- 00:07 **[APPROVAL-ON-BEHALF]** outline approved by LIVE (rev d37e911...). Outline read first: thesis is the three-way question (wedding / memorial / merchant advert); chapters are coherent.
