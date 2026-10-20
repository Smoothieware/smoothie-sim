# smoothie-sim documentation

smoothie-sim builds the real Smoothieware core for a PC and checks firmware pull requests against it, without hardware.
The [README](../README.md) is the short version; these pages have the detail.

| Page | What it covers |
| --- | --- |
| [Installation](installation.md) | Install from a release: script, tarball, deb, rpm or container image; the `smoothie-sim` command; how releases are made. |
| [Getting started](getting-started.md) | Requirements, building the simulator, running the checkers, reading the report. |
| [How it works](how-it-works.md) | Staging, the host shims, stage patches, the simulator runtime and its output. |
| [Checkers](checkers.md) | Each checker: what it verifies, its inputs and every option. |
| [Wait rules](wait-rules.md) | `rules.json`: which blocking calls fail, warn or pass, and why. |
| [Old-PR replay](pr-replay.md) | The regression test that replays historical pull requests. |
| [Race mode](race-mode.md) | `RACE=1`: a step interrupt that preempts the firmware mid-write. |
| [Limits](limits.md) | What the simulator does not model. |
| [Developing](developing.md) | Repository layout, adding a stage patch, a checker or a case. |
