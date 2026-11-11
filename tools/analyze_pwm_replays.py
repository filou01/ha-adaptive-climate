"""Convert test_pwm_simulation exports into independently labeled CSV analyses."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import analyze_hydraulic_consistency as cli


def run(source_directory: Path, output: Path) -> list[dict]:
    """Analyze the synthetic four-zone traces exported by the regression suite."""
    anchor = datetime(2025, 1, 1, tzinfo=timezone.utc)
    cases = []
    for source in sorted(source_directory.glob("*.json")):
        trace = json.loads(source.read_text(encoding="utf-8"))
        case = output / source.stem
        case.mkdir(parents=True, exist_ok=True)
        for label in ("legacy", "coordinated"):
            with (case / f"{label}.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(["entity_id", "state", "last_changed"])
                for number, transitions in enumerate(trace[label]):
                    for at, on in transitions:
                        writer.writerow(
                            [
                                f"switch.zone_{number}",
                                "on" if on else "off",
                                (anchor + timedelta(seconds=at)).isoformat(),
                            ]
                        )
        mapping = {
            "continuity_verified": True,
            "initial_states": {f"switch.zone_{n}": "off" for n in range(4)},
            "groups": {
                "pump": {
                    "zones": {
                        f"zone_{n}": {"entity_id": f"switch.zone_{n}", "weight": 4 if n == 0 else 1} for n in range(4)
                    }
                }
            },
        }
        config = case / "mapping.json"
        config.write_text(json.dumps(mapping), encoding="utf-8")
        args = cli.parser().parse_args(
            [
                "--dataset",
                f"independent-replay={case / 'legacy.csv'}",
                "--dataset",
                f"coordinated-replay={case / 'coordinated.csv'}",
                "--mapping",
                str(config),
                "--start",
                anchor.isoformat(),
                "--end",
                (anchor + timedelta(days=1)).isoformat(),
                "--rolling",
                "24h,7d",
                "--output",
                str(case),
                "--html",
            ]
        )
        result = cli.run(args)
        row = {"trace": source.stem, "kind": "controlled same-demand electrical replay; not historical measurement"}
        for label, prefix in (("independent-replay", "independent"), ("coordinated-replay", "coordinated")):
            group = result["datasets"][label]["groups"]["pump"]
            zone = group["zones"]["pump/zone_0"]
            row.update(
                {
                    f"{prefix}_starts": group["reconstructed_pump_starts"],
                    f"{prefix}_runtime_seconds": group["pump_runtime_seconds"],
                    f"{prefix}_high_weight_score": zone["score"],
                    f"{prefix}_high_weight_solo_pct": zone["solo_runtime_pct"],
                    f"{prefix}_weighted_overlap": group["weighted_overlap_seconds"],
                }
            )
        cases.append(row)
    if not cases:
        raise ValueError("No replay JSON exports found")
    (output / "controlled-comparison.json").write_text(json.dumps(cases, indent=2), encoding="utf-8")
    with (output / "controlled-comparison.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(cases[0]))
        writer.writeheader()
        writer.writerows(cases)
    return cases


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    options = parser.parse_args()
    print(f"Analyzed {len(run(options.input, options.output))} controlled replay pairs")
