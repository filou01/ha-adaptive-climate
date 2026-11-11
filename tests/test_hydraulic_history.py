"""CSV, calendar/DST, rolling-window and mapping tests independent of HA."""

import csv
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

SPEC = importlib.util.spec_from_file_location(
    "hydraulic_cli", Path(__file__).parents[1] / "tools/analyze_hydraulic_consistency.py"
)
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)


def test_dst_calendar_is_25_hours_but_rolling_is_exact_elapsed_time():
    start = cli.timestamp("2026-10-24T00:00:00+02:00")
    end = cli.timestamp("2026-10-27T00:00:00+01:00")
    days = list(cli.calendar_windows(start, end, ZoneInfo("Europe/Vienna")))
    assert [b - a for _, a, b in days] == [86400, 90000, 86400]
    maximum = cli.rolling_max([start + 100, start + 86500], start, end, 86400)
    assert cli.timestamp(maximum["end"]) - cli.timestamp(maximum["start"]) == 86400
    assert maximum["starts"] == 1


def test_rolling_max_has_exact_window_and_excludes_right_boundary():
    r = cli.rolling_max([0, 86399, 86400, 86401], 0, 172800, 86400)
    assert r["starts"] == 3
    assert cli.timestamp(r["end"]) - cli.timestamp(r["start"]) == 86400
    assert cli.rolling_max([10], 0, 100, 86400)["starts"] is None


def test_csv_duplicates_unknown_and_conflicting_ties_are_explicit(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text(
        "entity_id,state,last_changed\n"
        "switch.a,on,2026-10-25T01:00:00Z\n"
        "switch.a,off,2026-10-25T00:00:00Z\n"
        "switch.a,on,2026-10-25T01:00:00Z\n"
        "switch.a,unavailable,2026-10-25T02:00:00Z\n"
        "switch.a,off,2026-10-25T01:00:00Z\n",
        encoding="utf-8",
    )
    events, warnings, duplicates = cli.load_events([p], {"switch.a": "a"})
    assert duplicates == 1 and warnings
    assert [e.state for e in events] == [False, None, None]
    with pytest.raises(ValueError, match="timezone"):
        cli.timestamp("2026-10-25T01:00:00")


def test_flow_circuit_weight_priority_and_validation():
    assert cli.weight({"nominal_flow": 3, "heating_circuits": 4, "weight": 9}) == 3
    assert cli.weight({"heating_circuits": 4}) == 4
    assert cli.weight({}) == 1
    with pytest.raises(ValueError):
        cli.weight({"weight": True})


def test_csv_fixture_matches_independently_calculated_overlap():
    path = Path(__file__).parent / "fixtures/hydraulic_history/partial_overlap.csv"
    events, warnings, duplicates = cli.load_events([path], {"switch.zone_a": "a", "switch.zone_b": "b"})
    start = cli.timestamp("2025-01-01T00:00:00Z")
    result = cli.CORE.analyze(events, {"a": 4, "b": 1}, start, start + 400)
    assert not warnings and duplicates == 0
    assert result["reconstructed_pump_starts"] == 2
    assert result["pump_runtime_seconds"] == 200
    assert result["zones"]["a"]["score"] == pytest.approx(80)
    assert result["weighted_overlap_seconds"] == 400


def test_local_midnight_does_not_split_whole_period_pulses():
    start = cli.timestamp("2026-10-24T23:00:00+02:00")
    end = cli.timestamp("2026-10-25T01:00:00+02:00")
    events = [
        cli.CORE.HydraulicEvent(cli.timestamp(t), "a", state)
        for t, state in [("2026-10-24T23:50:00+02:00", True), ("2026-10-25T00:10:00+02:00", False)]
    ]
    result = cli.CORE.analyze(events, {"a": 1}, start, end, {"a": False})
    assert len(result["pulses"]) == 1
    assert result["pulses"][0]["duration_seconds"] == 1200
    days = [
        cli.CORE.analyze(events, {"a": 1}, a, b, {"a": False})
        for _, a, b in cli.calendar_windows(start, end, ZoneInfo("Europe/Vienna"))
    ]
    assert [day["pump_runtime_seconds"] for day in days] == [600, 600]


def test_multi_file_multi_group_7d_and_explicit_comparison(tmp_path):
    mapping = {
        "continuity_verified": True,
        "groups": {
            "one": {"zones": {"a": {"entity_id": "switch.a", "weight": 4}}},
            "two": {"zones": {"b": {"entity_id": "switch.b", "weight": 1}}},
        },
    }
    config = tmp_path / "mapping.json"
    config.write_text(json.dumps(mapping))
    for zone in "ab":
        (tmp_path / f"{zone}.csv").write_text(
            "entity_id,state,last_changed\n"
            f"switch.{zone},off,2026-10-24T00:00:00Z\n"
            f"switch.{zone},on,2026-10-24T23:50:00Z\n"
            f"switch.{zone},off,2026-10-25T00:10:00Z\n"
            f"switch.{zone},on,2026-10-26T23:50:00Z\n"
            f"switch.{zone},off,2026-10-27T00:10:00Z\n",
            encoding="utf-8",
        )
    args = SimpleNamespace(
        mapping=str(config),
        timezone="Europe/Vienna",
        input=None,
        dataset=[f"baseline={tmp_path}", f"coordinated={tmp_path}"],
        label="observed",
        output=str(tmp_path / "result"),
        start="2026-10-24T00:00:00Z",
        end="2026-11-01T00:00:00Z",
        exclusions=None,
        minimum_pulse_seconds=1,
        rolling="24h,7d",
    )
    result = cli.run(args)
    assert set(result["datasets"]["baseline"]["groups"]) == {"one", "two"}
    assert result["datasets"]["baseline"]["groups"]["one"]["rolling_7d_max"]["starts"] == 2
    assert len(list(csv.DictReader((tmp_path / "result/hydraulic_comparison.csv").open()))) > 3
    assert (tmp_path / "result/hydraulic_consistency_rolling.csv").exists()
