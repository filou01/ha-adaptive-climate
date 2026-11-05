# Executable minimal-overlap handovers — preview 8

`v0.67.1-pwm.8` repairs avoidable group OFF gaps when nominal cyclic phases
do not describe executable pulses. The `minimal` strategy remains intentional:
fewer group starts first, then short genuine handovers and high-weight solo
time. It does not change to concentrated/maximal overlap.

## Root cause and reproduced failures

Previously the cyclic planner received nominal `allocation`, while execution
used signed remaining credit, minimum times and period start allowances.
A spent allocation could still occupy an ideal plan interval. A minimum-OFF
delay moved only its own start. An ordinary request arriving after its nominal
phase started immediately, even just before a usable neighboring next period.
The ideal `projected_cyclic_starts` therefore did not describe the executable
remaining schedule.

Three regressions failed against unmodified preview 7 before implementation:

| Case | Before | Feasible repaired placement |
| --- | --- | --- |
| Nominal A 1200s with -600s prior overdelivery; B 900s | A 0–600, B 960–1860: 360s gap, two starts | A 0–600, B 360–1260: 240s handover, one start |
| A 1200s; B 900s with known earliest ON at 1500 | A 0–1200, B 1500–2400: 300s gap, two starts | A 540–1740, B 1500–2400: one start |
| B requests 600s at t=2990; A next authorized at 3600 | B 2990–3590: 10s gap before A | B 3240–3840: 240s handover to A |

All examples use a 3600s period, a 240s handover target, genuine effective
electrical durations and a 3600s ordinary deferral limit. Minimum-ON is 600s;
minimum-OFF is 600s except B's explicitly modeled 1600s in the second case.
The repaired schedules deliver identical ON seconds, keep the minimum times
and spend at most one ordinary allowance per zone/group-origin epoch.

These are controlled software counterexamples. They are not a complete replay
of the installation's changing temperature/PID history. If genuine demand
disappears before a planned transition, a group gap may be unavoidable.

## Implementation and limits

The cyclic planner still supplies steady-state phases and next-budget timing.
A separate pure `pwm_runtime_planner.py` receives one absolute window per zone:

- Current ON intervals are fixed, including remaining minimum-ON and signed
  budget effects. An expiring output is represented by a 1ms boundary marker
  only so the existing ON-before-OFF transaction order can preserve continuity.
  This marker never adds commanded heat or changes OFF timing.
- Unstarted ordinary reservations use real credit and effective minimum-ON,
  earliest start after minimum-OFF, the original deferral deadline, and the
  current epoch/allocation boundary. They may move only inside those bounds.
- A closed eligible neighbor's next usable budget can be a fixed advisory
  opportunity in the following period. It is not delivered heat, new credit,
  or permission to issue an unconditional future command. Current eligibility
  and the real entitlement are checked again before every ON.
- Priority and direct-100% windows are fixed at their earliest safe start.
  Already active valves are never cycled for phase alignment. Closed ordinary
  reservations still cannot reopen in the same epoch.

Two deterministic coordinate passes consider placements at interval handovers,
original/previous starts and earliest bounds. The ordered score is remaining
union starts, feasible handover shortfall, high-weight concurrency, weighted
concurrency and movement. Small-zone moves are considered first. The bound is
16 windows and O(n^4); it is a local repair, not an exhaustive global optimum.
Forecast changes can invalidate a planned bridge. No future thermal demand or
physical flow is guaranteed. `maximal` keeps its existing placement policy.

All commands still pass through the existing serialized HeaterController,
journal checks, output confirmation and generation/eligibility guards. No
ledger or restart schema changes, learning reset, PID gain change, outside-term
change or configuration migration is introduced. Repaired starts are transient
plans, reconstructed after restart from the existing durable budgets/deadlines.

## Diagnostics

| Field in `pwm_coordination` | Meaning |
| --- | --- |
| `runtime_projected_starts` | Components in the remaining absolute plan, including advisory next-period opportunities; not a measured count or a daily/cyclic total |
| `runtime_start_in_seconds` | Planned current reservation start delay; null without a current pending start or while already ON |
| `runtime_plan_reason` | `ordinary_slot`, `handover_wait`, `handover_advance`, `already_on`, `priority_or_continuous`, `no_reserved_demand`, or `start_quota_or_balance` |

Existing `projected_cyclic_starts` and `projected_high_weight_overlap_seconds`
remain **ideal steady-state cyclic** metrics. Observed `estimated_pump_starts`
and energized/overlap counters continue to use actual configured output states.
Neither projected metric proves a physical pump or hydraulic transition.

## Automated test plan and acceptance

New tests live in `tests/test_pwm_runtime_handover.py`.

