"""Joint acceptance: executed heat, stable entitlement and adaptive handovers."""

from itertools import pairwise

import pytest

from test_pwm_load_balancing import Simulation
from test_pwm_restart import journal
from test_pwm_ha_integration import live
from custom_components.adaptive_climate.managers.pwm_pulse import Pulse


def configured(durations, period=3600):
    sim = Simulation(durations, period=period)
    sim.manager.overlap = period / 30
    sim.manager.max_deferral = period
    for zone in sim.zones:
        zone.min_on = zone.min_off = period / 6
    return sim


def intervals(zone):
    return [(a[0], b[0]) for a, b in pairwise(zone.transitions) if a[1] and not b[1]]


def occupancy(sim, begin, end):
    spans = [(max(a, begin), min(b, end)) for z in sim.zones for a, b in intervals(z) if a < end and b > begin]
    points = sorted({begin, end, *(x for ab in spans for x in ab)})
    union = overlap = starts = 0
    was_on = False
    for a, b in pairwise(points):
        count = sum(s <= a < e for s, e in spans)
        union += (b - a) * bool(count)
        overlap += (b - a) * max(0, count - 1)
        starts += bool(count) and not was_on
        was_on = bool(count)
    return union, overlap, starts


def balance(sim):
    for ledger in sim.manager._zones.values():
        sim.manager._sample(ledger, sim.now)
        assert ledger.requested == pytest.approx(ledger.delivered + ledger.credit + ledger.cancelled_balance)


@pytest.mark.asyncio
@pytest.mark.parametrize("period", [1800, 3600, 7200])
async def test_stable_low_load_six_executed_periods(period):
    sim = configured((period / 6, period / 6), period)
    await sim.update()
    await sim.advance(7 * period)
    for n in range(6):
        assert occupancy(sim, n * period, (n + 1) * period) == pytest.approx((period / 3 - period / 30, period / 30, 1))
    balance(sim)


@pytest.mark.asyncio
async def test_return_after_pause_repairs_inherited_phase_without_moving_budget_anchor():
    sim = configured((600, 600))
    await sim.update()
    original_release = sim.manager._zones[sim.zones[0].entity_id].next_budget_at
    await sim.advance(1800)
    sim.zones[0].seconds = 0
    await sim.update()
    await sim.advance(7553)  # New demand 127s before the neighbor's 7680s opportunity.
    sim.zones[0].seconds = 600
    await sim.update()
    await sim.advance(10799)
    first = next(ab for ab in intervals(sim.zones[0]) if ab[0] >= 7553)
    second = next(ab for ab in intervals(sim.zones[1]) if ab[0] >= 7200)
    # Feasible witness: neighbor 7680..8280, returning room 8160..8760.
    assert min(first[1], second[1]) - max(first[0], second[0]) == pytest.approx(120, abs=0.001)
    anchor = sim.manager._zones[sim.zones[0].entity_id].next_budget_at
    assert (anchor - original_release) % 3600 == pytest.approx(0, abs=0.001)
    await sim.advance(7 * 3600 - 1)
    assert (sim.manager._zones[sim.zones[0].entity_id].next_budget_at - anchor) % 3600 == pytest.approx(0, abs=0.001)
    for zone in sim.zones:
        assert all(b - a == pytest.approx(600) for a, b in intervals(zone))
        settled = [at for at, on in zone.transitions if on and at >= 3 * 3600]
        assert len(settled) >= 4
        assert all(b - a == pytest.approx(3600) for a, b in pairwise(settled))
    balance(sim)


@pytest.mark.asyncio
async def test_longer_demand_repositions_successor_and_keeps_six_full_budgets():
    sim = configured((600, 600))
    await sim.update()
    await sim.advance(3500)
    sim.zones[0].seconds = 1200
    await sim.update()
    await sim.advance(8 * 3600 - 1)
    for n in range(1, 7):
        assert occupancy(sim, n * 3600, (n + 1) * 3600) == pytest.approx((1680, 120, 1), abs=0.001)
    for n, zone in enumerate(sim.zones):
        runs = [(a, b) for a, b in intervals(zone) if 3600 <= a < 7 * 3600]
        assert len(runs) == 6
        assert all(b - a == pytest.approx((1200, 600)[n]) for a, b in runs)
    balance(sim)


