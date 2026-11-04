# Pump-aware PWM verification

Implementation baseline: upstream `48add428ccc9d356be186f69049526a7d91116c9`
(0.67.0). Development branch: `codex/pump-aware-pwm` in the personal fork
`filou01/ha-adaptive-climate`. No upstream PR has been opened.

The earlier [safety review](pump-aware-pwm-safety-review.md) records the original
counterexamples. They now run as ordinary passing regression tests of the
opt-in actuation path, not expected failures. The historical review's
unimplemented-status statements do not describe this later implementation.

## Architecture

- `pwm_coordination_config.py`: strict standalone schema, disabled default,
  strategy/weight validation and duplicate group-member rejection.
- `pwm_load_balancing_optimizer.py`: pure deterministic circular chain planner
  with exact interval arithmetic. No HA or optimizer dependencies. At most
  16 members; longer unavoidable overlaps favor low-weight edges in minimal
  mode. Maximal mode aligns starts and intentionally trades pump starts for
  concentration where necessary.
- `pwm_pulse.py`: effective pulse reservation from the existing PWM model,
  including pipeline, close offset, minimum times and raw accumulated credit.
- `pwm_load_balancing_manager.py`: protocol-based runtime, one cancellable next
  timer, generation/version guards, monotonic observed-time ledgers, separate
  phase entitlements, urgent requests and latched fallback.
- `pwm_coordination.py`: HA adapters, live post-restoration identity binding,
  output listeners, group compatibility checks and ownership release.
- `heater_actuation.py`: serialized result-bearing controller helper, blocking
  service acceptance, HA state confirmation, cancellation reconciliation and
  partial-failure rollback. The controller remains the public hardware path.
- Existing heater, control, lifecycle, target and mode paths provide narrow
  hooks. Demand/learning bookkeeping still precedes output dispatch. Ordinary
  unconfigured control keeps the original implementation. Valve timers use
  generation guards; opt-in learning timestamps follow observed transitions.

There is no persistence of plan phases, monotonic deadlines or debt and no
adaptive-learning storage migration. Restart reconstructs readiness/state;
unknown elapsed ON time conservatively disengages coordination.

## Reproduction

Install `requirements-test.txt`, Ruff and Pyright in a virtual environment.
Then run:

```text
python -m pytest tests/ -q --tb=short
python -m pytest tests/test_pwm_coordination_prerequisites.py tests/test_pwm_load_balancing.py tests/test_pwm_ha_integration.py tests/test_pwm_simulation.py -q -s
ruff check custom_components/ tests/
ruff format --check custom_components/ tests/
pyright custom_components/adaptive_climate/
```

The simulation emits reproducible JSON metrics; CPU durations vary by host.
Raw local logs are in the excluded `validation/` directory. The fork's
`PWM validation` workflow runs the full suite, lint, formatting and types on
Linux Python 3.11 and 3.12 with repository contents read permission only.

## Immediate-demand coverage

This mapping identifies software coverage, not physical HA/hardware approval.
The protocol runtime and actual heater/adapter boundaries are tested separately.

| Requirement | Regression evidence |
| --- | --- |
| I01, I02, I03 | `test_immediate_eligible_demand_replaces_future_slot`, `test_120_minute_period_does_not_defer_priority`, interactive 24h replays. |
| I04, I05 | `test_i04_i05_zero_demand_never_gets_priority_heat`. |
| I06 | `test_already_on_replan_freezes_preparation_and_single_payment`, real dispatch/common target setter test. |
| I07 | `test_cancelled_demand_cannot_resurrect`, `test_target_reduction_zero_cancels_future_on`. |
| I08 | Generic pause cancellation test plus existing contact/humidity/window suite; full physical contact-to-relay trial NOT RUN. |
| I09 | `test_first_safe_min_off_retry` and retained-credit prerequisite test. |
| I10 | `test_low_duty_is_not_fabricated_and_credit_is_reserved`. |
| I11 | `test_i11_latest_repeated_change_no_duplicate_payment`. |
| I12 | `test_urgent_pulse_crosses_boundary_without_duplicate_start`, full-demand wrap test. |
| I13 | Captured stale callbacks after urgent replacement/removal; generation and serialization tests. |
| I14 | `test_force_off_wins_over_inflight_start`, `test_force_off_revokes_waiting_state_confirmation`. |
| I15 | `test_priority_living_room_accepts_overlap_with_active_small_zone`. |
| I16 | `test_i16_ordinary_pid_change_uses_phase_not_priority`. |
| I17 | `test_real_dispatch_uses_one_writer_and_common_setpoint_setter`; actual HA automation/preset service end-to-end trial NOT RUN. |
| I18 | Effective-duration test with real pipeline committed heat covering demand. |
| I19 | `test_fallback_during_priority_does_not_cycle_other_active_output`, unavailable/failure ownership-release tests. |

