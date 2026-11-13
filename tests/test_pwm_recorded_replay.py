"""Opt-in observed-input replay; no production data are included in the repo.

PWM_RECORDED_TRACE is JSON {duration: seconds, updates: [{at, zone, output,
target, mode}]}; zone is an integer 0..3. Updates must be time ordered.
The model maps output percent to effective duration with zero valve/min times.
It compares software versions, not physical delivery at the source installation.
"""

import json
import os
from pathlib import Path

import pytest

from pwm_benchmark_support import benchmark


@pytest.mark.skipif(
    not os.environ.get("PWM_RECORDED_ELECTRICAL_TRACE"), reason="opt-in electrical recorded-input audit"
)
@pytest.mark.asyncio
async def test_recorded_electrical_budget_provenance(monkeypatch):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    from replay_pwm_budgets import replay
    from custom_components.adaptive_climate.managers import pwm_controller

    monkeypatch.setattr(pwm_controller, "time", pwm_controller.time)
    trace = json.loads(Path(os.environ["PWM_RECORDED_ELECTRICAL_TRACE"]).read_text(encoding="utf-8"))
    result = await replay(trace)
    output = Path(os.environ["PWM_RECORDED_OUTPUT"])
    output.mkdir(parents=True, exist_ok=True)
    (output / "electrical-budget-audit.json").write_text(json.dumps(result), encoding="utf-8")
    assert not result["duplicate_grants"], "A balanced ledger must not hide resurrected spent allocations"
    assert not result["active_ordinary_period_grants"], "A global boundary must not extend an ordinary running pulse"


@pytest.mark.skipif(not os.environ.get("PWM_RECORDED_TRACE"), reason="opt-in recorded-input replay")
@pytest.mark.parametrize("overlap", [120, 240])
@pytest.mark.asyncio
async def test_recorded_input_replay(monkeypatch, overlap):
    trace = json.loads(Path(os.environ["PWM_RECORDED_TRACE"]).read_text(encoding="utf-8"))
    result = await benchmark(monkeypatch, "recorded", 0, "minimal", recorded=trace, overlap=overlap)
    result["model"] = (
        "observed inputs, cold-start effective-duration simulation; not physical historical reconstruction"
    )
    result["duration"] = trace["duration"]
    result["handover_seconds"] = overlap
    output = Path(os.environ["PWM_RECORDED_OUTPUT"])
    output.mkdir(parents=True, exist_ok=True)
    (output / f"recorded-{overlap}.json").write_text(json.dumps(result), encoding="utf-8")
