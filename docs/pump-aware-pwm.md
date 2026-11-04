# Pump-aware PWM coordination (preview)

This fork implements optional phase coordination for heating zones whose single
binary switch outputs energize a shared pump through an existing electrical OR.
The feature is disabled by default. It controls zone timing, not the pump relay,
water flow or heat-pump speed. Keep the integration domain `adaptive_climate`.

**Preview status:** software tests and simulation evidence are in the
[verification report](architecture/pump-aware-pwm-verification.md). This is a
supervised-test candidate, not a claim of validation on your heating equipment.

## Configuration

Without this block, or with `enabled: false`, existing independent control is
used. No group scheduling timers or listeners are created when disabled.

```yaml
adaptive_climate:
  pwm_coordination:
    enabled: false  # Enable explicitly only when preparing a monitored trial.
    mode: load_balancing
    groups:
      - name: heating_pump
        overlap_strategy: minimal
        handover_overlap_seconds: 240
        max_deferral_seconds: 3600
        zones:
          - entity: climate.zone_a
            hydraulic_weight: 4.0
          - entity: climate.zone_b
            hydraulic_weight: 1.0
          - entity: climate.zone_c
            hydraulic_weight: 1.0
          - entity: climate.zone_d
            hydraulic_weight: 1.0
```

Merge this into your existing `adaptive_climate:` block; do not duplicate the
top-level key. Use actual climate entity IDs, including registry suffixes.
Weights of 1 are illustrative and do not establish any room's real loop count.

| Setting | Meaning |
| --- | --- |
| `enabled` | Strict Boolean, default false. |
| `mode` | Only `load_balancing` is supported. |
| `groups[].name` | Unique nonempty group name, one physical pump per group. |
| `overlap_strategy` | `minimal` (default) or `maximal`. |
| `handover_overlap_seconds` | Finite 0–1800 seconds, default 240; a target within genuine demand, not extra heater runtime. |
| `max_deferral_seconds` | Finite 0–7200 seconds, default 3600; ordinary phases only. Does not defer urgent demand. |
| `zones` | 2–16 explicit climate entities, unique across all groups. |
| `hydraulic_weight` | Finite, strictly positive; default 1. Ranks concurrency preference, not physical flow. |

Unknown options, duplicate membership, invalid entity IDs and nonfinite numbers
are rejected. Runtime validates actual output identity, period and readiness.

## Choosing overlap

`minimal` arranges a contiguous group run with small handovers, puts the
highest-weight zone first and assigns unavoidable longer overlaps to small
zones. Pump energized runtime can increase relative to concentrating pulses.
At total demand above 100%, long overlap can be mathematically unavoidable.
The 140% reference has a continuous cyclic union and eight minutes of overlap
touching the high-weight zone in each hour.

`maximal` aligns ordinary pulse starts to concentrate the same requested ON
time into a shorter group run. It prioritizes concurrence over high-weight
solo time. It can increase pump starts compared with an already continuous
independent workload. It is not a universal pump-start-minimizing mode.

Both modes preserve the hard safety/delivery rules. Neither adds heat to fill
a pump gap. Handover overlap is electrical overlap; it proves no hydraulic flow.
Changes to group configuration or strategy require a Home Assistant restart.

## Immediate demand and accounting

An eligible setpoint increase or OFF->HEAT transition is evaluated immediately
and is never delayed to the next coordinated PWM slot; subsequent pulses are
optimized. Real demand, output availability, pauses and original minimum-cycle
constraints remain authoritative. A minimum-OFF-blocked urgent pulse is retried
at its first eligible instant. Low duty must earn its original accumulator
credit; a target change cannot invent a minimum pulse.

The coordinator reserves effective electrical duration from the original PWM
model, including committed heat, valve travel, early close and effective
minimum ON time. Phase-only replanning reuses that reservation. Observed ON
seconds pay a ledger; a displaced reservation is not played twice. A fresh
eligible target transaction can authorize a new legacy pulse after an earlier
quantum has finished, without erasing already delivered history.

