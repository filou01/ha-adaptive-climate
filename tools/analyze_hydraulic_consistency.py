#!/usr/bin/env python3
"""Offline HA CSV analysis. Standard library only; never imports Home Assistant."""

from __future__ import annotations

import argparse
from bisect import bisect_left
import csv
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any
from zoneinfo import ZoneInfo

CORE_PATH = Path(__file__).resolve().parents[1] / "custom_components/adaptive_climate/helpers/hydraulic_metrics.py"
SPEC = importlib.util.spec_from_file_location("adaptive_hydraulic_core", CORE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Cannot load shared hydraulic metric core")
CORE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CORE
SPEC.loader.exec_module(CORE)


def timestamp(value: str) -> float:
    result = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError(f"Timestamp requires Z or explicit timezone offset: {value}")
    return result.timestamp()


def iso(value: float, tz: ZoneInfo | timezone = timezone.utc) -> str:
    return datetime.fromtimestamp(value, tz).isoformat()


def weight(zone: dict[str, Any]) -> float:
    """Explicit flow, then circuits, then existing relative weight/default 1."""
    value = next((zone[k] for k in ("nominal_flow", "heating_circuits", "weight") if zone.get(k) is not None), 1)
    if isinstance(value, bool):
        raise ValueError("Hydraulic weight cannot be Boolean")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError("Hydraulic weights must be finite and positive")
    return result


def load_events(paths: list[Path], aliases: dict[str, str]) -> tuple[list[Any], list[str], int]:
    values: dict[tuple[float, str], bool | None] = {}
    conflicts: set[tuple[float, str]] = set()
    warnings: list[str] = []
    duplicates = 0
    for path in paths:
        files = sorted(path.glob("*.csv")) if path.is_dir() else [path]
        if not files:
            raise ValueError(f"No CSV input in {path}")
        for file in files:
            with file.open(encoding="utf-8-sig", newline="") as stream:
                for row in csv.DictReader(stream):
                    entity = aliases.get(row.get("entity_id", ""))
                    if entity is None:
                        continue
                    at = timestamp(row.get("last_changed") or row.get("last_updated") or row.get("timestamp") or "")
                    raw = row.get("state", "").strip().lower()
                    state = True if raw in ("on", "true", "1") else False if raw in ("off", "false", "0") else None
                    key = (at, entity)
                    if key in values:
                        if values[key] == state:
                            duplicates += 1
                        else:
                            conflicts.add(key)
                    values[key] = state
    for key in conflicts:
        values[key] = None
        warnings.append(f"Conflicting simultaneous states for {key[1]} at {iso(key[0])}; treated as unknown")
    return (
        [CORE.HydraulicEvent(t, entity, state) for (t, entity), state in sorted(values.items())],
        warnings,
        duplicates,
    )


def rolling_max(starts: list[float], start: float, end: float, seconds: float) -> dict[str, Any]:
    """Exact maximum on fully observed elapsed-time windows [start, end)."""
    if end - start < seconds:
        return {"starts": None, "reason": "insufficient_elapsed_window", "window_seconds": seconds}
    candidates = {start, end - seconds, *(t for t in starts if start <= t <= end - seconds)}
    best = max(sorted(candidates), key=lambda t: bisect_left(starts, t + seconds) - bisect_left(starts, t))
    count = bisect_left(starts, best + seconds) - bisect_left(starts, best)
    return {"starts": count, "start": iso(best), "end": iso(best + seconds), "window_seconds": seconds}


def calendar_windows(start: float, end: float, tz: ZoneInfo):
    cursor = start
    while cursor < end:
        local = datetime.fromtimestamp(cursor, tz)
        midnight = datetime.combine(local.date() + timedelta(days=1), datetime.min.time(), tz).timestamp()
        stop = min(end, midnight)
        yield local.date().isoformat(), cursor, stop
        cursor = stop


def write_csv(path: Path, rows: list[dict[str, Any]], defaults: list[str]) -> None:
    fields = list(dict.fromkeys([*defaults, *(k for row in rows for k in row)]))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run(args: argparse.Namespace) -> dict[str, Any]:
    config = json.loads(Path(args.mapping).read_text(encoding="utf-8-sig"))
    tz = ZoneInfo(args.timezone)
    datasets: dict[str, list[Path]] = {}
    if args.input:
        datasets[args.label] = [Path(p) for p in args.input]
    for spec in args.dataset or []:
        label, path = spec.split("=", 1)
        datasets.setdefault(label, []).append(Path(path))
    if not datasets:
        raise ValueError("Provide --input or --dataset LABEL=PATH")
    mappings = {}
    used: set[str] = set()
    for group, data in config["groups"].items():
        zones = data["zones"]
        if used.intersection(z["entity_id"] for z in zones.values()):
            raise ValueError("An entity cannot belong to multiple hydraulic groups")
        used.update(z["entity_id"] for z in zones.values())
        mappings[group] = zones
    aliases = {z["entity_id"]: f"{g}/{alias}" for g, zones in mappings.items() for alias, z in zones.items()}
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    daily_pump, daily_hc, whole_hc, pulses, rolling_pump, rolling_hc = [], [], [], [], [], []
    reports: dict[str, Any] = {}
    for label, paths in datasets.items():
        events, warnings, duplicates = load_events(paths, aliases)
        if not events:
            raise ValueError(f"Dataset {label} contains no mapped events")
        start = timestamp(args.start) if args.start else min(e.time for e in events)
        end = timestamp(args.end) if args.end else max(e.time for e in events)
        if not args.start or not args.end:
            warnings.append("Inferred dataset boundaries; edge pulses are censored, export coverage is not established")
        if not config.get("continuity_verified", False):
            warnings.append(
                "Export continuity is unverified: unchanged known states are carried forward; "
                "undetected downtime may remain"
            )
        exclusions = [(timestamp(a), timestamp(b)) for a, b in config.get("maintenance_exclusions", [])]
        if args.exclusions:
            exclusions += [(timestamp(a), timestamp(b)) for a, b in json.loads(Path(args.exclusions).read_text())]
        results = {}
        for group, zones in mappings.items():
            weights = {f"{group}/{alias}": weight(zone) for alias, zone in zones.items()}
            initial = {
                aliases[e]: (True if s == "on" else False if s == "off" else None)
                for e, s in config.get("initial_states", {}).items()
                if e in aliases and aliases[e] in weights
            }
            coverage = config.get("coverage", {})
            group_events = [e for e in events if e.entity in weights]
            # Optional per-entity declared coverage. Outside it is explicitly
            # unknown, not an inferred OFF. A boundary needs a fresh known state.
            for entity_id, windows in coverage.items():
                alias = aliases.get(entity_id)
                if alias not in weights:
                    continue
                windows = sorted((timestamp(a), timestamp(b)) for a, b in windows)
                original = [e for e in group_events if e.entity == alias]
                group_events = [e for e in group_events if e.entity != alias]
                for a, b in windows:
                    if b <= a:
                        raise ValueError("Invalid declared entity coverage")
                    group_events.extend(e for e in original if a <= e.time < b)
                    group_events.extend([CORE.HydraulicEvent(a, alias, None), CORE.HydraulicEvent(b, alias, None)])
                    # Actual event at coverage start has precedence over the
                    # unknown marker, but no prior state is guessed.
                    group_events.extend(e for e in original if e.time == a)
                initial[alias] = None
            result = CORE.analyze(group_events, weights, start, end, initial, exclusions, args.minimum_pulse_seconds)
            starts = result["pump_start_times"]
            if result["coverage_seconds"] < end - start:
                warnings.append(
                    f"{group}: some intervals have unknown group states; hydraulic data excludes those intervals"
                )
            result["rolling_24h_max"] = rolling_max(starts, start, end, 86400)
            result["rolling_7d_max"] = rolling_max(starts, start, end, 604800)
            result["average_starts_per_24h_known_time"] = (
                len(starts) * 86400 / result["pump_known_seconds"] if result["pump_known_seconds"] else None
            )
            result["average_starts_per_7d_known_time"] = (
                len(starts) * 604800 / result["pump_known_seconds"] if result["pump_known_seconds"] else None
            )
            for name, values in result["zones"].items():
                whole_hc.append(
                    {
                        "dataset": label,
                        "group": group,
                        "zone": name,
                        "display_name": zones[name.split("/", 1)[1]].get("display_name", name),
                        **values,
                    }
                )
            for pulse in result["pulses"]:
                pulses.append(
                    {
                        "dataset": label,
                        "group": group,
                        **pulse,
                        "start": iso(pulse["start"], tz),
                        "end": iso(pulse["end"], tz),
                    }
                )
            for date, a, b in calendar_windows(start, end, tz):
                day = CORE.analyze(group_events, weights, a, b, initial, exclusions)
                daily_pump.append(
                    {
                        "dataset": label,
                        "group": group,
                        "date": date,
                        "start": iso(a, tz),
                        "end": iso(b, tz),
                        "elapsed_seconds": b - a,
                        "coverage_seconds": day["coverage_seconds"],
                        "reconstructed_pump_starts": day["reconstructed_pump_starts"],
                        "pump_runtime_seconds": day["pump_runtime_seconds"],
                    }
                )
                for name, values in day["zones"].items():
                    daily_hc.append({"dataset": label, "group": group, "zone": name, "date": date, **values})
            for window in args.rolling.split(","):
                seconds = {"24h": 86400, "7d": 604800}[window]
                endpoints = {end, *(start + i * 3600 for i in range(1, int((end - start) // 3600) + 1))}
                for stop in sorted(endpoints):
                    begin = max(start, stop - seconds)
                    rolling = CORE.analyze(group_events, weights, begin, stop, initial, exclusions)
                    rolling_pump.append(
                        {
                            "dataset": label,
                            "group": group,
                            "window": window,
                            "start": iso(begin),
                            "end": iso(stop),
                            "full_window": stop - begin == seconds,
                            "coverage_seconds": rolling["coverage_seconds"],
                            "reconstructed_pump_starts": rolling["reconstructed_pump_starts"],
                            "pump_runtime_seconds": rolling["pump_runtime_seconds"],
                        }
                    )
                    for name, values in rolling["zones"].items():
                        rolling_hc.append(
                            {
                                "dataset": label,
                                "group": group,
                                "zone": name,
                                "window": window,
                                "start": iso(begin),
                                "end": iso(stop),
                                **values,
                            }
                        )
            results[group] = result
        reports[label] = {
            "label_source": "explicit user label; no date-based version inference",
            "start": iso(start),
            "end": iso(end),
            "warnings": sorted(set(warnings)),
            "duplicate_rows": duplicates,
            "groups": results,
        }
    comparison = []
    labels = list(reports)
    for label in labels[1:]:
        for group in mappings:
            before, after = reports[labels[0]]["groups"][group], reports[label]["groups"][group]
            for metric in ("reconstructed_pump_starts", "pump_runtime_seconds", "weighted_overlap_seconds"):
                comparison.append(
                    {
                        "baseline_label": labels[0],
                        "comparison_label": label,
                        "group": group,
                        "metric": metric,
                        "before": before[metric],
                        "after": after[metric],
                        "difference": after[metric] - before[metric],
                        "interpretation": "observational; heat demand, duration and coverage may differ",
                    }
                )
            for name in before["zones"]:
                for metric in (
                    "score",
                    "solo_runtime_pct",
                    "mean_competing_load",
                    "competing_load_changes",
                    "observation_duration_seconds",
                    "intra_pulse_variation",
                    "inter_pulse_variation",
                ):
                    a, b = before["zones"][name][metric], after["zones"][name][metric]
                    comparison.append(
                        {
                            "baseline_label": labels[0],
                            "comparison_label": label,
                            "group": group,
                            "zone": name,
                            "metric": metric,
                            "before": a,
                            "after": b,
                            "difference": b - a if a is not None and b is not None else None,
                            "interpretation": "observational; not causal evidence",
                        }
                    )
    for filename, rows, defaults in (
        ("pump_starts_daily.csv", daily_pump, ["dataset", "group", "date"]),
        ("hydraulic_consistency_daily.csv", daily_hc, ["dataset", "group", "zone", "date"]),
        ("hydraulic_consistency_per_zone.csv", whole_hc, ["dataset", "group", "zone"]),
        ("hydraulic_pulses.csv", pulses, ["dataset", "group", "entity", "start", "end"]),
        ("hydraulic_comparison.csv", comparison, ["baseline_label", "comparison_label", "group", "metric"]),
        ("pump_starts_rolling.csv", rolling_pump, ["dataset", "group", "window", "start", "end"]),
        ("hydraulic_consistency_rolling.csv", rolling_hc, ["dataset", "group", "zone", "window"]),
    ):
        write_csv(output / filename, rows, defaults)
    summary = {
        "metric_version": 1,
        "report_timezone": args.timezone,
        "definitions": {
            "weighted_overlap": "integral sum(i<j) w_i*w_j*I_i*I_j dt",
            "score": "clamp(100*(1-2*sqrt(E[R^2]-E[R]^2)),0,100)",
            "rolling_boundary": "[start,end), exactly 86400/604800 elapsed seconds",
            "average_spells": "only complete ON/OFF spells; censored boundaries excluded",
            "short_pulses": "retained in all raw metrics and pulse CSV; separately flagged",
        },
        "datasets": reports,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    if len(labels) == 1:
        (output / "comparison-status.txt").write_text(
            "Only one labeled dataset supplied. No independent-PWM baseline comparison can be established.\n",
            encoding="utf-8",
        )
    return summary


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--input", action="append", help="CSV file or directory (repeatable)")
    result.add_argument("--dataset", action="append", help="Explicit LABEL=CSV_OR_DIRECTORY (repeatable)")
    result.add_argument("--label", default="observed")
    result.add_argument(
        "--mapping", required=True, help="JSON group/entity mapping, weights, optional initial states/coverage"
    )
    result.add_argument("--start", help="Timezone-aware ISO start, inclusive")
    result.add_argument("--end", help="Timezone-aware ISO end, exclusive")
    result.add_argument("--timezone", default="Europe/Vienna")
    result.add_argument("--rolling", default="24h,7d", help="24h,7d or both")
    result.add_argument("--minimum-pulse-seconds", type=float, default=0)
    result.add_argument("--exclusions", help="JSON list of maintenance [start,end] timestamp pairs")
    result.add_argument("--output", required=True)
    return result


if __name__ == "__main__":
    try:
        summary = run(parser().parse_args())
        print(json.dumps({"datasets": list(summary["datasets"]), "output": "analysis completed"}))
    except (ValueError, KeyError, OSError) as error:
        raise SystemExit(str(error)) from error