Additional checks cover the 0/40/80/100/140/250/400% pure fixtures, exact
per-zone duration, deterministic results, invalid numbers/schema, effective
valve/minimum timing, real controller dispatch, late callbacks, shared outputs,
rename/removal, shutdown, low credit and failed commands.

## 24-hour simulations

Eight deterministic replays compare the actual legacy `PWMController` with
the production group runtime: two strategies × two workloads × fixed/interactive
traces. Legacy zones start independently phased at 0/900/1800/2700 seconds;
both runs start with outputs OFF. Legacy control ticks every 30 seconds;
coordinated timers run at exact simulated deadlines.

The input durations are already effective electrical seconds with zero valve
travel, zero transport delay and zero minimum times. Thermal feedback, room
temperature and hydronic flow are not simulated. Separate integration tests
cover real effective-duration preparation; the replays do not establish
overnight behavior with nonzero minimum times or low-duty accumulation.

Interactive traces switch zone 4 OFF at 06:00, back to HEAT at 08:17 and raise
zone 1's target/duration at 12:17. The two eligible event-response latencies
are zero simulated seconds in both legacy and coordinated runs.

| Effective demand | Strategy | Legacy starts | Coordinated starts | Legacy energized s | Coordinated energized s |
| --- | --- | ---: | ---: | ---: | ---: |
| Fixed 140% | minimal | 1 | 1 | 86400 | 86400 |
| Fixed 140% | maximal | 1 | 24 | 86400 | 34560 |
| Interactive 140% | minimal | 19 | 4 | 64080 | 84960 |
| Interactive 140% | maximal | 19 | 24 | 64080 | 39900 |
| Fixed 80% | minimal | 96 | 24 | 69120 | 51840 |
| Fixed 80% | maximal | 96 | 24 | 69120 | 17280 |
| Interactive 80% | minimal | 54 | 25 | 52080 | 63000 |
| Interactive 80% | maximal | 54 | 26 | 52080 | 30960 |

At fixed 80%, both implementations deliver exactly 17280 electrical seconds
to every zone over the day, with zero pending/cancelled balance. This is the
clean demonstration of fewer starts without suppressed heat.

At fixed 140%, coordinated minimal delivers 34560/25920/25920/34320 seconds
(rounded); 240 seconds remain in the wrapping final pulse. Delivery plus
pending credit equals the same 34560/25920/25920/34560 seconds as legacy.
Maximal delivers those totals with no pending balance.

At interactive 80%, both strategies and legacy deliver
30240/17280/17280/15840 seconds. At interactive 140%, minimal delivers
38880/25920/25920/31200 seconds (rounded), with 240 seconds pending and
240 seconds explicitly cancelled on OFF. Legacy delivers 31680 seconds to
zone 4; these differing window/cancellation positions must not be presented
as exact delivered-heat parity or an isolated start-saving proof for that
trace. Maximal delivers the same electrical totals as legacy, but more starts.

Measured maximum ordinary start deferrals are 2400 seconds (140% minimal)
and 1440 seconds (80% minimal), within the simulated 7200-second limit.
Maximal deferral is zero for these fixtures. Runtime per 24h replay was about
0.2–0.4 host CPU seconds; Raspberry Pi performance is NOT RUN. All counters
are estimates from configured electrical outputs, not measured pump feedback.

## Validation status and limits

The final release notes record exact commands, counts, commit and CI links.
Do not infer hardware approval from a passing simulation or repository check.

Final source commit: `254b878cec851ca48da8fca89b600618a8a36052`.
Local Linux release checks use Ubuntu/WSL and project-local environments.