| Test group | Acceptance |
| --- | --- |
| Three root-cause regressions | Exact real output edges match the repaired schedules above; same per-zone delivery and balanced signed ledgers |
| Real HA adapter/controller boundary | Both switch and input_boolean hand over using remaining credit and actual effective valve/minimum timing |
| Priority, both strategies | A genuine target transition is immediate even when an ordinary pulse would wait for a handover |
| Maximal compatibility | Late ordinary demand retains the existing concentrated policy |
| Deadline/replanning | Repeated updates cannot move the original deadline; a shorter feasible overlap wins over starvation |
| Cancellation and stale timer | Withdrawn demand cannot execute an old planned ON |
| Forecast withdrawal | A speculative neighboring budget cannot cause an unconditional ON after demand disappears |
| Same-transaction expiry | Genuine successor ON occurs before predecessor OFF without extra heat or a new group start |
| Running-budget revision | Shorter remaining demand moves the successor, never restarts or extends the predecessor |
| 20 deterministic 16-zone cases | Durations, switching bounds and frozen windows preserved; score never worsens; deterministic result and broad CPU guard |
| Invalid numeric targets | Nonfinite/negative handover values rejected |
| 24h ordinary-demand replay | Same input and initial state with/without executable repair; exact delivery, ordinary epoch quota, starts, overlap and ending credit checked |

The replay uses 24 hourly late ordinary requests plus 1800s drain time to
include the final wrapped pulse. Both runs use 600s minimum ON/OFF. The baseline
is the same group runtime with the executable repair disabled, **not** the
independent upstream PWM implementation.

| Measured replay result | Nominal-only placement | Executable minimal repair |
| --- | ---: | ---: |
| Group starts, including initial start | 49 | 25 |
| Zone A delivered seconds, including drain | 30000 | 30000 |
| Zone B delivered seconds | 14400 | 14400 |
| Ending signed credit, both zones | 0 / 0 | 0 / 0 |
| High-weight concurrency seconds | 0 | 5760 |
| Maximum ordinary starts per zone/epoch | 1 | 1 |

The additional 240s handovers trade high-weight solo time for fewer starts, in
the specified priority order. They do not increase per-zone delivered ON time.
This is deterministic electrical scheduling, without thermal feedback, network
latency, physical valves or pump sensing; it does not promise these savings in
every installation or changing-demand workload.

Run validation with the repository test dependencies:

```text
python -m pytest tests/test_pwm_runtime_handover.py -q -s
python -m pytest tests/ -q --tb=short -p no:cacheprovider
ruff check custom_components/ tests/
ruff format --check custom_components/ tests/
pyright custom_components/adaptive_climate/
```

The existing PWM simulation, entitlement, restart, callback and HA-boundary
suites must also pass. The observed-epoch attribution test explicitly disables
optional ordinary deferral so it continues to isolate edge attribution rather
than prescribe a phase placement that this fix is intended to optimize.

### Validation evidence

Before-fix reproduction: **3 failed**, matching all three original gaps.
New handover suite: **37 passed** under Windows Python 3.12.14.
Ruff check/format and Pyright: **PASS**. Final full-suite counts, exact source
commit and Linux/HACS/hassfest links will be recorded after GitHub validation.

**NOT RUN:** installed-HA/device end-to-end validation, physical relay/pump/flow
checks, supervised 24h heating, real power loss/OS cache tests, Raspberry Pi
performance/SD-write/save-latency measurements and wiki publication. Existing
temperature-dependent outside-term switching and broader maintenance-learning
behavior are unchanged. No claim that every historical live gap is avoidable.

## Supervised installation test plan

1. Preserve integration/configuration/learning backups and record preview 7 for
   rollback. For the monitored upgrade set participating thermostats OFF and
   verify their outputs OFF. Install preview 8 in HACS prereleases, restart HA
   and resume HEAT. Keep the existing `minimal` YAML and zone weights.
2. Confirm group `mode: active`, strategy `minimal` and no fallback reason.
   Capture actual helper/switch edges, requested/observed/cancelled seconds,
   signed credit, ordinary epochs and the new runtime diagnostics.
3. Observe ordinary pulses with negative signed carry and minimum-time guards.
   Where feasible, the successor should connect to the actual predecessor's
   remaining pulse or a permitted next-period neighbor. No duplicate ordinary
   start is allowed merely because a minimum-OFF guard expired.
4. Separately raise an effective target and test OFF->HEAT. A genuine eligible
   pulse must start immediately or at the existing first safe minimum-OFF time.
   It must not wait for an optimized handover. Check priority counters.
5. Withdraw demand/pause a zone while it waits. No stale scheduled ON may occur.
   Check a pulse crossing a period boundary and verify no artificial OFF/ON.
6. Compare at least a full day of observed output histories and room comfort.
   Record unavoidable gaps and changing-demand context. Boolean helpers alone
   do not confirm NSPanel/ESPHome delivery; inspect downstream relay feedback
   separately if available. Do not infer physical pump savings from projections.

These are a deployment test plan, not tests already performed in the user's HA.
No automatic HA installation or restart is part of publishing this release.

## Rollback and changed files

Disable coordination and restart for the existing independent path, or reinstall
preview 7 and restart. Existing YAML, learner data and PWM journal v1 remain
compatible. Preview 7 restores nominal-only placement and the reproduced gaps.
Do not erase learning or signed budgets to conceal a planning problem.

- `managers/pwm_runtime_planner.py`: pure bounded executable-interval repair.
- `managers/pwm_load_balancing_manager.py`: project actual constraints and
  advisory opportunities, apply repaired ordinary start times, diagnostics.
- `managers/pwm_coordination.py`: expose effective minimum-ON through the adapter.
- `tests/test_pwm_runtime_handover.py`: reproduction, regression and daily replay.
- Shared simulation adapter: expose its minimum-ON contract.
- One existing attribution test: isolate its original focus with zero deferral.
- README, user guide and combined PR description: preview 8 documentation.
