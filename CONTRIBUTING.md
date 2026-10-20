# Contributing

Issues and pull requests are welcome.

- Report a problem with the firmware revision you tested, the exact command, and the output or `report.html`. Remove private content from logs.
- Keep a change focused. A new checker, stage patch or replay case follows the steps in [Developing](documentation/developing.md).
- Before opening a pull request, build the simulator against current Smoothieware `edge` and run `./run_checks.sh` (see [Getting started](documentation/getting-started.md)); say what you ran and what you did not.
- User-visible changes get an entry under `[Unreleased]` in [CHANGELOG.md](CHANGELOG.md).
- Contributions are licensed under GPL-2.0-or-later (files under `overlay/` keep Smoothieware's GPL-3.0-or-later).
