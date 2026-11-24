"""A positive subminimum dip must not create debt when demand returns ON."""

import pytest

from test_pwm_ha_integration import live
from test_pwm_restart import journal


def prepare(live, at_target):
    entity, other = live.entities
    other._control_output = 0
    heater = entity._heater_controller
    heater._min_open_time = heater._pwm_controller._min_open_time = 480
    assert heater.effective_min_open_time == 600
    entity._current_temp = entity._target_temp if at_target else entity._target_temp - 0.2
    group = live.registry.groups[0]
    ledger = group._zones[entity.entity_id]
    # A known inherited signed balance; do not forgive it in the oracle.
    ledger.credit, ledger.delivered = -447.2, 447.2
    return entity, ledger, live.clock.now


@pytest.mark.asyncio
@pytest.mark.parametrize("at_target", [False, True])
async def test_positive_subminimum_return_revises_the_running_budget_without_cancellation(live, at_target):
    entity, ledger, start = prepare(live, at_target)
    entity._control_output = 23.7
    await entity.apply()
    assert ledger.credit == pytest.approx(913.2 - 447.2)
    live.clock.now = start + 120
    entity._control_output = 0.7  # Eligible, but PWM preparation produces Pulse(0).
    await entity.apply()
    assert live.state[f"{live.domain}.a"] == "on"
    live.clock.now = start + 180
    entity._control_output = 23.8
    await entity.apply()
    assert live.state[f"{live.domain}.a"] == "on"
    # Independent entitlement: revised nominal budget minus inherited debt and
    # actual delivery. No pause, OFF edge, target change or expired reservation.
    assert ledger.credit == pytest.approx(916.8 - 447.2 - 180)
    assert ledger.cancelled_balance == pytest.approx(0)


@pytest.mark.asyncio
@pytest.mark.parametrize("at_target", [False, True])
async def test_following_budget_is_not_blocked_by_fictitious_subminimum_debt(live, at_target):
    entity, ledger, start = prepare(live, at_target)
    for at, output in ((0, 23.7), (120, 0.7), (180, 23.8), (600, 23.3)):
        live.clock.now = start + at
        entity._control_output = output
        await entity.apply()
    assert live.state[f"{live.domain}.a"] == "off"
    assert ledger.delivered == pytest.approx(447.2 + 600)
    # At the next stable release, all physical minimum guards have elapsed.
    live.clock.now = start + 3600
    entity._control_output = 25.6
    await entity.apply()
    expected_carry = 898.8 - 447.2 - 600  # -148.4, not -1065.2.
    expected_credit = 981.6 + expected_carry  # 833.2s of usable heating.
    assert ledger.credit == pytest.approx(expected_credit)
    assert live.state[f"{live.domain}.a"] == "on"
    assert ledger.cancelled_balance == pytest.approx(0)
    live.clock.now += expected_credit - 1
    await entity.apply()
    assert live.state[f"{live.domain}.a"] == "on"
    live.clock.now += 1
    await entity.apply()
    assert live.state[f"{live.domain}.a"] == "off"
    assert ledger.delivered == pytest.approx(447.2 + 600 + expected_credit)


@pytest.mark.asyncio
async def test_recorded_auditor_must_not_accept_active_revisions_as_closed_cancellations(monkeypatch):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    from replay_pwm_budgets import replay
    from custom_components.adaptive_climate.managers import pwm_controller

    monkeypatch.setattr(pwm_controller, "time", pwm_controller.time)
    trace = {
        "duration": 1800,
        "min_raw": 480,
        "profiles": [{"target": 21, "mode": "heat"}],
        "updates": [
            dict(at=at, zone=0, output=output, target=21, temperature=20.8, mode="heat")
            for at, output in ((0, 23.7), (120, 0.7), (180, 23.8))
        ],
    }
    result = await replay(trace)
    assert not result["unexpected_active_budget_cancellations"]
    invalid = [
        event
        for event in result["budget_events"]
        if event["on"] and event["after"]["cancelled_balance"] > event["before"]["cancelled_balance"] + 0.001
    ]
    assert not invalid, "A live eligible revision is not a closed-period cancellation"
    assert result["zones"][0]["delivered"] == pytest.approx(916.8)
    assert result["zones"][0]["cancelled"] == pytest.approx(0)


@pytest.mark.asyncio
async def test_repeated_positive_dips_do_not_ratchet_cancelled_budget(live):
    entity, ledger, start = prepare(live, False)
    for at, output in ((0, 23.7), (120, 0.7), (180, 23.8), (240, 0.8), (300, 23.8)):
        live.clock.now = start + at
        entity._control_output = output
        await entity.apply()
    assert ledger.credit == pytest.approx(916.8 - 447.2 - 300)
    assert ledger.requested == pytest.approx(916.8)
    assert ledger.cancelled_balance == 0
    live.clock.now = start + 600
    await entity.apply()
    assert live.state[f"{live.domain}.a"] == "off"
    assert ledger.credit == pytest.approx(-130.4)
    assert sum(action == "turn_on" for _, action, _ in live.commands) == 1


@pytest.mark.asyncio
async def test_positive_return_after_off_cannot_reopen_spent_reservation(live):
    entity, ledger, start = prepare(live, False)
    for at, output in ((0, 23.7), (120, 0.7), (600, 0.7), (1200, 23.8)):
        live.clock.now = start + at
        entity._control_output = output
        await entity.apply()
    assert live.state[f"{live.domain}.a"] == "off"
    assert ledger.credit == pytest.approx(-1047.2)
    assert not ledger.zero_revision_known
    assert sum(action == "turn_on" for _, action, _ in live.commands) == 1


