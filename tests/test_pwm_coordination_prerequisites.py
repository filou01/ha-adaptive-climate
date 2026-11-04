"""Safety gates for adding a second, scheduled entry into HeaterController.

These are NOT scheduler acceptance tests. Strict expected failures document
unresolved upstream contracts; use --runxfail to reproduce the red assertions.
The runtime scheduler must remain unavailable until these gates are resolved.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.adaptive_climate.managers import heater_controller as heater_module
from custom_components.adaptive_climate.managers import pwm_controller as pwm_module
from custom_components.adaptive_climate.managers.events import CycleEventType


@pytest.fixture
def actuator(monkeypatch):
    """Use the real controllers with an explicitly observed binary output."""
    mode = SimpleNamespace(HEAT="heat", COOL="cool", OFF="off")
    monkeypatch.setattr(heater_module, "HVACMode", mode)
    monkeypatch.setattr(pwm_module, "HVACMode", mode)
    clock = SimpleNamespace(now=10000.0)
    monotonic = SimpleNamespace(monotonic=lambda: clock.now)
    monkeypatch.setattr(heater_module, "time", monotonic)
    monkeypatch.setattr(pwm_module, "time", monotonic)
    state = {"switch.zone": "off"}
    hass = MagicMock()
    hass.states.is_state.side_effect = lambda entity, expected: state.get(entity) == expected
    thermostat = SimpleNamespace(
        entity_id="climate.zone", _current_temp=19.0, target_temperature=22.0, _target_temp=22.0
    )
    dispatcher = MagicMock()
    controller = heater_module.HeaterController(
        hass=hass,
        thermostat=thermostat,
        heater_entity_id=["switch.zone"],
        cooler_entity_id=None,
        demand_switch_entity_id=None,
        heater_polarity_invert=False,
        pwm=3600,
        difference=100.0,
        min_open_time=600.0,
        min_closed_time=600.0,
        dispatcher=dispatcher,
    )
    tracking = SimpleNamespace(changed=0.0, heating=False)
    callbacks = {
        "hvac_mode": "heat",
        "get_cycle_start_time": lambda: tracking.changed,
        "set_is_heating": lambda active: setattr(tracking, "heating", active),
        "set_last_heat_cycle_time": lambda at: setattr(tracking, "changed", at),
    }

    async def successful_service(domain, service, data):
        state[data["entity_id"]] = "on" if service == "turn_on" else "off"

    hass.services.async_call = AsyncMock(side_effect=successful_service)
    return SimpleNamespace(
        controller=controller,
        hass=hass,
        state=state,
        clock=clock,
        tracking=tracking,
        callbacks=callbacks,
        dispatcher=dispatcher,
    )


def emitted_types(actuator):
    return [call.args[0].event_type for call in actuator.dispatcher.emit.call_args_list]


async def accumulated_pulse(actuator):
    controller = actuator.controller
    controller.set_duty_accumulator(600.0)
    await controller.async_pwm_switch(
        control_output=5.0,
        **actuator.callbacks,
        time_changed=0.0,
        set_time_changed=MagicMock(),
        force_on=True,
        force_off=False,
        set_force_on=MagicMock(),
        set_force_off=MagicMock(),
    )


@pytest.mark.asyncio
async def test_successful_start_tracks_observed_output(actuator):
    """Positive control: the harness can deliver a real controller pulse."""
    actuator.controller._has_demand = True
    await actuator.controller.async_turn_on(**actuator.callbacks)
    assert actuator.state["switch.zone"] == "on"
    assert actuator.tracking.heating
    assert CycleEventType.HEATING_STARTED in emitted_types(actuator)


@pytest.mark.asyncio
@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="Controller emits learning/pipeline start before service success"
)
async def test_failed_start_does_not_commit_delivery_or_learning(actuator):
    actuator.hass.services.async_call.side_effect = RuntimeError("relay unavailable")
    actuator.controller._has_demand = True
    await actuator.controller.async_turn_on(**actuator.callbacks)
    assert actuator.state["switch.zone"] == "off"
    assert actuator.controller.heater_control_failed
    assert CycleEventType.HEATING_STARTED not in emitted_types(actuator)
    assert not actuator.tracking.heating
    assert actuator.controller._heat_pipeline._valve_opened_at is None


@pytest.mark.asyncio
@pytest.mark.xfail(strict=True, raises=AssertionError, reason="PWM spends accumulated credit after a min-OFF rejection")
async def test_min_off_rejection_retains_accumulated_credit(actuator):
    actuator.tracking.changed = actuator.clock.now - 420.0  # 180s of min-OFF left
    await accumulated_pulse(actuator)
    actuator.hass.services.async_call.assert_not_awaited()
    assert actuator.state["switch.zone"] == "off"
    assert actuator.controller.duty_accumulator_seconds == 600.0


@pytest.mark.asyncio
@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="PWM spends accumulated credit after a failed service call"
)
async def test_failed_accumulated_pulse_retains_credit(actuator):
    actuator.hass.services.async_call.side_effect = RuntimeError("relay unavailable")
    await accumulated_pulse(actuator)
    assert actuator.state["switch.zone"] == "off"
    assert actuator.controller.heater_control_failed
    assert actuator.controller.duty_accumulator_seconds == 600.0


@pytest.mark.asyncio
@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="Forced OFF sees relay still OFF while a prior ON is in flight"
)
async def test_force_off_wins_over_inflight_start(actuator):
    """Model separate scheduler and mode entry points with a suspended service."""
    entered = asyncio.Event()
    release = asyncio.Event()

    async def delayed_service(domain, service, data):
        if service == "turn_on":
            entered.set()
            await release.wait()
        actuator.state[data["entity_id"]] = "on" if service == "turn_on" else "off"

    actuator.hass.services.async_call.side_effect = delayed_service
    pending = asyncio.create_task(actuator.controller.async_turn_on(**actuator.callbacks))
    try:
        await asyncio.wait_for(entered.wait(), timeout=1.0)
        actuator.controller._has_demand = False
        await actuator.controller.async_turn_off(**actuator.callbacks, force=True)
    finally:
        release.set()
        await pending
    assert actuator.state["switch.zone"] == "off"


@pytest.mark.asyncio
@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="Controller emits HEATING_ENDED before failed OFF service"
)
async def test_failed_stop_does_not_commit_learning_end(actuator):
    actuator.controller._has_demand = True
    await actuator.controller.async_turn_on(**actuator.callbacks)
    actuator.clock.now += 900.0
    actuator.dispatcher.reset_mock()
    actuator.hass.services.async_call.side_effect = RuntimeError("relay unavailable")
    await actuator.controller.async_turn_off(**actuator.callbacks)
    assert actuator.state["switch.zone"] == "on"
    assert actuator.controller.heater_control_failed
    assert CycleEventType.HEATING_ENDED not in emitted_types(actuator)
    assert actuator.tracking.heating
