"""Audit recorded inputs with the production scheduler and electrical pulse model.

Input JSON: duration, origin (relative group phase), min_raw (default 480),
profiles [{target, mode}], updates [{at, zone, output, target, mode, temperature,
status}]. All times are seconds. Inputs stay private. This is an open-loop,
cold-start conditional replay, not a thermal or physical relay prediction.
Use test_pwm_restart.py for durable HA-adapter recovery tests; this runner does
not pretend to reconstruct a journal that was never captured.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace


def source():
    root = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(root), str(root / "tests")]
    import conftest
    import test_pwm_load_balancing as simulation
    from custom_components.adaptive_climate.managers import pwm_controller
    from custom_components.adaptive_climate.managers.heat_pipeline import HeatPipeline
    from custom_components.adaptive_climate.managers.pwm_pulse import prepare_pulse, Pulse
    from custom_components.adaptive_climate.helpers.hydraulic_metrics import HydraulicEvent, analyze

    return SimpleNamespace(**locals())


def historical_manager(ref, destination):
    """Load the exact original manager without modifying the working tree."""
    root = Path(__file__).resolve().parents[1]
    data = subprocess.check_output(
        [
            "git",
            "-C",
            str(root),
            "show",
            f"{ref}:custom_components/adaptive_climate/managers/pwm_load_balancing_manager.py",
        ]
    )
    destination.write_bytes(data)
    name = "custom_components.adaptive_climate.managers._budget_baseline"
    spec = importlib.util.spec_from_file_location(name, destination)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module.PWMLoadBalancingManager


async def replay(trace, manager_class=None):
    src = source()
    current = src.simulation.PWMLoadBalancingManager
    if manager_class is not None:
        src.simulation.PWMLoadBalancingManager = manager_class
    try:
        sim = src.simulation.Simulation((0,) * len(trace["profiles"]))
    finally:
        src.simulation.PWMLoadBalancingManager = current
    sim.manager._origin = trace.get("origin", 0.0)
    sim.manager.overlap = trace.get("overlap", 120)
    sim.manager.max_deferral = 3600
    minimum = trace.get("min_raw", 480)
    duration = trace["duration"]
    src.pwm_controller.time = SimpleNamespace(monotonic=lambda: sim.now)
    audit = []
    duplicates = []
    active_period_grants = []
    entitlement_accounts = {}
    cancelled_baselines = {}
    original_allocate = sim.manager._allocate

    def allocate(ledger, now):
        account = entitlement_accounts.setdefault(
            ledger.adapter.entity_id, {"requested": 0.0, "cancelled": 0.0, "credit": 0.0, "delivered": 0.0}
        )
        account["credit"] -= ledger.delivered - account["delivered"]
        account["delivered"] = ledger.delivered
        before = {k: getattr(ledger, k) for k in ("epoch", "credit", "allocation", "requested", "cancelled_balance")}
        adapter = ledger.adapter
        signature = adapter.signature()
        changed = signature != ledger.target_signature or ledger.pending_priority
        eligible = adapter.eligible()
        if not eligible and ledger.observed_on and ledger.allocation_started and ledger.allocation > 0:
            cancelled_baselines[adapter.entity_id] = (ledger.epoch, ledger.allocation, signature)
        original_allocate(ledger, now)
        grant = ledger.requested - before["requested"]
        if (
            before["epoch"] >= 0
            and ledger.epoch > before["epoch"]
            and ledger.observed_on
            and adapter.output() < 100
            and not changed
        ):
            active_period_grants.append({"at": now, "zone": adapter.entity_id, "seconds": grant})
        duplicate = 0.0
        baseline = cancelled_baselines.get(adapter.entity_id)
        if baseline and eligible:
            epoch, allocation, old_signature = baseline
            if (
                epoch == ledger.epoch == before["epoch"]
                and ledger.observed_on
                and not changed
                and signature == old_signature
                and before["allocation"] == 0
                and ledger.pulse.accumulator_debit == 0
                and grant > 0
            ):
                duplicate = min(grant, allocation)
                duplicates.append({"at": now, "zone": adapter.entity_id, "seconds": duplicate})
            cancelled_baselines.pop(adapter.entity_id, None)
        after = {k: getattr(ledger, k) for k in before}
        valid_grant = grant - duplicate
        cancellation = ledger.cancelled_balance - before["cancelled_balance"]
        account["requested"] += valid_grant
        if not eligible:
            account["cancelled"] += max(0.0, account["credit"])
            account["credit"] = min(0.0, account["credit"])
        elif abs(cancellation - grant) < 1e-7 and cancellation != 0:
            # Closed-period revisions affect both sides, not usable credit.
            account["cancelled"] += valid_grant
        else:
            account["credit"] += valid_grant
            revoked = min(max(0.0, account["credit"]), max(0.0, cancellation))
            account["credit"] -= revoked
            account["cancelled"] += revoked
        if before != after:
            audit.append(
                {
                    "at": now,
                    "zone": adapter.entity_id,
                    "on": ledger.observed_on,
                    "output": adapter.output(),
                    "target": adapter.target,
                    "mode": adapter.mode,
                    "priority": ledger.priority,
                    "before": before,
                    "after": after,
                    "grant": grant,
                }
            )

    sim.manager._allocate = allocate

    class Zone(src.simulation.SimZone):
        def prepare(self, now):
            pwm = self.heater._pwm_controller
            if pwm._calculate_heat_duration(self.output(), 100) < minimum and self.temperature >= self.target:
                pwm.reset_duty_accumulator()
                return src.Pulse(0)
            return src.prepare_pulse(self.heater, self.output(), now)

        def commit_credit(self, seconds):
            if seconds:
                pwm = self.heater._pwm_controller
                pwm.set_duty_accumulator(max(0, pwm.duty_accumulator_seconds - seconds))
                pwm._last_accumulator_calc_time = None

        def suspend_accumulation(self):
            pwm = self.heater._pwm_controller
            if self.output() <= 0:
                pwm.reset_duty_accumulator()
            else:
                pwm._last_accumulator_calc_time = None

        async def command(self, on):
            previous = self.on
            ledger = sim.manager._zones[self.entity_id]
            ordinary = not ledger.priority and not ledger.pulse.continuous
            result = await super().command(on)
            if previous != self.on:
                if on:
                    self.starts.append({"at": sim.now, "ordinary": ordinary})
                pipeline = self.heater._pwm_controller._heat_pipeline
                (pipeline.valve_opened if on else pipeline.valve_closed)(sim.now)
            return result

    for n, profile in enumerate(trace["profiles"]):
        old = sim.zones[n]
        zone = Zone(old.entity_id, sim, 0)
        zone.target, zone.mode = profile["target"], profile["mode"]
        zone.temperature = zone.target
        zone.min_on, zone.min_off = minimum + 120, 600
        zone.starts = []
        zone.heater = SimpleNamespace(
            _pwm=3600,
            _difference=100,
            _min_closed_time=600,
            effective_min_open_time=minimum + 120,
            _pwm_controller=src.pwm_controller.PWMController(
                SimpleNamespace(), 3600, 100, minimum, 600, 120, src.HeatPipeline(0, 120, 2700)
            ),
            is_active=lambda mode, z=zone: z.on,
        )
        sim.zones[n] = zone
        ledger = sim.manager._zones[zone.entity_id]
        ledger.adapter, ledger.target_signature = zone, zone.signature()
    last = -1.0
    for row in trace["updates"]:
        if not last <= row["at"] <= duration:
            raise ValueError("Updates must be ordered and inside the replay window")
        last = row["at"]
        await sim.advance(last)
        zone = sim.zones[row["zone"]]
        zone.seconds = row["output"] * 36
        zone.target, zone.mode = row["target"], row["mode"]
        zone.temperature = row.get("temperature", zone.target)
        overrides = (row.get("status") or {}).get("overrides", [])
        zone.paused = zone.temperature is None or any(o.get("type") in ("contact_open", "humidity") for o in overrides)
        await sim.update(row["zone"])
    await sim.advance(duration)
    zones = []
    for zone in sim.zones:
        ledger = sim.manager._zones[zone.entity_id]
        sim.manager._sample(ledger, duration)
        residual = ledger.requested - ledger.delivered - ledger.credit - ledger.cancelled_balance
        assert abs(residual) < 1e-5
        intervals = []
        for n, (at, on) in enumerate(zone.transitions):
            end = zone.transitions[n + 1][0] if n + 1 < len(zone.transitions) else duration
            if on:
                intervals.append(end - at)
            if n + 1 < len(zone.transitions):
                assert end - at >= (zone.min_on if on else zone.min_off) - 0.001
        gaps = [b["at"] - a["at"] for a, b in zip(zone.starts, zone.starts[1:])]
        spacing = [b["at"] - a["at"] for a, b in zip(zone.starts, zone.starts[1:]) if b["ordinary"]]
        assert all(gap >= 3600 - 0.001 for gap in spacing)
        duplicate = sum(d["seconds"] for d in duplicates if d["zone"] == zone.entity_id)
        account = entitlement_accounts[zone.entity_id]
        entitlement = account["requested"] - account["cancelled"]
        zones.append(
            {
                "zone": zone.entity_id,
                "starts": len(zone.starts),
                "minimum_start_gap": min(gaps, default=None),
                "maximum_on_seconds": max(intervals, default=0),
                "on_intervals_seconds": intervals,
                "delivered": ledger.delivered,
                "requested": ledger.requested,
                "cancelled": ledger.cancelled_balance,
                "credit": ledger.credit,
                "audited_entitlement": entitlement,
                "entitlement_account": account,
                "duplicate_seconds": duplicate,
                "overdelivery": max(0, ledger.delivered - entitlement),
                "underdelivery": max(0, entitlement - ledger.delivered),
                "ledger_residual": residual,
                "priority_starts": ledger.priority_start_count,
            }
        )
    events = [src.HydraulicEvent(at, z.entity_id, on) for z in sim.zones for at, on in z.transitions if at < duration]
    hydraulics = src.analyze(events, sim.manager.members, 0, duration, dict.fromkeys(sim.manager.members, False))
    return {
        "model": __doc__,
        "zones": zones,
        "budget_events": audit,
        "duplicate_grants": duplicates,
        "active_ordinary_period_grants": active_period_grants,
        "hydraulics": hydraulics,
        "transitions": [z.transitions for z in sim.zones],
    }


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", default="v0.67.1-pwm.12")
    parser.add_argument("--baseline-label", default="baseline")
    parser.add_argument("--candidate-label", default="candidate")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    trace = json.loads(args.input.read_text(encoding="utf-8-sig"))
    source()
    old = historical_manager(args.baseline, args.output / "baseline_manager_private.py")
    for label, manager in ((args.baseline_label, old), (args.candidate_label, None)):
        result = await replay(trace, manager)
        (args.output / f"{label}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(label, json.dumps(result["zones"]), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
