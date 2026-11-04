# PWM event-loop callbacks — preview 5

`v0.67.1-pwm.5` corrects the reported call to `hass.async_create_task` from a
worker thread. The timer lambda and binary-output state listener introduced
with PWM coordination were synchronous functions without HA's `@callback`
annotation. HA can dispatch such functions to its executor. Besides creating
a task, those functions could mutate scheduler or actuator state off-loop.

The timer now uses a named, marked callback. The output listener is also marked,
as is the short state-confirmation listener in `HeaterActuationController`.
All three perform nonblocking work on the event loop. The scheduler's generation
guards, serialized controller command path and confirmation timeout remain in
place. Simply changing the task-creation API would not protect the other state
mutations in those callbacks. This follows the
[HA thread-safety guidance](https://contributors.home-assistant.io/core/internals/thread-safety/).

All earlier learning/startup fixes and input_boolean support remain included.
No YAML, PID parameter, schema, learning-data, phase-planner or overlap-policy
change is introduced. Coordination remains opt-in and disabled by default.

## Separate `Large dt discrepancy` warnings

The report also compares `actual_dt=50.30` with `sensor_dt=0.81`, and
`actual_dt=0.57` with `sensor_dt=39.98`. In `managers/control_output.py`, these
are respectively the time between calls to `calc_output` and the time between
temperature sensor updates. They need not coincide when external or periodic
events also request control. The warning is emitted for ratios above 10 and
is rate-limited per entity. It does not itself cancel learning or force fallback.

In the supplied configuration, `sampling_period` is 60 seconds. The underlying
PID controller separately checks its sampling interval and can return its
cached output; the diagnostic's `actual_dt` therefore does not necessarily
describe an actual applied PID integration step. Normal group timer/output
updates do not call `calc_output`. Fallback release requests a full thermostat
control pass, which currently recalculates output even with `calc_pid=False`;
that behavior predates this fix.

The two log entries alone do not identify which control trigger occurred or
prove a PID timing defect. This release fixes the confirmed thread-dispatch
bug and leaves that diagnostic and PID behavior unchanged. It does not claim
that the reported dt warnings will disappear or that their exact live trigger
has been reproduced.

## Verification

Tested source/test commit: `587d621641c58aeb1184d3fbd056668cce3231dc`.
Only release documentation is added after that source/test tree.

Six new regression cases cover both switch and input_boolean outputs. The
harness models HA dispatch: marked sync functions run on the loop, unmarked
functions run through `asyncio.to_thread`; task creation rejects the wrong
thread. It verifies output-event dispatch, timer task creation, stale timer
invalidation and state-confirmation listener cleanup. The existing real
controller boundary, failure, immediate-demand and simulation tests also run.
This is a deterministic modeled boundary, not a full installed-HA test.

| Check | Result |
| --- | --- |
| Windows callback/controller safety and HA boundary tests | 44 passed |
| Full Linux Python 3.11.18 suite | 3578 passed, 11 skipped; exit 0 |
| Full Linux Python 3.12.3 suite | 3578 passed, 11 skipped; exit 0 |
| Ruff check / format | PASS; 251 files formatted |
| Pyright source | PASS; 0 errors |
| GitHub test/lint/type matrix | [PASS](https://github.com/filou01/ha-adaptive-climate/actions/runs/41883832132) |
| HACS | [PASS](https://github.com/filou01/ha-adaptive-climate/actions/runs/41883832388) |
| hassfest | [PASS](https://github.com/filou01/ha-adaptive-climate/actions/runs/41883831711) |

The full suite includes eight deterministic 24h legacy/coordinated replays;
the [existing simulation assumptions](architecture/pump-aware-pwm-verification.md)
and [Boolean proxy observation limits](input-boolean-pwm.md) remain applicable.

**NOT RUN:** installed-HA debug/thread-safety end-to-end trial, physical
NSPanel/ESPHome/relay/pump/flow validation, supervised 24h heating, Raspberry Pi
performance, variable maintenance-duty replay with real actuator timing, full
Windows suite for preview 5 and wiki publication. The actual dt-warning trigger
in the user's installation has not been reproduced.

## Changed files, upgrade and rollback

- `managers/pwm_coordination.py`: marked timer wrapper and output listener.
- `managers/heater_actuation.py`: marked confirmation listener.
- `tests/test_pwm_callback_safety.py`: executor-versus-loop regression harness.
- README, user guide, this report and combined PR draft: evidence and scope.

Back up integration/configuration/learning storage, select
[`v0.67.1-pwm.5` in HACS prereleases](https://github.com/filou01/ha-adaptive-climate/releases/tag/v0.67.1-pwm.5)
and restart HA. For the monitored restart first turn participating thermostats
OFF through HA and verify outputs OFF, then resume HEAT after startup. No
learning reset, standalone patch or YAML change is needed. Check for fresh
thread-safety messages after restart rather than only reading old log entries.

Disable coordination and restart to return to independent control. Code rollback
to unchanged preview 4 is possible with compatible learning data, but restores
the known callback-dispatch bug; preview 5 is the corrective version. The
manifest remains semantic-release managed at `0.67.0`; the tag identifies this
fork preview. No upstream issue/comment/PR is automatically posted.
