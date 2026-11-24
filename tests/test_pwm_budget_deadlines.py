"""Stable budget deadlines constrain flexible, hydraulically repaired starts."""

from itertools import pairwise

import pytest

from test_pwm_load_balancing import Simulation


@pytest.mark.asyncio
@pytest.mark.parametrize("period", [1800, 3600, 7200])
async def test_stable_overload_preserves_each_observed_cadence_and_full_budgets(period):
    durations = tuple(d * period / 3600 for d in (1800, 1200, 900, 900))
    sim = Simulation(durations, period=period)
    sim.manager.overlap = period / 30
    sim.manager.max_deferral = period
    for zone in sim.zones:
        zone.min_on = zone.min_off = period / 6
    await sim.update()
    await sim.advance(10 * period)
    for zone, duration in zip(sim.zones, durations):
        starts = [at for at, on in zone.transitions if on]
        assert len(starts) >= 10
        # A cyclic phase is a preference, not a runtime heat deadline. The
        # complete reservation must fit the stable entitlement window instead.
        assert starts[0] + duration <= period + 0.001
        assert all(b - a == pytest.approx(period, abs=0.001) for a, b in pairwise(starts))
        assert max(at - starts[0] - n * period for n, at in enumerate(starts)) <= 0.001
        ledger = sim.manager._zones[zone.entity_id]
        sim.manager._sample(ledger, sim.now)
        expected = sum(min(duration, max(0, sim.now - starts[0] - n * period)) for n in range(11))
        assert ledger.delivered == pytest.approx(expected, abs=0.001)
        assert ledger.cancelled_balance == pytest.approx(0, abs=0.001)
        assert ledger.requested == pytest.approx(ledger.delivered + ledger.credit + ledger.cancelled_balance)
    # Total active load beyond the union must provide at least the unavoidable
    # 20 minutes of combined overlap per fully populated steady period.
    delivered = sum(z.delivered for z in sim.manager._zones.values())
    assert delivered - sim.manager.energized_seconds >= 8 * period / 3
    diagnostics = sim.manager.diagnostics(sim.zones[0].entity_id)
    assert diagnostics["runtime_deadline_policy"] == "complete_budget_within_stable_window"
    assert diagnostics["overlap_required_seconds"] == pytest.approx(period / 3)
    assert diagnostics["projected_combined_overlap_seconds"] >= period / 3 - 0.001


@pytest.mark.asyncio
async def test_changing_outputs_keep_budget_lattice_while_execution_phase_can_change():
    sim = Simulation((1800, 1200, 900, 900))
    sim.manager.overlap = 120
    sim.manager.max_deferral = 3600
    anchors = {zone.entity_id: [] for zone in sim.zones}
    for at in range(0, 8 * 3600 + 1, 60):
        await sim.advance(at)
        for n, zone in enumerate(sim.zones):
            zone.seconds = (1800, 1200, 900, 900)[n] + (at // 1800 % 3 - 1) * 120
        await sim.update()
        for entity, ledger in sim.manager._zones.items():
            anchors[entity].append(ledger.next_budget_at)
    for zone in sim.zones:
        starts = [at for at, on in zone.transitions if on]
        # Demand changes may move phase in either direction. Preserve the
        # actual quota, full entitlements and fixed release lattice instead
        # of blessing v15's frozen phase as the definition of correctness.
        assert len(starts) >= 8
        assert len({int(at // 3600) for at in starts}) == len(starts)
        assert all(at % 3600 == pytest.approx(0, abs=0.001) for at in anchors[zone.entity_id])
        ledger = sim.manager._zones[zone.entity_id]
        sim.manager._sample(ledger, sim.now)
        assert ledger.requested == pytest.approx(ledger.delivered + ledger.credit + ledger.cancelled_balance)
        assert ledger.credit <= zone.seconds + 0.001


@pytest.mark.asyncio
async def test_late_single_start_still_cannot_merge_another_global_period():
    sim = Simulation((0,))
    await sim.update()
    await sim.advance(3240)
    sim.zones[0].seconds = 720
    await sim.update()
    await sim.advance(7561)
    assert sim.zones[0].transitions == [(3240, True), (3960, False), (6840, True), (7560, False)]


@pytest.mark.asyncio
async def test_recorded_input_auditor_rejects_hidden_eligible_budget_delay(monkeypatch):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    from replay_pwm_budgets import replay
    from custom_components.adaptive_climate.managers import pwm_controller

    monkeypatch.setattr(pwm_controller, "time", pwm_controller.time)
    trace = {
        "duration": 6 * 3600,
        "profiles": [{"target": 23, "mode": "heat"}] * 4,
        "updates": [
            {"at": 0, "zone": n, "output": duty, "target": 23, "temperature": 22, "mode": "heat"}
            for n, duty in enumerate((50, 100 / 3, 25, 25))
        ],
    }
    result = await replay(trace)
    assert not result["late_recurring_budget_starts"]
    assert not result["active_ordinary_period_grants"]
    assert not result["duplicate_grants"]
