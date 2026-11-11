"""Deterministic four-zone replay; fake disk counts actual serialized payloads."""

import copy
from datetime import datetime, timezone
import hashlib
import json
import inspect
import sys
from time import perf_counter
from types import SimpleNamespace

from custom_components.adaptive_climate.adaptive import persistence
from custom_components.adaptive_climate.managers import pwm_coordination
from test_pwm_load_balancing import Simulation


async def benchmark(monkeypatch, scenario, cadence, strategy, recorded=None, overlap=240):
    durations = (0, 0, 0, 0) if scenario == "idle" or recorded is not None else (720, 540, 360, 360)
    if scenario == "continuous":
        durations = (3600,) * 4
    sim = Simulation(durations, strategy)
    sim.manager.overlap = overlap
    totals = {"writes": 0, "bytes": 0, "by_key": {}}
    totals["writes_by_kind"] = {}
    phase = SimpleNamespace(kind="migration")
    disk = {
        persistence.STORAGE_KEY: {
            "version": persistence.STORAGE_VERSION,
            "zones": {str(i): {"history": [{"overshoot": 0.1, "samples": [0.1] * 24}] * 32} for i in range(4)},
        }
    }

    class Store:
        pwm_write_acknowledged = True

        async def async_load(self):
            return copy.deepcopy(disk.get(self.key))

        async def async_save(self, data):
            payload = json.dumps(data, allow_nan=False, separators=(",", ":")).encode()
            totals["writes"] += 1
            totals["bytes"] += len(payload)
            totals["by_key"][self.key] = totals["by_key"].get(self.key, 0) + 1
            totals["writes_by_kind"][phase.kind] = totals["writes_by_kind"].get(phase.kind, 0) + 1
            disk[self.key] = json.loads(payload)

        def __init__(self, key):
            self.key = key

    monkeypatch.setattr(persistence, "_create_store", lambda hass, version, key: Store(key))
    from custom_components.adaptive_climate.managers import pwm_restart

    try:
        from custom_components.adaptive_climate.managers import pwm_storage

        monkeypatch.setattr(pwm_storage, "create_store", lambda hass, key, version: Store(key))
    except ImportError:
        pass
    monkeypatch.setattr(pwm_coordination, "time", SimpleNamespace(monotonic=lambda: sim.now))
    monkeypatch.setattr(
        pwm_coordination,
        "dt_util",
        SimpleNamespace(utcnow=lambda: datetime.fromtimestamp(1735689600 + sim.now, timezone.utc)),
    )
    for zone in sim.zones:
        zone.restart_force_off = False
        zone.checkpoint_state = lambda now, wall, z=zone: {
            "outputs": list(z.outputs),
            "on": z.on,
            "reconcile_off": False,
            "switch_at": wall + z.last_change - now,
            "accumulator": 0.0,
            "accumulator_at": None,
            "opened_at": None,
            "closed_at": None,
            "q_at_close": 0.0,
        }
    store = persistence.LearningDataStore(SimpleNamespace())
    await store.async_load()
    registry = pwm_coordination.PWMCoordinationRegistry(SimpleNamespace(), {"groups": []})
    registry.groups = [sim.manager]
    await registry.async_initialize(store)
    original = sim.manager._reconcile
    source, first_line = inspect.getsourcelines(original)
    ordinary_line = max(first_line + i for i, line in enumerate(source) if "await self.save_checkpoint(" in line)
    counters = {"reconciles": 0, "checkpoints": 0}

    async def counted(reason):
        counters["reconciles"] += 1
        await original(reason)

    sim.manager._reconcile = counted
    checkpoint = sim.manager.checkpoint

    async def counted_checkpoint():
        counters["checkpoints"] += 1
        if hasattr(sim.manager, "checkpoint_critical"):
            critical = sim.manager.checkpoint_critical
        else:
            caller = sys._getframe(2)
            critical = caller.f_code.co_name != "_reconcile" or caller.f_lineno != ordinary_line
        phase.kind = "critical" if critical else "noncritical"
        try:
            await checkpoint()
        finally:
            phase.kind = "outside_checkpoint"

    sim.manager.checkpoint = counted_checkpoint
    started = perf_counter()
    if recorded is None:
        for tick in range(0, 86400, cadence):
            await sim.advance(tick)
            for index, zone in enumerate(sim.zones):
                if scenario == "noise":
                    zone.seconds = durations[index] + (tick // cadence % 3 - 1) * 3.6
                if scenario == "priority" and tick in (7200, 43200):
                    zone.target += 0.5
                await sim.update(index)
        await sim.advance(86400)
    else:
        for row in recorded["updates"]:
            await sim.advance(row["at"])
            index = row["zone"]
            zone = sim.zones[index]
            zone.seconds = max(0, min(100, row["output"])) * 36
            zone.target = row["target"]
            zone.mode = row["mode"]
            await sim.update(index)
        await sim.advance(recorded["duration"])
    await registry.async_save()
    elapsed = perf_counter() - started
    transitions = [z.transitions for z in sim.zones]
    ledgers = [
        dict(delivered=z.delivered, credit=z.credit, requested=z.requested, cancelled=z.cancelled_balance)
        for z in sim.manager._zones.values()
    ]
    for z in ledgers:
        assert abs(z["requested"] - z["delivered"] - z["credit"] - z["cancelled"]) < 1e-6
    return {
        "scenario": scenario,
        "cadence_seconds": cadence,
        "strategy": strategy,
        **totals,
        **counters,
        "wall_seconds": elapsed,
        "pump_starts": sim.manager.estimated_starts,
        "pump_seconds": sim.manager.energized_seconds,
        "weighted_overlap_seconds": sim.manager.weighted_overlap_seconds,
        "high_weight_overlap_seconds": sim.manager.high_weight_overlap_seconds,
        "transitions_sha256": hashlib.sha256(json.dumps(transitions).encode()).hexdigest(),
        "transitions": transitions,
        "ledgers": ledgers,
    }
