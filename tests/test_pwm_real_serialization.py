"""Real handovers outrank hypothetical opportunities and weight preferences."""

from dataclasses import replace

import pytest

from custom_components.adaptive_climate.managers.pwm_runtime_planner import (
    RuntimeWindow as W,
    execution_metrics,
    repair_windows,
)


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("forecast_weight", [4, 20])
def test_future_large_forecast_cannot_compress_real_children(reverse, forecast_weight):
    windows = [
        W("large", forecast_weight, 1000, 600, 1000, 1000, False, True),
        W("incoming", 1, 0, 1220, 0, 1000, True),
        W("active", 1, 0, 720, 0, 0),
    ]
    if reverse:
        windows.reverse()
    result = repair_windows(windows, "large", 120, {})
    by_id = {w.entity_id: w for w in result}
    assert by_id["incoming"].start == 600
    assert by_id["active"] == next(w for w in windows if w.entity_id == "active")
    assert by_id["large"] == next(w for w in windows if w.entity_id == "large")
    assert execution_metrics(result, "large", 120)[:3] == (1, 0, 0)


@pytest.mark.parametrize("reverse", [False, True])
def test_pending_large_zone_cannot_hide_avoidable_excess_between_small_zones(reverse):
    windows = [
        W("large", 4, 1160, 600, 1100, 1240, True),
        W("incoming", 1, 0, 1280, 0, 1240, True),
        W("active", 1, 0, 250, 0, 0),
    ]
    if reverse:
        windows.reverse()
    result = repair_windows(windows, "large", 120, {})
    metrics = execution_metrics(result, "large", 120)
    # A complete exact chain needs the large zone at 1290, beyond its deadline.
    # Fifty seconds excess is unavoidable, rather than the original 130 seconds.
    assert metrics[:3] == (1, 0, 50)
    assert metrics < execution_metrics(windows, "large", 120)
    for old, new in zip(windows, result):
        assert replace(new, start=old.start) == old
        assert old.earliest <= new.start <= old.latest


def test_feasible_three_zone_chain_has_no_excess_despite_high_weight_preference():
    windows = [
        W("large", 4, 1160, 600, 0, 1500, True),
        W("incoming", 1, 0, 1280, 0, 1500, True),
        W("active", 1, 0, 250, 0, 0),
    ]
    by_id = {w.entity_id: w for w in repair_windows(windows, "large", 120, {})}
    assert by_id["incoming"].start == 130
    assert by_id["large"].start == 1290


def test_reordering_real_successors_can_avoid_excess_with_a_tight_large_deadline():
    windows = [
        W("large", 4, 1160, 600, 0, 1240, True),
        W("incoming", 1, 0, 1280, 0, 1240, True),
        W("active", 1, 0, 250, 0, 0),
    ]
    result = repair_windows(windows, "large", 120, {})
    by_id = {w.entity_id: w for w in result}
    assert execution_metrics(result, "large", 120)[:3] == (1, 0, 0)
    assert by_id["large"].start == 130
    assert by_id["incoming"].start == 610


def test_forecast_still_connects_an_isolated_real_pulse_when_real_metrics_tie():
    windows = [W("large", 4, 1000, 600, 1000, 1000, False, True), W("real", 1, 0, 600, 0, 1500, True)]
    result = repair_windows(windows, "large", 120, {})
    assert result[1].start == 520
    assert execution_metrics(result, "large", 120) == execution_metrics(windows, "large", 120)


@pytest.mark.parametrize("fixed_forecast", [False, True])
def test_real_component_count_outranks_a_more_attractive_forecast(fixed_forecast):
    windows = [
        W("active", 1, 0, 600, 0, 0),
        W("real", 1, 1800, 600, 0, 1800, True),
        W("large", 4, 2200, 600, 2200, 2200, False, fixed_forecast),
    ]
    result = repair_windows(windows, "large", 120, {})
    assert execution_metrics(result, "large", 120)[0] <= execution_metrics(windows, "large", 120)[0]
    assert result[0] == windows[0] and result[2] == windows[2]
