"""A transient zero before minimum-ON expires cannot mint another ordinary pulse."""

import pytest

from test_pwm_ha_integration import live
from test_pwm_load_balancing import Simulation
from test_pwm_restart import journal


@pytest.mark.asyncio
async def test_zero_and_return_during_minimum_on_does_not_regrant_spent_budget(live):
    entity, other = live.entities
    other._control_output = 0
    entity._control_output = 20.5
    await entity.apply()
    group = live.registry.groups[0]
    ledger = group._zones[entity.entity_id]
    initial = ledger.requested
    minimum = entity._heater_controller.effective_min_open_time
    live.clock.now += minimum - 8
    entity._control_output = 0
    await entity.apply()
    assert live.state[f"{live.domain}.a"] == "on"
    live.clock.now += 7.97
    entity._control_output = 20.9
    await entity.apply()
    # A revision can add 14.4s, never another entire ~800s reservation.
    assert ledger.requested <= initial + 14.4 + 0.001
    live.clock.now += 15
    await entity.apply()
    assert live.state[f"{live.domain}.a"] == "off"
    assert ledger.requested == pytest.approx(ledger.delivered + ledger.credit + ledger.cancelled_balance)


@pytest.mark.asyncio
@pytest.mark.parametrize("period", [1800, 3600, 7200])
async def test_legitimate_adjacent_period_budgets_are_consumed_once(period):
    sim = Simulation((0,), period=period)
    zone = sim.zones[0]
    await sim.update()
    await sim.advance(period * 0.9)
    zone.seconds = period * 0.2
    await sim.update()
    await sim.advance(period * 1.31)
    ledger = sim.manager._zones[zone.entity_id]
    # Both independently earned periods can legitimately form one long pulse.
    assert zone.transitions == [(period * 0.9, True), (period * 1.3, False)]
    assert ledger.delivered == pytest.approx(period * 0.4)
    assert ledger.requested == pytest.approx(period * 0.4)
    assert ledger.credit == pytest.approx(0)


@pytest.mark.asyncio
async def test_zero_demand_does_not_forgive_minimum_on_overdelivery():
    sim = Simulation((300,))
    zone = sim.zones[0]
    zone.min_on = 600
    await sim.update()
    await sim.advance(600)
    ledger = sim.manager._zones[zone.entity_id]
    assert ledger.credit == -300
    zone.seconds = 0
    await sim.update()
    assert ledger.credit == -300
    assert ledger.cancelled_balance == 0


@pytest.mark.asyncio
async def test_v12_zero_demand_journal_cannot_regrant_a_running_pulse(journal):
    live = journal.live
    entity, other = live.entities
    other._control_output = 0
    entity._control_output = 20.5
    await entity.apply()
    journal.advance(entity._heater_controller.effective_min_open_time - 8)
    entity._control_output = 0
    await entity.apply()
    await live.registry.async_save()
    # The old serializer has the same schema, but v12 erased this baseline.
    saved = journal.disk.data["pwm_coordination"]["pump"]["zones"]["climate.a"]
    saved["allocation"] = 0
    assert saved["pulse"][0] == saved["credit"] == 0
    await journal.reboot(offline=0)
    journal.advance(7.97)
    live.entities[0]._control_output = 20.9
    await live.entities[0].apply()
    assert journal.ledger().credit <= 0
    journal.advance(0.04)
    await live.entities[0].apply()
    assert live.state[f"{live.domain}.a"] == "off"


@pytest.mark.asyncio
@pytest.mark.parametrize("period", [1800, 3600, 7200])
@pytest.mark.parametrize("return_fraction", [0.2, 0.25, 0.15])
async def test_transient_zero_revises_a_spent_baseline_instead_of_reminting(period, return_fraction):
    sim = Simulation((period * 0.2,), period=period)
    zone = sim.zones[0]
    zone.min_on = period / 6
    await sim.update()
    await sim.advance(zone.min_on - 8)
    zone.seconds = 0
    await sim.update()
    await sim.advance(zone.min_on - 0.03)
    zone.seconds = period * return_fraction
    await sim.update()
    ledger = sim.manager._zones[zone.entity_id]
    assert ledger.requested == pytest.approx(period * return_fraction)
    await sim.advance(period * 0.4)
    assert not zone.on
    assert len([on for _, on in zone.transitions if on]) == 1
