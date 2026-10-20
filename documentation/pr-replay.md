# Old-PR replay (regression test for the wait checker)

The wait checker must keep catching real mistakes. `tools/regress_prs.py` rebuilds the trees of historical Smoothieware pull requests that were rejected
for blocking waits and fails if one is no longer flagged.

```sh
tools/regress_prs.py OUT_DIR --firmware FIRMWARE_CHECKOUT [--trees DIR] [--prs 620 633 ...] [--no-run]
```

Requires `gh` (read-only use). For each PR:

1. `tools/make_pr_trees.sh OUT FIRMWARE_CHECKOUT` builds `OUT/trees/base` (the checkout's `HEAD`) and `OUT/trees/<PR>` (base plus `gh pr diff`; hunks that no longer apply are dropped and counted).
2. `tools/replay_pr.sh PR TREES OUT` builds one simulator per PR (files a PR changes outside `src/` go in as `EXTRA_FILES`) and runs the modules checker with the PR's extra config and workload.
3. `cases/pr-replay/expected.json` says per PR whether the static scan and the runtime check must flag it, and why a PR is not runtime-capable (for example it does not compile against current `edge`).

`--no-run` only evaluates results already in `OUT_DIR`. The summary is written to `OUT_DIR/regress.json`; pass it as `REPLAY=` to `run_checks.sh` to add the table to the report.

## Cases (`cases/pr-replay/`)

- `evidence.json`: for each PR, the maintainer's public review comments with links.
- `<PR>/config.extra`, `<PR>/workload.gcode`: configuration and G-code appended to the module defaults to exercise the PR's code path.
- `<PR>/compat/port.patch`: ports a PR written against an old firmware API so it builds, without touching the lines the PR is judged on (PR 633, and the synthetic PR 564). See the `README.md` beside each patch.
- `RESULTS.md`: what each PR shows in the static scan and at runtime.

PR 564 is synthetic: a blocking ADC-style busy loop injected into a copy of the base tree.
