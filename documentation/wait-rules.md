# Wait rules (`rules.json`)

Smoothieware must not block: delays inside handlers stall motion. `rules.json` is the table the modules checker applies.

Every call has a status and a written reason:

| Status | Meaning | Calls |
| --- | --- | --- |
| `forbidden` | Fails in a handler, helper or unknown context; warns at startup only. | `wait`, `wait_ms`, `wait_us`, `sleep` |
| `ask-maintainer` | Warns: the project's position is not settled. | `safe_delay_ms`, `safe_delay_us`, `safe_delay`, and `wait_us` of 2 us or less (`short_wait`) |
| `allowed` | Never reported. | `wait_for_idle` |

Other keys:

- `busy_loop_pattern`: regex for busy loops (`us_ticker_read`).
- `scan_dirs`: directories the static scan covers; `allow`: files exempt from the scan (shell, kernel, utils).
- `accepted_runtime_waits`: short waits accepted with a reason (display bit-bang timing of 100 us or less).
- `known_debt_runtime_waits`: waits that exist today and stay reported as warnings.
- `runtime_long_handler_us`: a handler running longer than this fails unless listed in `long_handler_allow` (each entry deserves a reason).

To change policy, edit `rules.json`; the report names the rule that applied to each hit.
