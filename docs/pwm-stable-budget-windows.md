# Stable budget windows (PWM previews 16 and 17)

Preview 16 separates the entitlement clock from hydraulic execution.
The PWM duration comes from the registered adapters; 3600 seconds is not a
production constant. Acceptance cases also exercise 1800 and 7200 seconds.

## Entitlements

The first eligible allocation establishes a release lattice. A new allocation
advances `next_budget_at` by whole PWM periods on that lattice. An ordinary
observed ON edge consumes its reservation and updates observed start history,
but does not change the lattice. A priority transaction may explicitly establish
a new cadence, preserving the existing priority allowance policy.

Active ordinary pulses and unstarted positive reservations cannot receive an
additional period allocation. Missed offline releases are not a backlog.
Signed minimum-ON debt, closed PID revisions, accumulator debits, actual-period
start quotas and pre-command persistence barriers remain authoritative.

A delayed preceding reservation may already have used the current observed
start period. A still-serviceable following budget waits for that quota to
reopen. It must not be minted and discarded merely because its release occurs
before the next observed-period boundary. Physically expired opportunities can
be skipped without joining two period budgets into one running pulse.

## Execution

The existing bounded runtime repair receives flexible windows for ordinary
reservations. Earliest execution respects minimum OFF and any conservative
restart guard. Latest execution is bounded by maximum deferral and the stable
budget end **minus the complete effective remaining pulse**, including minimum
ON. The cyclic phase is a preference inside these bounds.

The optimizer can therefore reorder low load into short handovers. At overload
it must overlap complete pulses instead of extending their budget windows.
Active intervals are never moved or cut by the optimizer. Full heat deadlines
bound the search; minimizing pump starts does not authorize missing them.

If minimum switching times or newly arriving demand make completion inside a
window impossible, earliest safe execution wins. Diagnostics expose that
exception. There is no claim of a global combinatorial optimum, or of feasible
delivery above physical minimum-OFF capacity.

## Recovery and diagnostics

The version-1 journal gains optional `budget_anchor_at`, `period_delivered`
and `recovery_not_before` fields. Legacy journals retain their recorded next
release, signed balances and start quota. An absent period-delivery observation
is reported as unknown until a new allocation. Missed offline releases advance
on the old lattice. Uncertain or legacy start timestamps retain a conservative
guard independently of the budget clock. Invalid new fields fail closed.

PWM preview 17 records `zero_revision_known` only when a positive, eligible
demand prepares zero pulse seconds during an already-started allocation. A
return to a larger pulse while the relay is still ON revises that allocation
once. The revised credit still accounts for observed ON time and inherited
signed debt. The field is optional in the version-1 journal. A missing field
retains conservative handling for older erased baselines, including v12.

Recovery retains this proof for an unexpired reservation when the saved and
current output are both ON and there is no unresolved command. Time spent
offline counts as uncertain consumption, bounded by one configured period,
and is booked as cancellation. Only observed ON time counts as delivery.
An OFF edge, mismatched state or expired reservation clears the proof. If an
expired output is still ON, ordinary demand waits for its minimum ON and OFF
guards before starting the current budget. Continuous demand retains its direct
response and missed releases are skipped on the existing lattice.

`budget_period_drift_seconds` measures deviation from the established release
lattice, not missing-period count. Use observed delivery and quota tests with
it. `requested_period_budget_seconds` is the nominal revised allocation;
`delivered_period_budget_seconds` is observed ON time since its allocation.
Carried signed debt can make those values differ even for correct execution.
`unmet_period_budget_seconds` is remaining positive credit, not a thermal-loss
measurement. Existing signed-balance and cancellation diagnostics remain.

`runtime_window_in_seconds` exposes earliest, preferred due, latest and budget
end relative to now. `runtime_window_constraint` distinguishes impossible
minimum/late-arrival windows from hydraulic waiting. Actual start delay is
measured from positive-credit availability. Observed group starts count logical
heater-request union edges, not physical pump or valve telemetry.

No additional periodic persistence task or diagnostic-only write is introduced.
Active delivery retains the existing durable accounting policy. Better
serialization can increase the time with at least one active output and hence
the number of existing active checkpoints; compare benchmark write counts.

## Validation

`tests/test_pwm_budget_phase_independence.py` checks actual executed intervals:
stable low load, return after pause, demand growth, 80-minute overload, six
load changes, hydraulic weight, signed-debt/minimum-pulse reproduction,
impossible switching windows, shifted quota, legacy recovery and corrupt state.
It combines delivered heat, pump starts, overlap bounds and entitlement anchors.

The v15 changing-load test now checks fixed release times and one actual pulse
per observed period, allowing execution phases to adapt. The stable-load test
still requires exactly one PWM period between starts and full heat delivery.
Safety tests are retained. The electrical replay auditor checks ordinary start
quotas and runtime budget deadlines instead of assuming all phase changes must
keep at least one full PWM period between actual starts.

`tests/test_pwm_subminimum_return.py` checks a positive demand dip with real
switch and input-boolean adapters. It verifies the revised entitlement, the
next period's usable heat, and recovery with elapsed offline time, pending
commands and expired windows. The replay auditor also checks that eligible
ordinary revisions while ON do not cancel the returned entitlement.

Reproduce synthetic version comparisons from the repository root:

```powershell
python tools/compare_pwm_versions.py --output /path/to/local/evidence
python -m pytest tests -k 'pwm or hydraulic' -q
$env:PWM_BENCHMARK_OUTPUT='/path/to/local/benchmarks'
python -m pytest tests/test_pwm_persistence_benchmark.py -q
```

The comparison loads exact pwm.14, pwm.15 and pwm.16 manager revisions from git and
uses their unchanged common runtime planner/optimizer. It reports complete
observed intervals and integrated union/overlap, not just cyclic preferences.
Private HA recorder inputs are never included in the repository.
