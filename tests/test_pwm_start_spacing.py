"""A late ordinary pulse must not be followed by another at the epoch boundary."""

from itertools import pairwise

import pytest

from test_pwm_load_balancing import Simulation
from test_pwm_ha_integration import live
from test_pwm_restart import journal


@pytest.mark.asyncio
@pytest.mark.parametrize("period", [1800, 3600, 7200])
@pytest.mark.parametrize("strategy", ["minimal", "maximal"])
async def test_late_ordinary_start_keeps_a_full_period_between_starts(period, strategy):
    sim = Simulation((0,), period=period, strategy=strategy)
    zone = sim.zones[0]
    zone.min_on = zone.min_off = period / 6
    await sim.update()
    late = period * 0.6
    await sim.advance(late)
    zone.seconds = period / 6
    await sim.update()
    await sim.advance(3 * period)
    starts = [at for at, on in zone.transitions if on]
    assert starts[0] == late
    assert len(starts) >= 2
    assert all(b - a >= period - 0.001 for a, b in pairwise(starts))
    assert starts[1] == pytest.approx(late + period)


@pytest.mark.asyncio
async def test_priority_bypasses_ordinary_spacing_but_spends_the_following_allowance():
    sim = Simulation((0,))
    zone = sim.zones[0]
    zone.min_on = zone.min_off = 600
    await sim.update()
    await sim.advance(2200)
    zone.seconds = 600
    await sim.update()
    await sim.advance(3700)
    assert not zone.on
    zone.target += 1
    await sim.update()
    assert zone.transitions[-1] == (3700, True)
    await sim.advance(11000)
    starts = [at for at, on in zone.transitions if on]
    assert starts[:2] == [2200, 3700]
    assert starts[2] >= 7300


@pytest.mark.asyncio
async def test_real_ha_adapter_does_not_restart_a_late_pulse_at_the_next_epoch(live):
    entity, other = live.entities
    entity._control_output = other._control_output = 0
    await entity.apply()
    for elapsed in range(60, 10801, 60):
        live.clock.now = 10000 + elapsed
        if elapsed == 2220:
            entity._control_output = 20
        await entity.apply()
    starts = [at for at, action, output in live.commands if action == "turn_on" and output == f"{live.domain}.a"]
    assert len(starts) >= 2
    assert all(b - a >= 3600 - 0.001 for a, b in pairwise(starts))


@pytest.mark.asyncio
async def test_late_start_spacing_survives_off_restart_and_monotonic_reset(journal):
    live = journal.live
    entity, other = live.entities
    entity._control_output = other._control_output = 0
    await entity.apply()
    journal.advance(2200)
    entity._control_output = 20
    await entity.apply()
    started = journal.wall.seconds
    journal.advance(1000)
    await entity.apply()
    assert live.state[f"{live.domain}.a"] == "off"
    await journal.reboot(offline=60)
    remaining = 3600 - (journal.wall.seconds - started)
    journal.advance(remaining - 1)
    await live.entities[0].apply()
    assert live.state[f"{live.domain}.a"] == "off"
    journal.advance(1)
    await live.entities[0].apply()
    assert live.state[f"{live.domain}.a"] == "on"
    assert journal.wall.seconds - started == 3600


@pytest.mark.asyncio
async def test_continuous_demand_is_not_delayed_by_ordinary_spacing():
    sim = Simulation((0,))
    zone = sim.zones[0]
    await sim.update()
    await sim.advance(2200)
    zone.seconds = 600
    await sim.update()
    await sim.advance(2900)
    assert not zone.on
    zone.seconds = 3600
    await sim.update()
    assert zone.transitions[-1] == (2900, True)
    await sim.advance(10000)
    assert zone.on
    assert [at for at, on in zone.transitions if on] == [2200, 2900]


@pytest.mark.asyncio
@pytest.mark.parametrize("keep_pipeline_stamp", [False, True])
async def test_old_journal_without_start_stamp_restores_a_safe_guard(journal, keep_pipeline_stamp):
    live = journal.live
    await journal.complete_first()
    saved = journal.disk.data["pwm_coordination"]["pump"]["zones"]["climate.a"]
    saved.pop("last_start_at")
    if not keep_pipeline_stamp:
        saved["controller"]["opened_at"] = None
    await journal.reboot(offline=60)
    ledger = journal.ledger()
    # Old snapshots retain an epoch but not an exact ON time. The upper bound
    # cannot imply an earlier restart than a full period from the saved row.
    age = 1560 if keep_pipeline_stamp else 60
    assert ledger.last_start_at == pytest.approx(live.clock.now - age)
    await live.entities[0].apply()
    assert live.state[f"{live.domain}.a"] == "off"
    assert live.registry.groups[0].diagnostics("climate.a")["ordinary_restart_in_seconds"] == 3600 - age


@pytest.mark.asyncio
async def test_future_start_stamp_is_rejected_before_restoring_group(journal):
    live = journal.live
    await journal.complete_first()
    state = journal.disk.data["pwm_coordination"]["pump"]
    state["zones"]["climate.a"]["last_start_at"] = state["at"] + 30
    await journal.reboot()
    assert live.registry.groups[0].mode == "fallback"
    assert live.registry.groups[0].reason == "restart_state_invalid"


@pytest.mark.asyncio
async def test_zero_demand_does_not_earn_low_duty_credit_for_the_idle_gap(live):
    entity, other = live.entities
    other._control_output = 0
    entity._control_output = 5
    await entity.apply()
    live.clock.now += 600
    await entity.apply()
    assert entity._heater_controller.duty_accumulator_seconds > 0
    entity._control_output = 0
    await entity.apply()
    live.clock.now += 20000
    entity._control_output = 5
    await entity.apply()
    await entity.apply()
    assert live.state[f"{live.domain}.a"] == "off"
    assert entity._heater_controller.duty_accumulator_seconds == 0


@pytest.mark.asyncio
async def test_pause_keeps_earned_credit_but_does_not_accrue_the_paused_interval(live):
    entity, other = live.entities
    other._control_output = 0
    entity._control_output = 5
    await entity.apply()
    live.clock.now += 600
    await entity.apply()
    earned = entity._heater_controller.duty_accumulator_seconds
    entity._status_manager.is_paused = lambda _: True
    await entity.apply()
    live.clock.now += 20000
    entity._status_manager.is_paused = lambda _: False
    await entity.apply()
    await entity.apply()
    assert live.state[f"{live.domain}.a"] == "off"
    assert entity._heater_controller.duty_accumulator_seconds == earned