Wrapped pulses carry their remaining credit across the global boundary. The
next entitlement belongs to the zone's next phase, avoiding a duplicate quantum
at the boundary. Delayed callbacks charge elapsed ON time, including overruns;
negative balances offset subsequent demand. OFF/blocked demand withdraws the
remaining reservation and reports the cancelled balance separately.

All commands enter `HeaterController`. Configured supported zones use a
serialized command path with explicit results, bounded service/state waits,
post-await invalidation checks and HA output-state confirmation. Credit and
learning state are not committed for rejected or failed starts. Cancellation
cannot retract a command already sent to a device: an obsolete in-flight ON
is reconciled OFF through the same controller. HA state is an electrical-state
estimate, not proof of valve position or physical heat.

## Compatibility and fallback

| Installation | Behavior |
| --- | --- |
| Feature absent or disabled | Existing independent path. |
| Same-period, HEAT-only PWM, one non-inverted `switch.*` per zone | Supported preview configuration. |
| HVAC OFF or paused zone | Never used to fill a gap; stale ON reservations are invalidated. |
| Direct 100% demand | Immediate eligible ON, continuous while demand remains full. |
| Cooling, AC, HEAT_COOL, analog valve (`pwm: 0`) | Not coordinated; independent fallback. |
| Multiple outputs or separate demand switches on one zone | Not coordinated in this first preview; existing hardware path retained. |
| Mixed/nonpositive periods, duplicate physical outputs, effective min-ON + min-OFF exceeding period | Group falls back with a reason. |
| Missing members | Independent control until actual entity/controller readiness. |
| Unavailable output, entity rename/removal or scheduler failure | Pending group callbacks revoked; independent ownership restored without mass OFF/ON. |
| Startup ON with unknown elapsed time | Conservative fallback; start the monitored trial with group outputs OFF. |

Fallback is latched for the group until restart. Do not repeatedly toggle
settings to hide a recurrent fault; inspect the exposed reason. No learning
storage migration, PID gain reset, obsolete `loops` key or pump-flow-control
dependency is introduced. Unconfigured zones are not scheduled.

## Installing the preview from the fork

1. Back up the existing integration files, YAML configuration and adaptive
   learning storage. Record the current upstream version for rollback.
2. In HACS, use the fork URL
   `https://github.com/filou01/ha-adaptive-climate` as a custom repository of type
   **Integration**. Replace the upstream repository entry rather than installing
   two integrations with the same domain. See
   [HACS custom repository documentation](https://hacs.dev/docs/faq/custom_repositories/).
3. Select the explicitly published PWM preview release rather than the fork's
   upstream-baseline `main`. Enable prerelease visibility if necessary. The
   release notes identify its exact tag, checks and remaining validation gaps.
4. Restart HA with coordination absent/disabled and verify ordinary operation.
5. For a monitored trial, first switch the participating thermostats to OFF
   through HA and confirm their outputs are OFF. Set `enabled: true`, verify
   actual member IDs and equal positive periods, then restart HA. Resume HEAT
   on the participating thermostats and watch the electrical outputs.
6. Test a mid-period setpoint increase and OFF->HEAT. Confirm immediate eligible
   electrical response and monitor temperatures, minimum times and diagnostics.

This page is not a declaration that a particular release has passed tests;
use its verification report. No automatic change is made to your HA instance.

## Diagnostics and rollback

Each participating climate entity exposes a bounded `pwm_coordination`
attribute: group mode/reason, strategy, generation, estimated pump starts and
energized time, projected/observed overlap, requested/observed/cancelled time,
outstanding debt, ordinary deferral and priority latency/blocking information.
Priority latency is command-response timing in the simulation or HA boundary;
it is not time until water reaches the room. No real pump-state sensor is read.

To return to independent PWM, set `enabled: false` or remove the block and
restart Home Assistant. If necessary, reinstall the recorded known-good
upstream release and restore its configuration. Preserve adaptive learning
storage; no reset or migration is required.
