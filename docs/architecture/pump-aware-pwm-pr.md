# feat: optional pump-aware HEAT PWM coordination

Independent zone PWM can start a shared electrically OR-controlled pump many
times per day. This change adds disabled-by-default group scheduling with
minimal overlap (spread pulses, favor high-weight solo time) or maximal overlap
(concentrate pulses, potentially trading more pump starts for less runtime).

**An eligible setpoint increase or OFF->HEAT transition is evaluated immediately
and is never delayed to the next coordinated PWM slot; subsequent pulses are
optimized.** Existing safety, genuine demand, minimum switching times and duty
accumulation remain authoritative. Old reservations are revoked and observed
electrical seconds pay the delivery ledger once.

The pure bounded planner issues no HA calls. A domain registry binds live
post-restoration entities to protocol-based group managers. Each group owns one
cancellable next-event timer; controller commands, mode/pause cancellation and
fallback use version checks and a serialized result-bearing heater helper.
Failed/rejected commands do not consume raw credit or emit successful learning
events. Valve/pipeline timestamps follow observed electrical transitions.

The initial preview supports same-period HEAT-only PWM with one non-inverted
`switch.*` or `input_boolean.*` output per zone. Helper proxies report requested
HA state, without downstream relay/network feedback. Unsupported modes/outputs, shared relays, unavailability,
unknown startup ON elapsed time and runtime failure disengage the group with
diagnostics. Unconfigured/disabled installations keep their independent path;
there is no optimizer dependency or pump relay control. The general learning
hotfixes additionally migrate learner payload v11 to v12 to persist its cooldown
cycle counter without discarding completed cycles or confidence.

Configuration, topology assumptions, diagnostics and rollback are in
[the user guide](../pump-aware-pwm.md). Full architecture, changed-file list,
I01–I19 coverage mapping and measured simulation results are in
[the verification report](pump-aware-pwm-verification.md).

The change also integrates the supplied fixes for upstream issues #6 and #7:
transient learning sessions restart consistently, zero/tiny PWM demand shares
one settling deadline, and PID recommendation diagnostics use actual gains.
Recommendation previews preserve cooldown credit; successful application commits
it. Both heater paths are covered. Repeated maintenance output above the 2%
threshold remains outside these narrow fixes. See [hotfix scope and exact-source
validation](../learning-hotfixes.md).

Parallel zone setup now serializes shared learning-store initialization and
restoration before publication, preventing duplicate learning-window number
registration and multiple initial store instances. Six deterministic startup
regressions cover concurrent load/restoration, errors and cancellation.
See [the startup fix report](../learning-startup-fix.md) for exact-source CI links.

Preview 4 accepts `input_boolean` relay proxies (including NSPanel/ESPHome)
through the same controller service and confirmation path. Both domains and
mixed groups are tested; unsupported analog output domains remain rejected.
See [the current compatibility and verification report](../input-boolean-pwm.md).

Preview 5 marks the HA timer, output listener and actuator-confirmation
callbacks for nonblocking event-loop dispatch, correcting executor-thread
access to task creation and scheduler/actuator state. Six new modeled-dispatch
regressions cover both binary domains. The separate dt discrepancy diagnostic
and PID timing remain unchanged; see [the callback fix report](../pwm-callback-safety.md).

Preview 6 adds a versioned per-group PWM journal in the existing HA Store.
It restores period budgets, known delivered time, last known output edges,
low-duty credit and waiting priority/deadline state. Write-ahead ON intents and
post-confirmation checkpoints prevent duplicate ordinary pulses after restart.
Unknown offline delivery is withdrawn into a separate uncertain balance rather
than claimed as measured heat. Failed persistence blocks ON and requests safety
OFF through HeaterController. Partial entity startup retains unbound rows.
See [architecture, changed files, evidence and limitations](../pwm-restart-safety.md).
The initial upgrade has no past journal; independent fallback retains legacy
restart behavior. There is no optimizer dependency or learning reset.

## Validation

- Linux Python 3.11.18: **3628 passed, 11 skipped**, full suite, exit 0.
- Linux Python 3.12.3: **3628 passed, 11 skipped**, full suite, exit 0.
- New PWM restart/storage regressions and simulations: **50 passed**.
- New shared-startup regressions: **6 passed** in each full suite.
- New learning hotfix regressions: **29 passed** in each full suite.
- Targeted PWM regressions: **147 passed**, no xfails.
- Ruff check/format and Pyright: **PASS**.
- HACS and hassfest: **PASS** for the preview 6 source commit.
- GitHub Linux 3.11/3.12 matrix: **PASS**, including full tests, lint, format
  and types. Exact-source links and local results are in the restart report.
- Four additional 24h persistence replays: switch/input_boolean, with zero or
  143 unclean restarts. All preserve 36000 ON seconds per zone, 24 starts and
  66240 group ON seconds, with zero ending debt. Unconfirmed budget is reported
  separately from known observed delivery. Physical behavior is not measured.
- Eight 24h runtime-vs-real-legacy-PWM replays: **PASS** for the measured model.
  At fixed 80% demand, starts fall from 96 to 24 and all four zones receive
  exactly 17280 electrical seconds, with zero debt. At fixed 140%, minimal
  preserves a continuously energized cyclic group; maximal reduces runtime
  but increases starts. Both interactive event latencies are zero simulated
  seconds. Model/finite-window qualifications are explicit in the report.
- Windows real-controller restart/storage regressions: **50 passed**.
  Full Windows suite for preview 6: **NOT RUN**. Preview 2 had 3538 passed,
  11 skipped and 11 pre-existing report-format failures (`%b %-d`).

**NOT RUN:** real HA automation/preset-to-device end-to-end trial, physical
relays/pump/flow, supervised 24h hydronic run with real minimum times, Raspberry
Pi CPU measurement, variable maintenance-duty 24h replay with real actuator
timing, and wiki publication. Stub/protocol tests do not replace these trials.

## Rollout and rollback

Publish only a clearly marked preview in the personal fork. Keep the feature
disabled initially, preserve learning storage, verify ordinary behavior and
then perform a supervised trial with correct entity IDs and outputs OFF at
startup. Remove the coordination block or set `enabled: false` and restart to
return to independent PWM, which retains legacy restart timing. The first
preview-6 upgrade has no earlier journal; start with outputs OFF and let minimum
OFF elapse before resuming HEAT. Reinstall the recorded upstream version if needed;
do not reset adaptive learning.

No PR is automatically opened upstream. Before an upstream PR, retain reusable
code/tests/docs and adjust fork-specific installation, badge and engineering
history references for the upstream repository. The source version remains
semantic-release managed at its upstream baseline; the fork preview is
identified by its Git tag and exact commit.
