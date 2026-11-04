# Pump-aware PWM: safety review and implementation blocker

Historical review of the initial prerequisite-only commit. The later
implementation and current evidence are documented in the
[verification report](pump-aware-pwm-verification.md).

Reviewed on 2026-11-04 against upstream main
`48add428ccc9d356be186f69049526a7d91116c9` (0.67.0), on branch
`codex/pump-aware-pwm`.

**Status: BLOCKED, feature not implemented or available for activation.**
This is a prerequisite test and review change, not the requested production
scheduler. No integration source, configuration schema, hardware path, learning
storage, release version or HACS packaging is changed. Do not install the
proposal's `pwm_coordination` YAML, even with `enabled: false`: the current schema
does not support that option.

The requested safety stop applies: a scheduler cannot be represented as ready
while successful actuation, exact-once credit and OFF precedence remain unproven.
Five deterministic counterexamples are provided in
[`test_pwm_coordination_prerequisites.py`](../../tests/test_pwm_coordination_prerequisites.py).
The strict expected failures document open gates, not passing safety checks.
They only accept assertion failures; unrelated exceptions are not masked.

## Checkout and specification compatibility

The supplied workspace was an empty Git repository with no commits or remotes.
Upstream was cloned into `ha-adaptive-climate/`, then the feature branch was
created from its current main. No personal fork remote was supplied or created.
No push or upstream PR was performed. The supplied handoff is kept locally at
`docs/proposals/pump-aware-pwm/`, excluded via `.git/info/exclude`; private room
examples and implementation prompts are not included in this change.

The handoff names a review date but no reviewed source commit. An exact temporal
breaking-change comparison is therefore unavailable. The following are verified
current contracts and mismatches with a naive scheduler adapter, rather than
claims that each changed since the author's review:

| Area inspected | Current contract and consequence |
| --- | --- |
| `pwm_controller.py` | Effective duration depends on live committed heat; close offset is half valve travel. Raw PID duty is not electrical pulse duration. Accumulation and hardware calls share one method. |
| `heater_controller.py` | Direct 100% bypasses ordinary PWM. Partial demand passes through PWM. Demand bookkeeping precedes both paths. `async_turn_on/off` return `None` for success, rejection and service failure. |
| `heater_service_caller.py` | A per-service Boolean is returned internally, but controller transition methods discard it. A later successful service can clear the failure flag for a previous output. Service acceptance is not observed relay confirmation. |
| `heater_timers.py`, `heater_cycle_bookkeeper.py` | Learning events and valve timers are part of actuation; cancelling a timer does not revoke in-flight service calls. |
| `heat_pipeline.py` | Monotonic valve commands drive exponential committed heat; a failed command cannot be treated as delivered seconds. |
| `climate_control.py` | The temperature lock serializes ordinary control. OFF/inactive and status pauses return early. Contact pause resets credit after its delay. A new scheduler must participate in these paths before returns. |
| `temperature_manager.py`, `climate_state_setters.py` | UI/automation setpoint entry sets force flags and invokes control; presets change the effective target through the common setter. Changes over 0.5 C reset duty credit. Not every PID tick is urgent. |
| `climate.py` | Mode is committed under the temperature lock before awaited I/O; `ModeChangedEvent` is emitted in `finally` after control. An event-only priority subscriber would be too late. OFF-to-HEAT must capture the old mode at entry. |
| `climate_setup.py`, `climate_init.py`, `coordinator.py` | Zone data is registered before entity/controller readiness, with a constructed `climate.<slug>` ID. A live entity reference is attached later. Scheduling must bind actual entity IDs after restoration. Removal cancels existing timers and unregisters after awaited saving. |
| `__init__.py`, `thermostat_config.py`, `const.py` | Domain defaults and a typed entity dataclass coexist. No coordination option exists. Group configuration requires both schema checks and runtime compatibility checks. |
| `manifold_config.py` | `loops` is explicitly rejected; manifold zones use `flow`. Proposed hydraulic weights must be independent. |
| Tests and contributor conventions | HA is stubbed in `tests/conftest.py`; this is not a real HA installation. Strict source Pyright, Ruff, protocols and monotonic elapsed time are conventions. |
| HACS and CI | Integration domain remains `adaptive_climate`, minimum HA is 2026.1.0, no manifest runtime requirements. Versions are semantic-release managed. CI runs pytest on Linux Python 3.11/3.12 plus separate HACS and hassfest workflows. |

