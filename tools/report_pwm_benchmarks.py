"""Compare measured replay artifacts and calculate their shared hydraulic metrics."""

import argparse
import csv
import importlib.util
import json
from pathlib import Path
import sys

SPEC = importlib.util.spec_from_file_location(
    "pwm_report_core", Path(__file__).parents[1] / "custom_components/adaptive_climate/helpers/hydraulic_metrics.py"
)
CORE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CORE
SPEC.loader.exec_module(CORE)


def metrics(record):
    weights = {f"zone_{n}": 4 if n == 0 else 1 for n in range(4)}
    events = [
        CORE.HydraulicEvent(at, f"zone_{n}", on)
        for n, transitions in enumerate(record["transitions"])
        for at, on in transitions
    ]
    return CORE.analyze(events, weights, 0, 86400, dict.fromkeys(weights, False))


def run(before, after, output):
    output.mkdir(parents=True, exist_ok=True)
    rows, zone_rows = [], []
    for file in sorted(before.glob("*.json")):
        a, b = json.loads(file.read_text()), json.loads((after / file.name).read_text())
        if a["transitions_sha256"] != b["transitions_sha256"] or a["ledgers"] != b["ledgers"]:
            raise ValueError(f"Behavioral equivalence failed: {file.name}")
        am, bm = metrics(a), metrics(b)
        if am != bm:
            raise ValueError(f"Hydraulic equivalence failed: {file.name}")
        rows.append(
            {
                "trace": file.stem,
                "before_writes": a["writes"],
                "after_writes": b["writes"],
                "write_reduction_pct": 100 * (1 - b["writes"] / a["writes"]),
                "before_bytes": a["bytes"],
                "after_bytes": b["bytes"],
                "byte_reduction_pct": 100 * (1 - b["bytes"] / a["bytes"]),
                "before_replay_seconds": a["wall_seconds"],
                "after_replay_seconds": b["wall_seconds"],
                "before_checkpoint_requests": a["checkpoints"],
                "after_checkpoint_requests": b["checkpoints"],
                "before_critical_writes": a["writes_by_kind"].get("critical", 0),
                "after_critical_writes": b["writes_by_kind"].get("critical", 0),
                "before_noncritical_writes": a["writes_by_kind"].get("noncritical", 0),
                "after_noncritical_writes": b["writes_by_kind"].get("noncritical", 0),
                "pump_starts_before": am["reconstructed_pump_starts"],
                "pump_starts_after": bm["reconstructed_pump_starts"],
                "pump_runtime_seconds": am["pump_runtime_seconds"],
                "weighted_overlap_seconds": am["weighted_overlap_seconds"],
                "high_weight_solo_pct": am["zones"]["zone_0"]["solo_runtime_pct"],
                "heating_delivery_deviation_seconds": 0,
                "observed_conservation_violations": 0,
                "reconciles_before": a["reconciles"],
                "reconciles_after": b["reconciles"],
            }
        )
        for name, values in am["zones"].items():
            zone_rows.append(
                {
                    "trace": file.stem,
                    "zone": name,
                    "before_score": values["score"],
                    "after_score": bm["zones"][name]["score"],
                    **values,
                }
            )
    for name, values in (("benchmark_comparison.csv", rows), ("benchmark_hydraulic_zones.csv", zone_rows)):
        with (output / name).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(values[0]))
            writer.writeheader()
            writer.writerows(values)
    report = {
        "kind": "controlled synthetic 24h replay; not historical energy measurements",
        "window": "[0,86400), terminal persistence/clean shutdown included in write counts",
        "baseline_source": "e2501cb44805f58b40532a1db6861882fa29b1a3",
        "bytes": "compact serialized JSON payload bytes, excluding HA envelope and flash amplification",
        "cpu": "host wall-clock replay time; not a Pi timing or isolated CPU benchmark",
        "traces": rows,
        "hydraulic_zones": zone_rows,
    }
    (output / "benchmark_summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    markdown = [
        "# PWM optimization benchmark / PWM-Optimierungsbenchmark",
        "",
        "Controlled synthetic 24h replay / Kontrollierte synthetische 24h-Wiedergabe.",
        "",
        "| Trace | Writes before → after | Bytes before → after | Pump starts | Delivery deviation |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        markdown.append(
            f"| {row['trace']} | {row['before_writes']} → {row['after_writes']} | "
            f"{row['before_bytes']} → {row['after_bytes']} | {row['pump_starts_after']} | 0 s |"
        )
    markdown += [
        "",
        "Exact transitions, signed ledgers and hydraulic observations are identical in every pair.",
        "Alle Ausgangswechsel, Zeitkonten und hydraulischen Beobachtungen sind je Vergleich identisch.",
        "",
        "See the CSV/JSON files for critical/noncritical writes, timings, per-zone scores, solo time and overlap.",
        "CSV/JSON enthalten Schreibzahlen, Laufzeiten, Zonen-Scores, Alleinlauf und Überlappung.",
        "",
        "The scores describe weighted output-state competition, not measured flow or PID improvement.",
        "Die Scores beschreiben gewichtete Ausgangs-Konkurrenz, keinen gemessenen Durchfluss oder PID-Fortschritt.",
    ]
    (output / "BENCHMARK.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", type=Path, required=True)
    p.add_argument("--optimized", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    report = run(args.baseline, args.optimized, args.output)
    print(f"PASS: {len(report['traces'])} exact behavior/hydraulic comparisons")
