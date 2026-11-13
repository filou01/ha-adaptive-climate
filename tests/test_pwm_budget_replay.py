"""The recorded-input runner audits electrical pulse length and grant provenance."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from replay_pwm_budgets import replay


@pytest.mark.asyncio
async def test_recorded_zero_crossing_cannot_pass_only_by_balancing_the_ledger(monkeypatch):
    from custom_components.adaptive_climate.managers import pwm_controller

    monkeypatch.setattr(pwm_controller, "time", pwm_controller.time)
    trace = {
        "duration": 2800,
        "origin": -2630.43,
        "profiles": [{"target": 22.8, "mode": "heat"}],
        "updates": [
            {"at": at, "zone": 0, "output": output, "target": 22.8, "mode": "heat"}
            for at, output in [(0, 20.5), (592.26, 0), (599.97, 20.9)]
        ],
    }
    result = await replay(trace)
    assert not result["duplicate_grants"]
    zone = result["zones"][0]
    assert zone["ledger_residual"] == pytest.approx(0)
    assert zone["maximum_on_seconds"] <= 615
    assert zone["starts"] == 1
    assert result["budget_events"]