| Validation | Measured result |
| --- | --- |
| Linux CPython 3.11.18, full pytest, cache plugin disabled | 3519 passed, 11 skipped, 6 existing warnings; 59.70 s; exit 0. |
| Linux CPython 3.12.3, full pytest, cache plugin disabled | 3519 passed, 11 skipped, 6 existing warnings; 59.21 s; exit 0. |
| Targeted PWM suite on Windows | 73 passed; exit 0. |
| Windows CPython 3.14.5, full suite | 3508 passed, 11 existing report-format failures, 11 skipped; 51.13 s; exit 1. |
| Ruff 0.17.3 check | PASS. |
| Ruff format check | PASS, 247 files already formatted. |
| Pyright 1.1.414 | PASS, 0 errors, 0 warnings, 0 informations. |
| Handoff reference checker | PASS, 10 declared scenarios and 140% interval arithmetic. |
| [HACS action, latest source](https://github.com/filou01/ha-adaptive-climate/actions/runs/41868272354) | PASS after enabling issues and adding repository topics required by HACS. No checks suppressed. |
| [hassfest, latest source](https://github.com/filou01/ha-adaptive-climate/actions/runs/41868272578) | PASS. |
| [GitHub Linux matrix, latest source](https://github.com/filou01/ha-adaptive-climate/actions/runs/41868272539) | Both `test (3.11)` and `test (3.12)` jobs completed successfully, including pytest, Ruff and Pyright. |

The eleven skipped tests and six warnings also occur in the existing suite;
they are not expected-failure exemptions for the PWM feature. No new PWM test
is xfailed. The local Linux cache plugin was disabled only to avoid NTFS/WSL
cache-path permissions; test collection and execution are otherwise unchanged.

- Local Windows full suite: existing report tests fail on `%b %-d`; no unrelated
  reporting fix is included. Final counts are recorded with the release.
- Local targeted PWM tests, Ruff, formatting and Pyright: executed; final
  results recorded with the release.
- Linux Python 3.12, Linux Python 3.11, HACS, hassfest: check the final release
  result matrix; queued or unexecuted checks are explicitly NOT RUN.
- Real Home Assistant instance, physical relays/pump, supervised 24h hydronic
  trial and Raspberry Pi measurements: NOT RUN.
- Variable 5–15% maintenance trace with real minimum times and fault injection:
  NOT RUN as a 24h comparison. Short deterministic low-duty tests are separate.
- Wiki publication: NOT RUN; fork documentation is kept in this repository.

Read [configuration, compatibility and rollback](../pump-aware-pwm.md) before
installing a preview. No production configuration is changed by these files.

## Changed files

```text
.github/workflows/pwm-validation.yml
README.md
custom_components/adaptive_climate/__init__.py
custom_components/adaptive_climate/climate.py
custom_components/adaptive_climate/climate_state_setters.py
custom_components/adaptive_climate/managers/control_output.py
custom_components/adaptive_climate/managers/heater_actuation.py
custom_components/adaptive_climate/managers/heater_controller.py
custom_components/adaptive_climate/managers/heater_cycle_bookkeeper.py
custom_components/adaptive_climate/managers/heater_service_caller.py
custom_components/adaptive_climate/managers/heater_timers.py
custom_components/adaptive_climate/managers/pwm_controller.py
custom_components/adaptive_climate/managers/pwm_coordination.py
custom_components/adaptive_climate/managers/pwm_load_balancing_manager.py
custom_components/adaptive_climate/managers/pwm_load_balancing_optimizer.py
custom_components/adaptive_climate/managers/pwm_pulse.py
custom_components/adaptive_climate/managers/state_attributes.py
custom_components/adaptive_climate/pwm_coordination_config.py
docs/pump-aware-pwm.md
docs/architecture/pump-aware-pwm-overlap-policy.md
docs/architecture/pump-aware-pwm-pr.md
docs/architecture/pump-aware-pwm-safety-review.md
docs/architecture/pump-aware-pwm-verification.md
tests/test_pwm_coordination_prerequisites.py
tests/test_pwm_ha_integration.py
tests/test_pwm_load_balancing.py
tests/test_pwm_simulation.py
```

The proposal archive, private configuration examples, original prompts, raw
logs, test environments and interpreter downloads are excluded from commits.
No version number, integration domain or learning-store schema is changed.
