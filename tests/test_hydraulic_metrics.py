"""Analytic expectations for the shared event-driven hydraulic proxy."""

import math

import pytest

from custom_components.adaptive_climate.helpers.hydraulic_metrics import HydraulicEvent as E
from custom_components.adaptive_climate.helpers.hydraulic_metrics import HydraulicTracker, analyze


def test_weighted_partial_overlap_has_independent_analytic_moments():
    events = [
        E(t, e, s)
        for t, e, s in [
            (10, "a", True),
            (60, "b", True),
            (110, "a", False),
            (110, "b", False),
            (210, "a", True),
            (260, "b", True),
            (310, "a", False),
            (310, "b", False),
        ]
    ]
    r = analyze(events, {"a": 4, "b": 1}, 0, 400, {"a": False, "b": False})
    a, b = r["zones"]["a"], r["zones"]["b"]
    assert a["score"] == pytest.approx(80)
    assert a["mean_competing_load"] == pytest.approx(0.1)
    assert a["solo_runtime_pct"] == 50
    assert a["intra_pulse_variation"] == pytest.approx(0.1)
    assert a["inter_pulse_variation"] == 0
    assert a["competing_load_changes"] == 2
    assert b["score"] == 100 and b["solo_runtime_pct"] == 0
    assert b["mean_competing_load"] == pytest.approx(0.8)
    assert r["weighted_overlap_seconds"] == 400
    assert r["reconstructed_pump_starts"] == 2
    assert r["pump_runtime_seconds"] == 200


def test_between_pulse_variation_differs_from_within_pulse_variation():
    events = [
        E(10, "a", True),
        E(110, "a", False),
        E(210, "a", True),
        E(210, "b", True),
        E(310, "a", False),
        E(310, "b", False),
    ]
    a = analyze(events, {"a": 4, "b": 1}, 0, 400, {"a": False, "b": False})["zones"]["a"]
    assert a["intra_pulse_variation"] == 0
    assert a["inter_pulse_variation"] == pytest.approx(0.1)
    assert a["score"] == pytest.approx(80)


@pytest.mark.parametrize("reverse", [False, True])
def test_simultaneous_handover_is_one_pump_run(reverse):
    events = [E(10, "a", True), E(60, "a", False), E(60, "b", True), E(110, "b", False)]
    if reverse:
        events.reverse()
    r = analyze(events, {"a": 1, "b": 1}, 0, 200, {"a": False, "b": False})
    assert r["reconstructed_pump_starts"] == 1
    assert r["weighted_overlap_seconds"] == 0
    assert r["pump_runtime_seconds"] == 100


def test_unknown_competitor_does_not_become_off_or_perfect_score():
    r = analyze([E(10, "a", True), E(50, "b", False), E(110, "a", False)], {"a": 4, "b": 1}, 0, 200)
    assert r["reconstructed_pump_starts"] == 0  # no verified OFF before first ON
    assert r["pump_runtime_seconds"] == 100  # OR is known true while a is true
    assert r["coverage_seconds"] == 150
    assert r["zones"]["a"]["observation_duration_seconds"] == 60
    assert r["zones"]["a"]["score"] is None
    assert not r["pulses"][0]["valid_complete"]


def test_unknown_downtime_splits_pulses_and_never_manufactures_restart():
    r = analyze([E(10, "a", True), E(200, "a", False)], {"a": 1}, 0, 300, {"a": False}, exclusions=[(50, 100)])
    assert r["reconstructed_pump_starts"] == 1
    assert r["pump_runtime_seconds"] == 140
    assert len(r["pulses"]) == 2
    assert r["pulses"][0]["right_censored"]
    assert r["pulses"][1]["left_censored"]


def test_long_unchanged_on_is_not_missing_but_is_boundary_censored():
    r = analyze([], {"a": 1}, 0, 604800, {"a": True})
    assert r["pump_runtime_seconds"] == 604800
    assert r["reconstructed_pump_starts"] == 0
    assert r["coverage_seconds"] == 604800
    assert len(r["pulses"]) == 1
    assert r["zones"]["a"]["score"] == 100
    assert r["zones"]["a"]["inter_pulse_variation"] is None
    assert r["zones"]["a"]["incomplete_heating_pulses"] == 1
    assert analyze([], {"a": 1}, 0, 60, {"a": True})["zones"]["a"]["score"] is None


def test_short_pulses_are_retained_and_flagged_not_filtered():
    r = analyze([E(1, "a", True), E(1.1, "a", False)], {"a": 1}, 0, 10, {"a": False}, minimum_pulse_seconds=1)
    assert r["pump_runtime_seconds"] == pytest.approx(0.1)
    assert r["pulses"][0]["short_pulse"]
    assert r["pulses"][0]["duration_seconds"] == pytest.approx(0.1)


def test_many_small_zones_competition_and_weighted_overlap():
    r = analyze(
        [E(10, z, True) for z in "abcd"] + [E(110, z, False) for z in "abcd"],
        dict.fromkeys("abcd", 1),
        0,
        200,
        dict.fromkeys("abcd", False),
    )
    assert r["weighted_overlap_seconds"] == 600  # 6 pairs * 100 seconds
    assert all(z["mean_competing_load"] == 0.75 for z in r["zones"].values())


def test_live_and_offline_use_identical_core_and_reset_to_insufficient():
    tracker = HydraulicTracker({"a": 1, "b": 1}, 0)
    events = [
        E(0, "a", False),
        E(0, "b", False),
        E(10, "a", True),
        E(110, "a", False),
        E(210, "a", True),
        E(310, "a", False),
    ]
    states = {"a": None, "b": None}
    for e in events:
        states[e.entity] = e.state
        tracker.observe(e.time, states)
    expected = analyze(events, {"a": 1, "b": 1}, 0, 400)["zones"]["a"]
    tracker.observe(400, states)
    observed = tracker.diagnostics(400, "a")
    assert {k: observed[k] for k in expected} == expected
    assert observed["cumulative_active_seconds"] == 200
    assert observed["cumulative_r_seconds"] == 0
    assert HydraulicTracker({"a": 1}, 400).diagnostics(400, "a")["score"] is None


def test_live_rolls_out_old_observations_without_storage_or_polling():
    tracker = HydraulicTracker({"a": 1}, 0, window=100)
    tracker.observe(0, {"a": False})
    tracker.observe(10, {"a": True})
    tracker.observe(20, {"a": False})
    tracker.observe(200, {"a": False})
    assert not tracker.events
    assert tracker.diagnostics(200, "a")["observation_duration_seconds"] == 0


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf")])
def test_invalid_weights_rejected(bad):
    with pytest.raises(ValueError):
        analyze([], {"a": bad}, 0, 10)
