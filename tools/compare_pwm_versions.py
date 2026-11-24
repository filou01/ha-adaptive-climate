"""Compare real synthetic runtime edges from exact git manager revisions.

The compared revisions share the same runtime planner and optimizer.
No Home Assistant data, credentials or journal reconstruction are involved.
"""

import argparse
import asyncio
import json
from pathlib import Path

from replay_pwm_budgets import historical_manager, source


async def run_case(manager, case):
    src = source()
    original = src.simulation.PWMLoadBalancingManager
    src.simulation.PWMLoadBalancingManager = manager
    try:
        sim = src.simulation.Simulation((1800, 1200, 900, 900) if case == "overload" else (600, 600))
    finally:
        src.simulation.PWMLoadBalancingManager = original
    sim.manager.overlap, sim.manager.max_deferral = 120, 3600
    for zone in sim.zones:
        zone.min_on = zone.min_off = 600
    await sim.update()
    if case == "return":
        await sim.advance(1800)
        sim.zones[0].seconds = 0
        await sim.update()
        await sim.advance(7553)
        sim.zones[0].seconds = 600
        await sim.update()
    elif case == "growth":
        await sim.advance(3500)
        sim.zones[0].seconds = 1200
        await sim.update()
    await sim.advance(8 * 3600 - 1)
    # Independent integration of observed intervals, not theoretical phases.
    from test_pwm_budget_phase_independence import intervals, occupancy

    zones = []
    for zone in sim.zones:
        ledger = sim.manager._zones[zone.entity_id]
        sim.manager._sample(ledger, sim.now)
        zones.append(
            {
                "entity": zone.entity_id,
                "intervals": intervals(zone),
                "requested": ledger.requested,
                "delivered": ledger.delivered,
                "cancelled": ledger.cancelled_balance,
                "credit": ledger.credit,
                "next_release_phase": ledger.next_budget_at % 3600 if ledger.next_budget_at is not None else None,
            }
        )
    return {
        "zones": zones,
        "periods": [
            dict(zip(("union", "combined_overlap", "pump_components"), occupancy(sim, n * 3600, (n + 1) * 3600)))
            for n in range(7)
        ],
        "group_pump_starts": sim.manager.estimated_starts,
        "weighted_overlap": sim.manager.weighted_overlap_seconds,
        "high_weight_overlap": sim.manager.high_weight_overlap_seconds,
    }


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    src = source()
    current = src.simulation.PWMLoadBalancingManager
    versions = {
        name: historical_manager(ref, args.output / f"manager-{name}.py")
        for name, ref in (
            ("v14", "551adf2f877663fdeb18585283a19d8c44507f6d"),
            ("v15", "46d3b488adb36efea9045ac93b26f368e9e368fa"),
            ("v16", "c7bcbd9a7e1902d1d2f06159013e3ebd5c8a514d"),
        )
    }
    versions["candidate"] = current
    results = {}
    for name, manager in versions.items():
        results[name] = {}
        for case in ("steady", "return", "growth", "overload"):
            result = await run_case(manager, case)
            results[name][case] = result
            print(name, case, "pump", result["group_pump_starts"], "period3", result["periods"][3], flush=True)
    (args.output / "runtime-comparison.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
