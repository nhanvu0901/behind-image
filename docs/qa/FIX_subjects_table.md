# Subjects table: incomplete

The picks normalizer preserves `subjects` rows (`id`, `kind`, `name`, optional `sub`, `strip`, `where`) and ordered `beats[beat].about` entries (`id`, `words`). Shape validation checks unique IDs and references. `set_subjects` and `set_about` are typed operations; subjects have a change-log/undo unit. This is only a foundation, not an integrated feature.

The picks agent, legacy-name conversion, draft compiler, generated strips and pointers, subject visibility warning, repair loop, automatic run and generic prompt examples remain unimplemented. No checks were folded. The requested painting fixtures and end-to-end behavior remain unverified. Undo behavior itself has not been tested. Do not rely on these partial changes for production.

Focused test summaries:

```text
2 passed in 0.11s
1 passed, 1 warning in 5.57s
```

The JavaScript suite reported:

```text
ℹ tests 499
ℹ suites 0
ℹ pass 497
ℹ fail 1
ℹ cancelled 0
ℹ skipped 1
ℹ todo 0
ℹ duration_ms 1141.006792
```

The failing test is `tests/editor_frontend/idfix.test.mjs`: it expects `/Settle/` in a Vietnamese issue sentence. The broad server suite was interrupted during `tests/picks`; remaining requested suites were not run. Generator checks reported:

```text
stale: skills/picks/SKILL.md: run `python -m bti.cli.docgen`
docs/OPS.md is out of date: run python -m bti.ops.doc
```

The hints check produced no output. Generated documentation was not updated.
