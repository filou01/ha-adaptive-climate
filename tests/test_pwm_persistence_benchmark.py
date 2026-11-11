"""Explicit opt-in 24h persistence/behavior benchmarks, not everyday unit tests."""

import json
import os
from pathlib import Path

import pytest

from pwm_benchmark_support import benchmark


@pytest.mark.skipif(not os.environ.get("PWM_BENCHMARK_OUTPUT"), reason="opt-in 24h benchmark")
@pytest.mark.parametrize("strategy", ["minimal", "maximal"])
@pytest.mark.parametrize(
    "scenario,cadence",
    [("idle", 60), ("steady", 60), ("steady", 10), ("noise", 10), ("continuous", 60), ("priority", 60)],
)
@pytest.mark.asyncio
async def test_benchmark(monkeypatch, scenario, cadence, strategy):
    result = await benchmark(monkeypatch, scenario, cadence, strategy)
    output = Path(os.environ["PWM_BENCHMARK_OUTPUT"])
    output.mkdir(parents=True, exist_ok=True)
    (output / f"{scenario}-{cadence}-{strategy}.json").write_text(json.dumps(result), encoding="utf-8")