@pytest.mark.asyncio
async def test_overload_delivers_eighty_minutes_with_only_necessary_combined_overlap():
    sim = configured((1800, 1200, 900, 900))
    await sim.update()
    await sim.advance(8 * 3600 - 1)
    for n in range(1, 7):
        union, overlap, _ = occupancy(sim, n * 3600, (n + 1) * 3600)
        assert union == pytest.approx(3600, abs=0.001)
        assert overlap == pytest.approx(1200, abs=0.001)
    for duration, zone in zip((1800, 1200, 900, 900), sim.zones):
        runs = [(a, b) for a, b in intervals(zone) if 3600 <= a < 7 * 3600]
        assert len(runs) == 6
        assert all(b - a == pytest.approx(duration) for a, b in runs)
    balance(sim)


@pytest.mark.asyncio
async def test_six_load_changes_preserve_release_lattice_and_observed_safety():
    sim = configured((900, 720, 600, 600))
    original = sim.manager._allocate
    grants = []

    def allocate(ledger, now):
        original(ledger, now)
        if ledger.allocated_now:
            grants.append((ledger.adapter.entity_id, now, ledger.observed_on))

    sim.manager._allocate = allocate
    await sim.update()
    profiles = [(1800, 1200, 900, 900), (900, 720, 600, 600)] * 3
    for cycle, durations in enumerate(profiles, 1):
        await sim.advance(cycle * 3600 - 1)
        for zone, duration in zip(sim.zones, durations):
            zone.seconds = duration
        await sim.update()
        await sim.advance(cycle * 3600 + 3500)
        for zone in sim.zones:
            diag = sim.manager.diagnostics(zone.entity_id)
            assert diag["budget_period_drift_seconds"] == pytest.approx(0, abs=0.001)
            assert diag["runtime_window_constraint"] is None
    await sim.advance(9 * 3600 - 1)
    assert not any(active for _, _, active in grants)
    for zone in sim.zones:
        starts = [at for at, on in zone.transitions if on]
        assert len(starts) >= 8
        assert len(starts) == len({int(at // 3600) for at in starts})
        assert all(b[0] - a[0] >= 600 - 0.001 for a, b in pairwise(zone.transitions))
        entity_grants = [at for entity, at, _ in grants if entity == zone.entity_id]
        assert len(entity_grants) == len({int(at // 3600) for at in entity_grants})
    # After the transient, full low-load budgets return to a single short chain.
    assert occupancy(sim, 8 * 3600, 9 * 3600 - 1) == pytest.approx((2460, 360, 1), abs=0.01)
    balance(sim)


@pytest.mark.asyncio
async def test_impossible_minimum_off_window_is_diagnosed_without_budget_multiplication():
    sim = configured((600,))
    sim.zones[0].min_off = 8000
    sim.zones[0].last_change = 0
    await sim.update()
    diag = sim.manager.diagnostics(sim.zones[0].entity_id)
    assert diag["runtime_window_constraint"] == "physical_minimum_or_late_demand"
    await sim.advance(8601)
    assert intervals(sim.zones[0]) == [(8000, 8600)]
    assert sim.manager._zones[sim.zones[0].entity_id].requested == 600
    balance(sim)


@pytest.mark.asyncio
async def test_hydraulic_weight_keeps_large_room_mostly_solo_under_overload():
    sim = configured((1800, 1200, 900, 900))
    await sim.update()
    await sim.advance(7 * 3600 - 1)
    # An explicit feasible plan bounds high-weight overlap to 120s per cycle.
    # This checks actual edges, including simultaneous small-room operation.
    total = 0
    for a, b in intervals(sim.zones[0]):
        points = sorted({a, b, *(max(a, min(b, t)) for z in sim.zones[1:] for ab in intervals(z) for t in ab)})
        total += sum(
            y - x for x, y in pairwise(points) if any(s <= x < e for z in sim.zones[1:] for s, e in intervals(z))
        )
    assert total <= 7 * 120 + 0.001


@pytest.mark.asyncio
async def test_release_anchor_survives_offline_missed_periods_and_monotonic_reset(journal):
    await journal.complete_first()
    saved = journal.disk.data["pwm_coordination"]["pump"]["zones"]["climate.a"]
    anchor = saved["budget_anchor_at"]
    old_next = saved["next_at"]
    await journal.reboot(offline=7250)
    await journal.live.entities[0].apply()
    row = journal.disk.data["pwm_coordination"]["pump"]["zones"]["climate.a"]
    assert row["budget_anchor_at"] == pytest.approx(anchor)
    assert (row["next_at"] - old_next) % 3600 == pytest.approx(0, abs=0.001)
    assert row["next_at"] > row["at"]
    assert row["requested"] - saved["requested"] <= 1500
    assert journal.live.registry.groups[0].diagnostics("climate.a")["budget_period_drift_seconds"] == pytest.approx(0)


@pytest.mark.asyncio
async def test_legacy_journal_migration_preserves_next_release_without_forgiving_signed_debt(journal):
    await journal.complete_first()
    saved = journal.disk.data["pwm_coordination"]["pump"]["zones"]["climate.a"]
    next_at, credit = saved["next_at"], saved["credit"]
    for key in ("budget_anchor_at", "period_delivered", "recovery_not_before"):
        saved.pop(key, None)
    await journal.reboot(offline=60)
    assert journal.ledger().credit == credit
    assert journal.ledger().period_delivered is None
    await journal.live.entities[0].apply()
    row = journal.disk.data["pwm_coordination"]["pump"]["zones"]["climate.a"]
    assert row["next_at"] == pytest.approx(next_at)
    assert row["budget_anchor_at"] == pytest.approx(next_at - 3600)


@pytest.mark.asyncio
async def test_live_shaped_minimum_pulses_retain_negative_debt_and_release_bounds():
    # Synthetic state shaped like the observed incident, not an exact journal
    # replay. Nominal PID pulses exceed remaining entitlement because previous
    # minimum-ON delivery is still owed back. Two low-weight rooms are active.
    sim = configured((0, 0, 776.4, 744))
    sim.manager._origin = -7200
    for index, debt, started, release in ((2, 746.3, -5888.459, 0), (3, 355.4, -3473.169, 126.831)):
        zone = sim.zones[index]
        ledger = sim.manager._zones[zone.entity_id]
        ledger.epoch = 1
        ledger.credit = -debt
        ledger.allocation = ledger.requested = zone.seconds
        ledger.delivered = zone.seconds + debt
        ledger.pulse = Pulse(zone.seconds)
        ledger.output_value = zone.output()
        ledger.allocation_started = True
        ledger.last_start_at = started
        ledger.last_start_epoch = sim.manager.period_epoch(started)
        ledger.last_ordinary_start_epoch = ledger.last_start_epoch
        ledger.next_budget_at = release
        ledger.budget_anchor_at = release - 3600
        zone.last_change = started + 600
    await sim.update()
    await sim.advance(1800)
    a, b = (intervals(zone)[0] for zone in sim.zones[2:])
    assert a[0] >= 0 and b[0] >= 126.831
    assert a[1] - a[0] == pytest.approx(600)
    assert b[1] - b[0] == pytest.approx(600)
    assert min(a[1], b[1]) - max(a[0], b[0]) == pytest.approx(120, abs=0.001)
    for index, end, debt in ((2, 3600, -569.9), (3, 3726.831, -211.4)):
        ledger = sim.manager._zones[sim.zones[index].entity_id]
        sim.manager._sample(ledger, sim.now)
        assert ledger.next_budget_at == pytest.approx(end)
        assert ledger.credit == pytest.approx(debt)
        assert ledger.priority_start_count == 0
    balance(sim)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "key,value",
    [
        ("period_delivered", -1),
        ("period_delivered", 1e9),
        ("budget_anchor_at", float("nan")),
        ("recovery_not_before", 1e12),
    ],
)
async def test_invalid_new_journal_fields_fail_closed(journal, key, value):
    await journal.complete_first()
    saved = journal.disk.data["pwm_coordination"]["pump"]["zones"]["climate.a"]
    saved[key] = value
    await journal.reboot()
    assert journal.live.registry.groups[0].mode == "fallback"
    assert journal.live.registry.groups[0].reason == "restart_state_invalid"


@pytest.mark.asyncio
async def test_shifted_start_quota_waits_without_discarding_a_serviceable_next_window():
    sim = configured((600,))
    sim.now = 10440
    zone = sim.zones[0]
    ledger = sim.manager._zones[zone.entity_id]
    # Releases at 3240 and 6840; their starts were 3240 and 8000.
    # Third release 10440 may run at 10800, after the actual-period quota
    # reopens, and still finish well before its stable deadline 14040.
    ledger.epoch = 1
    ledger.last_start_epoch = ledger.last_ordinary_start_epoch = 2
    ledger.last_start_at = 8000
    ledger.allocation_started = True
    ledger.allocation = 600
    ledger.pulse = Pulse(600)
    ledger.output_value = zone.output()
    ledger.requested = ledger.delivered = 1200
    ledger.next_budget_at, ledger.budget_anchor_at = 10440, 3240
    ledger.sampled_at = sim.now
    zone.last_change = 8600
    await sim.update()
    assert not zone.on
    assert ledger.requested == 1200
    await sim.advance(11401)
    assert intervals(zone) == [(10800, 11400)]
    assert ledger.requested == 1800
    assert ledger.next_budget_at == 14040
    assert ledger.cancelled_balance == 0
    balance(sim)
