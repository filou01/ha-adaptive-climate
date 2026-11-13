"""Ordinary period budgets cannot concatenate across the shared group phase."""

from itertools import pairwise

import pytest

from test_pwm_ha_integration import live
from test_pwm_load_balancing import Simulation
from test_pwm_restart import journal


@pytest.mark.asyncio
@pytest.mark.parametrize("period", [1800, 3600, 7200])
@pytest.mark.parametrize("strategy", ["minimal", "maximal"])
async def test_late_ordinary_pulse_keeps_one_budget_and_hourly_observed_starts(period, strategy):
    sim = Simulation((0,), period=period, strategy=strategy)
    await sim.update()
    await sim.advance(period * 0.95)
    zone = sim.zones[0]
    zone.seconds = period * 0.2
    await sim.update()
    await sim.advance(period * 5.5)
    starts = [at for at, on in zone.transitions if on]
    assert len(starts) == 5
    assert all(b - a == pytest.approx(period) for a, b in pairwise(starts))
    durations = [b[0] - a[0] for a, b in pairwise(zone.transitions) if a[1]]
    assert durations == pytest.approx([period * 0.2] * 5)
    ledger = sim.manager._zones[zone.entity_id]
    assert ledger.requested == pytest.approx(period)
    assert ledger.credit == pytest.approx(0)


@pytest.mark.asyncio
async def test_minimum_off_delayed_reservation_is_not_multiplied_by_missed_epochs():
    sim = Simulation((720,))
    zone = sim.zones[0]
    zone.min_off = 8000
    zone.last_change = 0
    await sim.update()
    await sim.advance(8001)
    await sim.update()
    assert zone.transitions == [(8000, True)]
    ledger = sim.manager._zones[zone.entity_id]
    assert ledger.requested == 720
    assert ledger.credit == 719
    await sim.advance(8721)
    assert zone.transitions[-1] == (8720, False)


@pytest.mark.asyncio
async def test_v13_phase_deadline_during_active_pulse_recovers_without_a_second_grant(journal):
    live = journal.live
    entity, other = live.entities
    entity._control_output = other._control_output = 0
    await entity.apply()
    journal.advance(3240)
    entity._control_output = 20
    await entity.apply()
    await live.registry.async_save()
    saved = journal.disk.data["pwm_coordination"]["pump"]
    # Legacy v13 deadline points to a group boundary 360s after the late ON.
    saved["zones"]["climate.a"]["next_at"] = saved["at"] + 360
    requested = journal.ledger().requested
    await journal.reboot(offline=0)
    journal.advance(361)
    await live.entities[0].apply()
    assert journal.ledger().requested == requested
    assert live.state[f"{live.domain}.a"] == "on"
    journal.advance(420)
    await live.entities[0].apply()
    assert live.state[f"{live.domain}.a"] == "off"


@pytest.mark.asyncio
async def test_real_adapter_boundary_preserves_single_effective_pulse(live):
    entity, other = live.entities
    entity._control_output = other._control_output = 0
    await entity.apply()
    live.clock.now += 3240
    entity._control_output = 20
    await entity.apply()
    requested = live.registry.groups[0]._zones[entity.entity_id].requested
    live.clock.now += 361
    await entity.apply()
    assert live.registry.groups[0]._zones[entity.entity_id].requested == requested
    live.clock.now += 419
    await entity.apply()
    assert live.state[f"{live.domain}.a"] == "off"


@pytest.mark.asyncio
async def test_target_change_while_on_revises_one_budget_across_global_boundary():
    sim = Simulation((0,))
    await sim.update()
    await sim.advance(3240)
    zone = sim.zones[0]
    zone.seconds = 720
    await sim.update()
    await sim.advance(3700)
    zone.target += 1
    zone.seconds = 900
    await sim.update()
    assert sim.manager._zones[zone.entity_id].requested == 900
    await sim.advance(4141)
    assert zone.transitions == [(3240, True), (4140, False)]