No optimizer dependency or runtime module was added.

Follow-up on 2026-11-04: the operator requested a personal GitHub fork and a
per-group minimal/maximal overlap choice, using minimal overlap for their own
installation even when pump energized runtime increases. The accepted policy
is documented in [the overlap policy](pump-aware-pwm-overlap-policy.md).
The personal fork now exists at
[filou01/ha-adaptive-climate](https://github.com/filou01/ha-adaptive-climate).
These updates do not resolve the safety gates or add runtime configuration.

## Reproduced safety and accounting gaps

Use the real `HeaterController`, `PWMController`, service caller, pipeline and
bookkeeper with the repository's HA stubs. A fake monotonic clock and explicit
relay-state dictionary keep the tests deterministic. One successful-start
control proves the harness can deliver and observe a pulse.

| Test | Observed result | Required prerequisite |
| --- | --- | --- |
| `test_failed_start_does_not_commit_delivery_or_learning` | Relay remains OFF and failure is recorded, but `HEATING_STARTED` has already emitted. | Commit transition/learning state only according to a defined successful-command and observation policy. |
| `test_min_off_rejection_retains_accumulated_credit` | With 180 seconds of minimum OFF remaining, no service is called, but 600 seconds of accrued credit become zero. | Reserve credit separately and debit only an accepted pulse; preserve the first safe retry time. |
| `test_failed_accumulated_pulse_retains_credit` | Failed ON leaves relay OFF but consumes all 600 seconds of credit. | Preserve/release reservations after a failed attempt without claiming delivery. |
| `test_force_off_wins_over_inflight_start` | A suspended ON, followed by forced OFF while observed relay remains OFF, completes with relay ON. | Serialize scheduler, mode, safety and fallback ownership, with invalidation before awaited work and post-await reconciliation. |
| `test_failed_stop_does_not_commit_learning_end` | Failed OFF leaves relay ON but emits `HEATING_ENDED`. | Reconcile actual output and accounting after failed stops. |

The in-flight test models a future separate scheduler entry point calling the
existing controller concurrently with a safety/mode entry point. It does not
claim to reproduce this race through today's lock-protected normal control
loop or on particular physical hardware. It demonstrates why merely wrapping
callbacks in generation checks before calling the controller is insufficient.
The service fake deliberately suspends at the awaited I/O boundary; real HA
service return and physical device feedback have additional timing uncertainty.

These gaps are repairable, but a correct repair needs an explicit controller
transaction contract. Changing common controller semantics silently would also
violate the requested disabled-mode equivalence. This branch leaves runtime
behavior intact rather than claiming those repairs and their proofs exist.

## Architecture required before enabling scheduling

1. Extract demand/pulse preparation from execution. Represent an effective pulse
   as a versioned reservation, including raw accumulator credit, effective
   electrical duration, close offset, current pipeline state and timing bounds.
   Define when it can be refreshed, invalidated or committed without double
   valve compensation. Keep the legacy path equivalent when unconfigured.
2. Define controller actuation results for accepted, rejected-minimum-time,
   unavailable, failed and partial-output transitions. Observe electrical
   changes for delivery accounting; do not use request or event timestamps as
   proof of actual ON time. Establish failure behavior for demand switches,
   multiple outputs, polarity and external output changes.
3. Establish one output owner shared by control, mode/safety changes, scheduler
   callbacks and fallback. Invalidate urgent/OFF tokens synchronously, use a
   consistent lock order, reconcile after awaited services, and retry a
   minimum-OFF-blocked urgent pulse at its first permitted instant. A plan
   generation alone cannot cancel a command already dispatched to a device.
4. Only then introduce the pure bounded planner, domain configuration, live
   post-restoration adapters and one cancellable next-event timer per group.
   Preserve direct 100%, low-duty credit, pause semantics and existing learning
   boundaries. Carry observed delivered time across nominal period boundaries.
5. Prove I01-I19 and lifecycle/fallback invariants, then compare the actual
   implementation against independent PWM over the same 24-hour demand trace.

Required future behavior: **An eligible setpoint increase or OFF->HEAT
transition is evaluated immediately and is never delayed to the next
coordinated PWM slot; subsequent pulses are optimized.** Genuine demand,
original minimum timing and safety constraints remain authoritative. This
statement is an acceptance requirement, not a claim about an implemented
coordinator on this branch.

## Validation evidence

Executed on Windows with CPython 3.14.5 in local `.venv` (the ordinary `python`
command resolves to an unusable Windows App Execution Alias). Tools: pytest
9.2.0, pytest-asyncio 1.4.1.post1, Ruff 0.17.3, Pyright 1.1.414.
Python 3.11/3.12 and real HA behavior are not validated by this environment.
Local raw logs live in the ignored `validation/` directory.

| Command, using `.venv/Scripts/python.exe` | Result |
| --- | --- |
| `-m pytest tests/ -q --tb=short` before new tests | 3,435 passed, 11 failed, 11 skipped; 56.73 seconds. |
| `-m pytest tests/ -q --tb=short` final branch | 3,436 passed, same 11 failed, 11 skipped, 5 expected failures; 49.19 seconds, exit 1. |
| `-m pytest tests/test_pwm_coordination_prerequisites.py -q -rx --tb=short` | 1 passed, 5 strict expected failures. These are open safety gates. |
| `-m pytest tests/test_pwm_coordination_prerequisites.py --runxfail -q --tb=short` | 1 passed, 5 failed; direct counterexample reproduction. |
| `-m ruff check custom_components/ tests/` | PASS, exit 0. |
| `-m ruff format --check custom_components/ tests/` | PASS, 238 files already formatted, exit 0. |
| `-m pyright custom_components/adaptive_climate/` | PASS, 0 errors, 0 warnings, 0 informations. |
| `docs/proposals/pump-aware-pwm/tools/check_reference_schedule.py` | PASS: all 10 fixture cases and declared totals; 140% reference arithmetic verified. |
| Production optimizer/runtime and disabled-option equivalence tests | NOT RUN: no runtime or option implemented. |
| I01-I19 full acceptance suite | NOT RUN: prerequisites above are not substitutes for these tests. |
| 24-hour legacy-vs-coordinated simulation and priority latency | NOT RUN: no implemented coordinator to compare; no pump-saving or response-latency claims. |
| Linux Python 3.11/3.12 CI, HACS action, hassfest, pre-commit | NOT RUN. |
| HA runtime, supervised hardware, Raspberry Pi performance | NOT RUN. |
| Wiki update | NOT RUN: no published feature documentation; this is a local engineering safety review. |

All 11 baseline failures are report/weekly-report tests raising
`ValueError: Invalid format string` from `%b %-d` in
`analytics/reports.py:195` on Windows. They predate this change. The baseline
also reports six existing asyncio-mark warnings and an unset fixture-loop-scope
deprecation warning. No unrelated reporting or tooling settings were changed.

The reference checker establishes only interval arithmetic: 5,040 zone-seconds,
3,600 pump-union seconds, zero cyclic steady-state starts, living-room solo
960 seconds and overlap 480 seconds. It is neither an optimizer nor a dynamic
simulation, and it proves no production delivery, safety or hydraulic behavior.

## Changed files, limitations and rollback

The intended committed diff contains only this review and
`tests/test_pwm_coordination_prerequisites.py`. The filled handoff `PR_BODY.md`,
archive contents, virtual environment and raw logs remain local and excluded
from the commit. No new feature is shipped in the HACS integration payload.

There is no activation or deployment procedure for this branch. Independent
PWM continues unchanged because no runtime code is modified. No controller
invariant has been fixed by adding these tests; a green normal invocation with
expected failures must not be presented as safety approval.

Rollback requires no HA action: do not copy the unsupported configuration into
HA, and continue using the existing integration. The tests/review commit can
be reverted in a later Git commit without touching adaptive learning storage.
If the proposal YAML was manually installed, remove that unsupported block and
validate HA configuration before restarting. Do not clear learning storage.
