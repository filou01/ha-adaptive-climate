# Learning hotfixes in fork preview 2

> Preview 3 includes these fixes plus the [shared learning startup fix](learning-startup-fix.md).

Release `v0.67.1-pwm.2` integrates the reviewed changes from
`apply_ac_067_cycle_fix.py` and `adaptive_climate_hotfix_0.67.0_v3.py` into the
current controller architecture. Their deployment/backup/restart entry points
are not included or executed. The fixes apply with PWM coordination enabled or
disabled; the planner and minimal/maximal overlap policies are unchanged.

## Behavior and scope

[Upstream issue #6](https://github.com/afewyards/ha-adaptive-climate/issues/6):
restoring an old controller session no longer suppresses a fresh learning
cycle. Transient cycle/demand flags restart consistently with the new tracker;
stored gains, integral, wear data and completed learner cycles remain intact.
Zero and tiny PWM output now share one continuous low-demand deadline, so
0 → 0.1 → 0 fluctuations cannot repeatedly cancel settling. Forced OFF clears
the active learning session even if the electrical relay is already OFF. Both
independent and serialized coordinated heater paths receive the fix.

**Remaining issue #6 scope:** repeated maintenance output at or above the
existing 2% threshold can still keep a session active. These supplied fixes
do not introduce a maximum session duration, change the E term, manufacture
completed cycles or redesign settling. They do not guarantee completion of
every long maintenance session described in the broader report.

[Upstream issue #7](https://github.com/afewyards/ha-adaptive-climate/issues/7):
manual services and scheduled daily analysis read actual HEAT PID gains from
the gains manager. Missing gains are reported explicitly. Diagnostics distinguish
insufficient cycles, cooldown gates, disturbed/usable cycles, convergence and
filtered/no matching rules. Calculating or viewing a recommendation no longer
consumes cooldown time or cycle credit. Only successfully applying gains commits
the adjustment timestamp and resets its cycle counter, after the existing
history-reset operation. Failed application does not consume that credit.

Learner payload version **11 → 12** adds `cycles_since_last_adjustment`.
Existing completed cycles, confidence, gains and timestamps are retained.
Older payloads without the counter start it conservatively at zero once;
subsequent saves/restarts preserve it. No manual learning reset is needed.
Intentional PID application retains its existing history-reset behavior.

## Validation evidence

Tested source: `a9b4716f58d88b4bd20007706026f4f43bf5c622`.
The release adds documentation to that exact source/test tree.

| Validation | Result |
| --- | --- |
| Full Linux Python 3.11.18 suite | 3549 passed, 11 skipped; exit 0 |
| Full Linux Python 3.12.3 suite | 3549 passed, 11 skipped; exit 0 |
| New hotfix regressions | 29 tests, all included in both full runs |
| Existing PWM regressions | 74 tests, all included in both full runs |
| Ruff check and format | PASS; 249 files formatted |
| Pyright source | PASS; 0 errors |
| Windows Python 3.14.5 full suite | 3538 passed, 11 skipped; 11 existing report-format failures (`%b %-d`) |
| GitHub Linux 3.11/3.12 matrix | [PASS](https://github.com/filou01/ha-adaptive-climate/actions/runs/41873657025), full tests/lint/format/types |
| HACS packaging | [PASS](https://github.com/filou01/ha-adaptive-climate/actions/runs/41873657016) |
| hassfest | [PASS](https://github.com/filou01/ha-adaptive-climate/actions/runs/41873656987) |

The new tests cover restart/migration, malformed counters, authoritative gains,
diagnostic reasons, repeated recommendation reads, successful/failed manual and
automatic application, daily analysis, and forced-OFF/zero-tiny demand in both
heater paths. Six existing pytest asyncio-marker warnings remain.
The eight deterministic 24-hour PWM replays also run in the full suite;
[the original PWM report](architecture/pump-aware-pwm-verification.md) describes
their model, measurements and limitations.

**NOT RUN:** real HA/device end-to-end testing, physical pump/relay/flow tests,
supervised 24-hour heating operation, Raspberry Pi performance measurements,
variable maintenance-duty replay with real actuator timing, and wiki publication.
No running Home Assistant installation was modified or restarted.

## Changed files and architecture

- `adaptive/learner_serialization.py`, `adaptive/learning.py`,
  `adaptive/learning_coordinator.py`: persistent counter, diagnostics and explicit
  successful-adjustment commit.
- `managers/pid_tuning.py`: commit cooldown after gain application/history reset.
- `managers/state_restorer.py`, `managers/state_attributes.py`: transient-session
  restoration contract.
- `managers/heater_timers.py`, `managers/heater_controller.py`,
  `managers/heater_actuation.py`: unified low-demand deadline and OFF reset.
- `services/learning_diagnostics.py`, `services/__init__.py`,
  `services/scheduled.py`: shared authoritative gains and outcome reporting.
- `tests/test_learning_hotfixes.py`: new regressions. Updated existing contracts
  in `test_heater_controller.py`, `test_integration_cycle_learning.py`,
  `test_learner_serialization.py`, `test_learning.py`, `test_rate_limiting.py`
  and `test_services.py`.
- Documentation: this report, README, PWM user guide, historical verification
  notice and combined PR draft.

## Installation and rollback

Use [the fork release](https://github.com/filou01/ha-adaptive-climate/releases/tag/v0.67.1-pwm.2)
in HACS with prereleases visible, then restart HA. Existing YAML remains valid;
coordination stays disabled unless explicitly configured. Do not additionally
run the old standalone patch scripts against this fork. Back up integration,
configuration and adaptive learning storage before upgrading.

To disable coordination, remove its block or set `enabled: false` and restart.
This leaves these general learning fixes active. To roll back the code, select
the unchanged `v0.67.1-pwm.1` release or your recorded upstream version and restart.
Keep the storage backup; older code does not persist the new counter. Do not
delete learning storage as a troubleshooting step. Fork preview identity uses
the release tag; the semantic-release-managed manifest remains at `0.67.0`.

No upstream pull request has been opened.