async def checkpoint_minimum_tail(journal, zero_revision=True):
    entity, _, _ = prepare(journal.live, False)
    entity._control_output = 40
    await entity.apply()
    journal.advance(120)
    if zero_revision:
        entity._control_output = 0.7
    await entity.apply()
    return journal.disk.data["pwm_coordination"]["pump"]["zones"]["climate.a"]


@pytest.mark.asyncio
@pytest.mark.parametrize("offline", [0, 60])
async def test_return_during_restored_minimum_on_charges_unknown_time_once(journal, offline):
    saved = await checkpoint_minimum_tail(journal)
    assert saved["zero_revision_known"] is True
    await journal.reboot(offline=offline)
    entity = journal.live.entities[0]
    entity._heater_controller._min_open_time = entity._heater_controller._pwm_controller._min_open_time = 480
    journal.advance(60)
    entity._control_output = 40
    await entity.apply()
    ledger = journal.ledger()
    expected_remaining = 1500 - 447.2 - 180 - offline
    assert ledger.credit == pytest.approx(expected_remaining)
    assert ledger.delivered == pytest.approx(447.2 + 180)
    assert ledger.cancelled_balance == ledger.uncertain_seconds == offline
    output = f"{journal.live.domain}.a"
    journal.advance(expected_remaining - 1)
    await entity.apply()
    assert journal.live.state[output] == "on"
    journal.advance(1)
    await entity.apply()
    assert journal.live.state[output] == "off"
    assert ledger.delivered + ledger.uncertain_seconds == pytest.approx(1500)


@pytest.mark.asyncio
@pytest.mark.parametrize("interruption", ["pending_on", "reconcile_off", "output_mismatch"])
async def test_ambiguous_restored_tail_cannot_reopen_the_reservation(journal, interruption):
    saved = await checkpoint_minimum_tail(journal)
    output = f"{journal.live.domain}.a"
    if interruption == "pending_on":
        saved["pending_on"] = True
    elif interruption == "reconcile_off":
        saved["controller"]["reconcile_off"] = True
    else:
        journal.live.state[output] = "off"
    await journal.reboot(offline=60)
    assert not journal.ledger().zero_revision_known
    entity = journal.live.entities[0]
    entity._control_output = 40
    await entity.apply()
    assert journal.live.state[output] == "off"
    assert journal.ledger().credit == pytest.approx(-447.2 - 120)
    assert journal.ledger().cancelled_balance == pytest.approx(1500)
    assert sum(action == "turn_on" for _, action, _ in journal.live.commands) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("zero_revision", [False, True])
async def test_expired_restored_on_ends_before_current_budget_can_run(journal, zero_revision):
    await checkpoint_minimum_tail(journal, zero_revision)
    await journal.reboot(offline=7250)
    entity = journal.live.entities[0]
    entity._control_output = 40
    output = f"{journal.live.domain}.a"
    await entity.apply()
    assert journal.live.state[output] == "off"
    ledger = journal.ledger()
    assert ledger.requested == pytest.approx(0 if zero_revision else 1500)
    journal.advance(1)
    await entity.apply()
    assert ledger.requested == pytest.approx(1500 if zero_revision else 3000)
    assert ledger.delivered == pytest.approx(447.2 + 120)
    assert ledger.credit == pytest.approx(1500 - (447.2 + 120) if zero_revision else 1500)
    assert ledger.next_budget_at - ledger.budget_anchor_at == 3 * 3600
    journal.advance(598)
    await entity.apply()
    assert journal.live.state[output] == "off"
    journal.advance(1)
    await entity.apply()
    assert journal.live.state[output] == "on"


@pytest.mark.asyncio
@pytest.mark.parametrize("continuous", [False, True])
async def test_expired_legacy_tail_preserves_minimum_on_and_continuous_demand(journal, continuous):
    entity, other = journal.live.entities
    entity._control_output = other._control_output = 0
    await entity.apply()
    journal.advance(3240)
    entity._control_output = 40
    await entity.apply()
    output = f"{journal.live.domain}.a"
    assert journal.live.state[output] == "on"
    saved = journal.disk.data["pwm_coordination"]["pump"]["zones"]["climate.a"]
    saved["next_at"] = saved["at"] + 360  # v13 used the shared period boundary.
    await journal.reboot(offline=361)
    entity = journal.live.entities[0]
    if continuous:
        entity._control_output = 100
    await entity.apply()
    assert journal.live.state[output] == "on"
    remaining_minimum = entity._heater_controller.effective_min_open_time - 361
    journal.advance(remaining_minimum - 1)
    await entity.apply()
    assert journal.live.state[output] == "on"
    journal.advance(1)
    await entity.apply()
    assert journal.live.state[output] == ("on" if continuous else "off")
    assert journal.ledger().requested == (5100 if continuous else 1500)


@pytest.mark.asyncio
@pytest.mark.parametrize("corruption", ["flag", "allocation", "accumulator_debit", "continuous"])
async def test_invalid_provenance_cannot_authorize_a_restored_budget(journal, corruption):
    saved = await checkpoint_minimum_tail(journal)
    if corruption == "flag":
        saved["zero_revision_known"] = "true"
    elif corruption == "allocation":
        saved["allocation"] = 1
    elif corruption == "accumulator_debit":
        saved["pulse"][1] = 1
    else:
        saved["pulse"][2] = True
    await journal.reboot()
    assert journal.live.registry.groups[0].mode == "fallback"
    assert journal.live.registry.groups[0].reason == "restart_state_invalid"
