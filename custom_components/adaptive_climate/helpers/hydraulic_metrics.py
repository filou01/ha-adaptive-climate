"""Exact event-interval hydraulic competition proxies, shared by HA and CLI.

No Home Assistant imports, filesystem access, sampling loop or persistence.
Weights model competition, not measured flow or physical valve positions.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import isfinite, sqrt
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, order=True)
class HydraulicEvent:
    time: float
    entity: str
    state: bool | None


class Moments:
    """Mergeable duration-weighted first/second moments; never average scores."""

    def __init__(self) -> None:
        self.seconds = self.total = self.squares = 0.0

    def add(self, value: float, seconds: float) -> None:
        self.seconds += seconds
        self.total += value * seconds
        self.squares += value * value * seconds

    @property
    def mean(self) -> float:
        return self.total / self.seconds if self.seconds else 0.0

    @property
    def variance(self) -> float:
        return max(0.0, self.squares / self.seconds - self.mean**2) if self.seconds else 0.0


def analyze(
    events: list[HydraulicEvent],
    weights: dict[str, float],
    start: float,
    end: float,
    initial: dict[str, bool | None] | None = None,
    exclusions: list[tuple[float, float]] | None = None,
    minimum_pulse_seconds: float = 0.0,
) -> dict[str, Any]:
    """Integrate simultaneous events atomically, treating unknowns explicitly.

    A score needs >=60 valid active seconds and >=2 complete valid pulses.
    No OFF state is invented before the first event. Events before start can
    establish its state but never manufacture a boundary start. Initial values
    are verified states immediately before start. End is exclusive.
    """
    if not isfinite(start) or not isfinite(end) or end <= start:
        raise ValueError("Expected finite start < end")
    if not weights or any(not isfinite(w) or w <= 0 for w in weights.values()):
        raise ValueError("Expected finite positive hydraulic weights")
    if minimum_pulse_seconds < 0 or not isfinite(minimum_pulse_seconds):
        raise ValueError("Expected finite nonnegative minimum pulse duration")
    states = dict.fromkeys(weights)
    if initial:
        states.update({k: v for k, v in initial.items() if k in weights})
    changes: dict[float, dict[str, bool | None]] = {}
    for event in sorted(events, key=lambda e: (e.time, e.entity)):
        if not isfinite(event.time) or event.entity not in weights:
            continue
        if event.time < start:
            states[event.entity] = event.state
        elif event.time < end:
            existing = changes.setdefault(event.time, {})
            # Input order breaks ties for one entity. Different entities at
            # the same instant are applied together, without false pump edges.
            existing[event.entity] = event.state
    excluded = exclusions or []
    points = {start, end, *changes}
    for a, b in excluded:
        if b <= a:
            raise ValueError("Invalid exclusion window")
        points.update(t for t in (a, b) if start < t < end)
    times = sorted(points)
    pulses: dict[str, list[dict[str, Any]]] = {k: [] for k in weights}
    running: dict[str, dict[str, Any]] = {}
    totals = {k: Moments() for k in weights}
    solo = dict.fromkeys(weights, 0.0)
    load_changes = dict.fromkeys(weights, 0)
    previous_r: dict[str, float] = {}
    coverage = weighted_overlap = pump_seconds = pump_known = 0.0
    starts: list[float] = []
    pump_spells: list[dict[str, Any]] = []

    def pump_state(values: dict[str, bool | None]) -> bool | None:
        if any(v is True for v in values.values()):
            return True
        return False if all(v is False for v in values.values()) else None

    previous = states.copy()
    last_pump = pump_state(previous)

    def finish(entity: str, at: float, censored: bool) -> None:
        pulse = running.pop(entity)
        moments = pulse.pop("moments")
        pulse.update(
            end=at,
            duration_seconds=at - pulse["start"],
            right_censored=censored,
            valid_seconds=moments.seconds,
            mean_competing_load=moments.mean,
            intra_pulse_variation=sqrt(moments.variance),
            sum_r_seconds=moments.total,
            sum_r2_seconds=moments.squares,
        )
        pulse["overlap_seconds"] = moments.seconds - pulse["solo_seconds"]
        pulse["short_pulse"] = pulse["duration_seconds"] < minimum_pulse_seconds
        pulse["valid_complete"] = (
            not pulse["left_censored"] and not censored and abs(moments.seconds - pulse["duration_seconds"]) < 1e-6
        )
        if pulse["duration_seconds"] > 0:
            pulses[entity].append(pulse)
        previous_r.pop(entity, None)

    for index, at in enumerate(times[:-1]):
        states.update(changes.get(at, {}))
        visible = states.copy()
        if any(a <= at < b for a, b in excluded):
            visible = dict.fromkeys(weights)
        current_pump = pump_state(visible)
        if current_pump is True and last_pump is False:
            starts.append(at)
        if not pump_spells or pump_spells[-1]["state"] != current_pump:
            pump_spells.append({"start": at, "end": at, "state": current_pump})
        dt = times[index + 1] - at
        pump_spells[-1]["end"] = at + dt
        if current_pump is not None:
            pump_known += dt
        if current_pump:
            pump_seconds += dt
        last_pump = current_pump
        for entity in weights:
            if entity in running and visible[entity] is not True:
                finish(entity, at, visible[entity] is None)
            if visible[entity] is True and entity not in running:
                running[entity] = {
                    "entity": entity,
                    "start": at,
                    "left_censored": previous[entity] is not False,
                    "moments": Moments(),
                    "solo_seconds": 0.0,
                    "max_competing_load": 0.0,
                    "competing_load_changes": 0,
                }
        valid = all(v is not None for v in visible.values())
        if valid:
            coverage += dt
            active = [k for k in weights if visible[k]]
            load = sum(weights[k] for k in active)
            weighted_overlap += dt * sum(weights[a] * weights[b] for n, a in enumerate(active) for b in active[n + 1 :])
            for entity in active:
                relative = (load - weights[entity]) / load
                totals[entity].add(relative, dt)
                pulse = running[entity]
                pulse["moments"].add(relative, dt)
                pulse["max_competing_load"] = max(pulse["max_competing_load"], relative)
                if entity in previous_r and abs(relative - previous_r[entity]) > 1e-12:
                    load_changes[entity] += 1
                    pulse["competing_load_changes"] += 1
                previous_r[entity] = relative
                if len(active) == 1:
                    solo[entity] += dt
                    pulse["solo_seconds"] += dt
        else:
            previous_r.clear()
        previous = visible
    for entity in list(running):
        finish(entity, end, True)
    summaries = {}
    for entity, moments in totals.items():
        valid_pulses = sum(p["valid_complete"] for p in pulses[entity])
        pulse_means = Moments()
        within = 0.0
        for pulse in pulses[entity]:
            duration = pulse["valid_seconds"]
            pulse_means.add(pulse["mean_competing_load"], duration)
            within += duration * pulse["intra_pulse_variation"] ** 2
        sufficient = moments.seconds >= 60 and valid_pulses >= 2
        summaries[entity] = {
            "status": "ok" if sufficient else "insufficient_data",
            "score": max(0.0, min(100.0, 100 * (1 - 2 * sqrt(moments.variance)))) if sufficient else None,
            "solo_runtime_pct": 100 * solo[entity] / moments.seconds if moments.seconds else None,
            "mean_competing_load": moments.mean if moments.seconds else None,
            "intra_pulse_variation": sqrt(within / moments.seconds) if moments.seconds else None,
            "inter_pulse_variation": sqrt(pulse_means.variance) if pulse_means.seconds else None,
            "competing_load_changes": load_changes[entity],
            "observation_duration_seconds": moments.seconds,
            "observation_window_hours": (end - start) / 3600,
            "valid_heating_pulses": valid_pulses,
            "total_heating_pulses": len(pulses[entity]),
            "solo_seconds": solo[entity],
            "sum_r_seconds": moments.total,
            "sum_r2_seconds": moments.squares,
        }
    complete_on = [
        p["end"] - p["start"] for p in pump_spells if p["state"] is True and p["start"] > start and p["end"] < end
    ]
    complete_off = [
        p["end"] - p["start"] for p in pump_spells if p["state"] is False and p["start"] > start and p["end"] < end
    ]
    return {
        "start": start,
        "end": end,
        "coverage_seconds": coverage,
        "pump_known_seconds": pump_known,
        "pump_runtime_seconds": pump_seconds,
        "reconstructed_pump_starts": len(starts),
        "pump_start_times": starts,
        "average_complete_on_seconds": sum(complete_on) / len(complete_on) if complete_on else None,
        "average_complete_off_seconds": sum(complete_off) / len(complete_off) if complete_off else None,
        "weighted_overlap_seconds": weighted_overlap,
        "zones": summaries,
        "pulses": [p for values in pulses.values() for p in values],
        "pump_spells": pump_spells,
    }


class HydraulicTracker:
    """Transition-only bounded memory, 24h rolling window, minute-cached reports."""

    def __init__(self, weights: dict[str, float], start: float, window: float = 86400) -> None:
        self.weights = weights.copy()
        self.start = start
        self.window = window
        self.events: deque[HydraulicEvent] = deque()
        self.initial: dict[str, bool | None] = dict.fromkeys(weights)
        self.current: dict[str, bool | None] = dict.fromkeys(weights)
        self._cache: dict[str, Any] = {}
        self._cache_key: tuple | None = None
        self._sampled_at = start
        self._lifetime = {entity: Moments() for entity in weights}
        self._lifetime_solo = dict.fromkeys(weights, 0.0)
        self.collection_id = uuid4().hex

    def observe(self, now: float, states: dict[str, bool | None]) -> None:
        elapsed = max(0.0, now - self._sampled_at)
        if all(v is not None for v in self.current.values()):
            active = [k for k, value in self.current.items() if value]
            load = sum(self.weights[k] for k in active)
            for entity in active:
                self._lifetime[entity].add((load - self.weights[entity]) / load, elapsed)
                if len(active) == 1:
                    self._lifetime_solo[entity] += elapsed
        self._sampled_at = now
        for entity in self.weights:
            value = states.get(entity)
            if value != self.current[entity]:
                self.events.append(HydraulicEvent(now, entity, value))
                self.current[entity] = value
                self._cache_key = None
        cutoff = max(self.start, now - self.window)
        while self.events and (self.events[0].time < cutoff or len(self.events) > 20000):
            event = self.events.popleft()
            self.initial[event.entity] = event.state
            self.start = max(self.start, event.time)

    def diagnostics(self, now: float, entity: str) -> dict[str, Any]:
        start = max(self.start, now - self.window)
        if now <= start:
            return {"status": "insufficient_data", "score": None, "valid_heating_pulses": 0}
        key = (int(now // 60), start if start == self.start else None, len(self.events))
        if self._cache_key != key:
            self._cache = analyze(list(self.events), self.weights, start, now, self.initial)["zones"]
            for name, values in self._cache.items():
                total = self._lifetime[name]
                values.update(
                    collection_id=self.collection_id,
                    cumulative_active_seconds=total.seconds,
                    cumulative_solo_seconds=self._lifetime_solo[name],
                    cumulative_r_seconds=total.total,
                    cumulative_r2_seconds=total.squares,
                )
            self._cache_key = key
        return self._cache[entity].copy()
