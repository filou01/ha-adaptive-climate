"""Event-driven PWM groups with observed-time ledgers and revocable requests.

The manager sees zone protocols, never HA entities or service APIs. The HA
adapter supplies fresh eligibility, command results and actual binary states.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from .heater_actuation import ActuationResult
from .pwm_load_balancing_optimizer import Schedule, ZoneRequest, plan
from .pwm_pulse import Pulse

_LOGGER = logging.getLogger(__name__)


class ZoneAdapter(Protocol):
    """Live zone boundary. Commands must go through HeaterController."""

    entity_id: str
    period: float
    outputs: tuple[str, ...]

    def ready(self) -> bool: ...
    def checkpoint_state(self, now: float, wall: float) -> dict[str, Any]: ...
    def eligible(self) -> bool: ...
    def available(self) -> bool: ...
    def active(self) -> bool: ...
    def active_elapsed(self, now: float) -> float: ...
    def output(self) -> float: ...
    def signature(self) -> tuple[object, ...]: ...
    def prepare(self, now: float) -> Pulse: ...
    def minimum_remaining(self, on: bool, now: float) -> float: ...
    def invalidate(self) -> None: ...
    def commit_credit(self, seconds: float) -> None: ...
    async def command(self, on: bool) -> ActuationResult: ...
    def release(self) -> None: ...


@dataclass
class Ledger:
    """Bounded counters; elapsed ON seconds, never planned seconds, pay debt."""

    adapter: ZoneAdapter
    weight: float
    sampled_at: float
    observed_on: bool
    credit: float = 0.0
    allocation: float = 0.0
    epoch: int = -1
    output_value: float = 0.0
    target_signature: tuple[object, ...] = ()
    pulse: Pulse = field(default_factory=lambda: Pulse(0.0))
    owed_since: float | None = None
    delivered: float = 0.0
    requested: float = 0.0
    cancelled_balance: float = 0.0
    priority: bool = False
    priority_at: float | None = None
    priority_start_count: int = 0
    priority_latency_ms: float | None = None
    version: int = 0
    pending_priority: bool = False
    next_budget_at: float | None = None
    allocated_now: bool = False
    restart_pending: bool = False
    pending_on: bool = False
    uncertain_seconds: float = 0.0
    max_deferral: float = 0.0
    priority_blocked_count: int = 0
    priority_blocked_reason: str | None = None


class PWMCheckpointError(RuntimeError):
    """The last durable PWM reservation could not be updated."""


class PWMLoadBalancingManager:
    """A single physical pump group's one-writer scheduling lifecycle."""

    def __init__(
        self,
        name: str,
        members: dict[str, float],
        overlap: float,
        max_deferral: float,
        strategy: str,
        schedule_later: Callable[[float, Callable[[], None]], Callable[[], None]],
        create_task: Callable[[object], None],
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self.name = name
        self.members = members
        self.overlap = overlap
        self.max_deferral = max_deferral
        self.strategy = strategy
        self._later = schedule_later
        self._task = create_task
        self._now = now
        self._zones: dict[str, Ledger] = {}
        self.checkpoint: Callable[[], Awaitable[None]] | None = None
        self.on_register: Callable[[], None] | None = None
        self.restored_members: set[str] = set()
        self.on_checkpoint_failure: Callable[[], Awaitable[None]] | None = None
        self._lock = asyncio.Lock()
        self._cancel: Callable[[], None] | None = None
        self._generation = 0
        self._origin: float | None = None
        self._period = 0.0
        self.mode = "waiting_for_members"
        self.reason = "startup"
        self.schedule: Schedule | None = None
        self.estimated_starts = 0
        self.energized_seconds = 0.0
        self._pump_on = False
        self._pump_sample = now()
        self._next_at: float | None = None
        self._observed_group: set[str] = set()
        self.weighted_overlap_seconds = 0.0
        self.high_weight_overlap_seconds = 0.0

    def register(self, adapter: ZoneAdapter) -> None:
        """Bind after actual entity ID, restoration and controller readiness."""
        if adapter.entity_id not in self.members or self.mode == "fallback":
            return
        if adapter.entity_id in self._zones:
            self.fail("duplicate entity registration")
            return
        self._zones[adapter.entity_id] = Ledger(adapter, self.members[adapter.entity_id], self._now(), adapter.active())
        if self.on_register is not None:
            self.on_register()
            if self.mode == "fallback":
                return
        if set(self._zones) == set(self.members):
            periods = {zone.adapter.period for zone in self._zones.values()}
            outputs = [output for zone in self._zones.values() for output in zone.adapter.outputs]
            if len(periods) != 1 or min(periods) <= 0 or len(set(outputs)) != len(outputs):
                self.fail("mixed/nonpositive PWM periods or duplicate heater outputs")
                return
            self._period = periods.pop()
            if self._origin is not None:
                return  # A journal already restored earlier members; never reset them.
            self._origin = self._now()
            for zone in self._zones.values():
                zone.sampled_at = self._origin
                zone.observed_on = zone.adapter.active()
                elapsed = zone.adapter.active_elapsed(self._origin) if zone.observed_on else 0.0
                zone.credit = -elapsed
                zone.delivered = elapsed
                zone.target_signature = zone.adapter.signature()
            self._observed_group = {entity for entity, zone in self._zones.items() if zone.observed_on}
            self._pump_sample = self._origin
            self.mode, self.reason = "active", "members_ready"

    def invalidate(self, entity_id: str, urgent: bool = False) -> None:
        """Revoke before any mode/pause/removal I/O can suspend execution."""
        self._generation += 1
        zone = self._zones.get(entity_id)
        if zone is not None:
            zone.version += 1
            zone.pending_priority = zone.pending_priority or urgent
            zone.adapter.invalidate()
        if self._cancel is not None:
            self._cancel()
            self._cancel = None

    def remove(self, entity_id: str) -> None:
        self.invalidate(entity_id)
        self._zones.pop(entity_id, None)
        self.fail("member_removed")

    def fail(self, reason: str, release: bool = True) -> None:
        """Cancel ownership first. Do not manufacture OFF/ON edges on handoff."""
        self._generation += 1
        if self._cancel is not None:
            self._cancel()
            self._cancel = None
        self.mode, self.reason = "fallback", reason
        for zone in self._zones.values():
            zone.adapter.invalidate()
            if release:
                zone.adapter.release()
        _LOGGER.warning("PWM group %s uses independent control: %s", self.name, reason)

    def _sample(self, zone: Ledger, now: float) -> None:
        observed = zone.adapter.active()
        # Samples at every command, state notification and control update. A
        # delayed callback charges the actual elapsed run, not the planned end.
        if zone.observed_on:
            elapsed = max(0.0, now - zone.sampled_at)
            zone.credit -= elapsed
            zone.delivered += elapsed
        zone.observed_on, zone.sampled_at = observed, now
        self._metrics(now)

    def _metrics(self, now: float) -> None:
        elapsed = max(0.0, now - self._pump_sample)
        active = self._observed_group
        if active:
            self.energized_seconds += elapsed
        if len(active) > 1:
            highest = min(self.members, key=lambda entity: (-self.members[entity], entity))
            if highest in active:
                self.high_weight_overlap_seconds += elapsed
            ordered = sorted(active)
            self.weighted_overlap_seconds += elapsed * sum(
                self.members[a] * self.members[b] for n, a in enumerate(ordered) for b in ordered[n + 1 :]
            )
        current = {entity for entity, zone in self._zones.items() if zone.adapter.active()}
        if current and not active:
            self.estimated_starts += 1
        self._observed_group, self._pump_sample = current, now

    def observe(self, entity_id: str) -> None:
        """Stamp observed edges synchronously, including during awaited commands."""
        zone = self._zones.get(entity_id)
        if zone is not None:
            self._sample(zone, self._now())

    def _allocate(self, zone: Ledger, now: float) -> None:
        adapter = zone.adapter
        zone.allocated_now = False
        if zone.restart_pending and not adapter.ready():
            return
        zone.restart_pending = False
        if not adapter.eligible():
            zone.cancelled_balance += zone.credit
            zone.credit = zone.allocation = 0.0
            zone.pulse = Pulse(0.0)
            zone.priority = False
            zone.owed_since = None
            zone.target_signature = adapter.signature()
            return
        if self._origin is None:
            return
        output = adapter.output()
        signature = adapter.signature()
        changed = signature != zone.target_signature or zone.pending_priority
        logical_epoch = int((now - self._origin) // self._period)
        new_epoch = (
            zone.epoch < 0
            or (zone.next_budget_at is not None and now >= zone.next_budget_at)
            or (changed and logical_epoch > zone.epoch)
        )
        low_duty = zone.pulse.accumulator_debit > 0
        if low_duty and (zone.observed_on or zone.credit > 0) and not changed:
            # A reserved accumulator pulse is not replaced on ordinary PID ticks.
            if zone.next_budget_at is not None and zone.next_budget_at <= now:
                zone.next_budget_at = now + self._period
            return
        if low_duty and not zone.observed_on and zone.credit <= 0:
            zone.allocation = 0.0
            zone.pulse = Pulse(0.0)
        if new_epoch or output != zone.output_value or changed or zone.pulse.seconds == 0:
            pulse = adapter.prepare(now)
            if new_epoch:
                # One entitlement per observed period; never replay missed
                # periods after an event-loop stall or HA restart.
                zone.credit += pulse.seconds
            else:
                zone.credit += pulse.seconds - zone.allocation
                if changed and not zone.observed_on and pulse.seconds > 0 and zone.credit <= 0:
                    # A fresh eligible target/mode transaction can authorize a
                    # new legacy pulse even after the previous quantum was paid.
                    # Keep all delivered history; do not replay an old slot.
                    zone.credit += zone.allocation
                    zone.requested += zone.allocation
            zone.requested += pulse.seconds if new_epoch else pulse.seconds - zone.allocation
            zone.allocation = pulse.seconds
            zone.pulse = pulse
            if new_epoch:
                zone.epoch = logical_epoch
                zone.allocated_now = True
            zone.output_value, zone.target_signature = output, signature
        if zone.pulse.continuous and not zone.observed_on and zone.credit <= 0:
            # Direct 100% is authoritative continuous demand, not an ordinary slot.
            extra = zone.pulse.seconds - zone.credit
            zone.requested += extra
            zone.credit += extra
        if (changed and zone.credit > 0) or (zone.pulse.continuous and not zone.priority):
            zone.priority = True
            zone.priority_at = now
            zone.priority_blocked_reason = None
        zone.pending_priority = False
        if zone.credit > 0 and zone.owed_since is None:
            zone.owed_since = now
        elif zone.credit <= 0:
            zone.owed_since = None
            zone.priority = False

    async def update(self, entity_id: str, reason: str = "control") -> bool:
        """Return True only while this group owns the normal output path."""
        if self.mode != "active" or entity_id not in self._zones:
            return False
        try:
            async with self._lock:
                if self.mode != "active":
                    return False
                await self._reconcile(reason)
        except PWMCheckpointError:
            _LOGGER.exception("PWM group %s cannot persist restart state", self.name)
            self.fail("restart_storage_error", release=False)
            if self.on_checkpoint_failure is not None:
                await self.on_checkpoint_failure()
        except Exception:
            _LOGGER.exception("PWM group %s failed", self.name)
            self.fail("scheduler_exception")
        return self.mode == "active"

    async def save_checkpoint(self) -> None:
        """A failed journal must not authorize an unrecorded heater start."""
        if self.checkpoint is not None:
            try:
                await self.checkpoint()
            except Exception as err:
                raise PWMCheckpointError from err

    async def _reconcile(self, reason: str) -> None:
        now = self._now()
        if any(not z.adapter.available() for z in self._zones.values()):
            self.fail("unavailable_output")
            return
        for zone in self._zones.values():
            self._sample(zone, now)
            self._allocate(zone, now)
        requests = [
            ZoneRequest(entity, min(self._period, max(0.0, zone.allocation)), zone.weight)
            for entity, zone in self._zones.items()
        ]
        self.schedule = plan(requests, self._period, self.overlap, self.strategy)
        self.reason = reason
        self._generation += 1
        generation = self._generation
        if self._cancel is not None:
            self._cancel()
            self._cancel = None
        next_times: list[float] = []
        if self._origin is None:
            raise RuntimeError("active PWM group has no origin")
        cycle = int((now - self._origin) // self._period)
        cycle_start = self._origin + cycle * self._period
        next_times.append(cycle_start + self._period)
        for entity, zone in self._zones.items():
            if zone.allocated_now:
                zone.next_budget_at = cycle_start + self.schedule.phases[entity] + self._period
            if zone.next_budget_at is not None and zone.next_budget_at > now:
                next_times.append(zone.next_budget_at)
        # Start genuine successors before ending predecessors at the same event.
        for on in (True, False):
            for entity, zone in self._zones.items():
                if generation != self._generation or self.mode != "active":
                    return
                adapter = zone.adapter
                active = adapter.active()
                eligible = adapter.eligible()
                if on:
                    if active or not eligible or zone.credit <= 0:
                        continue
                    deadline = (zone.owed_since if zone.owed_since is not None else now) + self.max_deferral
                    slot = cycle_start + self.schedule.phases[entity]
                    due = now if zone.priority else min(max(now, slot), deadline)
                    minimum = adapter.minimum_remaining(True, now)
                    if zone.priority and minimum > 0 and zone.priority_blocked_reason is None:
                        zone.priority_blocked_count += 1
                        zone.priority_blocked_reason = "minimum_off"
                    due = max(due, now + minimum)
                else:
                    if not active or (zone.pulse.continuous and eligible):
                        continue
                    due = now + max(0.0, zone.credit) if eligible else now
                    due = max(due, now + adapter.minimum_remaining(False, now))
                if due > now + 0.001:
                    next_times.append(due)
                    continue
                version = zone.version
                zone.pending_on = on
                await self.save_checkpoint()
                if version != zone.version or generation != self._generation:
                    zone.pending_on = False
                    return
                result = await adapter.command(on)
                zone.pending_on = False
                sampled = self._now()
                self._sample(zone, sampled)
                if result == ActuationResult.CHANGED and on:
                    adapter.commit_credit(zone.pulse.accumulator_debit)
                await self.save_checkpoint()
                if version != zone.version or generation != self._generation:
                    return
                if result in (ActuationResult.FAILED, ActuationResult.UNAVAILABLE):
                    self.fail(f"actuation_{result}")
                    return
                if result == ActuationResult.CHANGED and on:
                    if zone.priority:
                        zone.priority_start_count += 1
                        started = zone.priority_at if zone.priority_at is not None else sampled
                        zone.priority_latency_ms = 1000 * (sampled - started)
                    elif zone.owed_since is not None:
                        zone.max_deferral = max(zone.max_deferral, sampled - zone.owed_since)
                    zone.priority = False
                    next_times.append(sampled + max(0.001, zone.credit))
                elif result == ActuationResult.MINIMUM_TIME:
                    next_times.append(sampled + max(1.0, adapter.minimum_remaining(on, sampled)))
        self._metrics(self._now())
        when = min(t for t in next_times if math.isfinite(t) and t > now)
        self._next_at = when

        def wake() -> None:
            if generation == self._generation and self.mode == "active":
                self._task(self.update(next(iter(self._zones)), "timer"))

        self._cancel = self._later(max(0.001, when - self._now()), wake)
        await self.save_checkpoint()

    def diagnostics(self, entity_id: str) -> dict[str, object]:
        zone = self._zones.get(entity_id)
        return {
            "group": self.name,
            "mode": self.mode,
            "reason": self.reason,
            "overlap_strategy": self.strategy,
            "generation": self._generation,
            "estimated_pump_starts": self.estimated_starts,
            "estimated_energized_seconds": round(self.energized_seconds, 1),
            "estimated_weighted_overlap_seconds": round(self.weighted_overlap_seconds, 1),
            "estimated_high_weight_overlap_seconds": round(self.high_weight_overlap_seconds, 1),
            "projected_cyclic_starts": self.schedule.cyclic_starts if self.schedule else 0,
            "requested_seconds": round(zone.requested, 1) if zone else 0.0,
            "observed_on_seconds": round(zone.delivered, 1) if zone else 0.0,
            "cancelled_balance_seconds": round(zone.cancelled_balance, 1) if zone else 0.0,
            "restart_uncertain_seconds": round(zone.uncertain_seconds, 1) if zone else 0.0,
            "unmet_debt_seconds": round(max(0.0, zone.credit), 1) if zone else 0.0,
            "priority_start_count": zone.priority_start_count if zone else 0,
            "priority_start_latency_ms": zone.priority_latency_ms if zone else None,
            "priority_start_blocked_count": zone.priority_blocked_count if zone else 0,
            "priority_start_blocked_reason": zone.priority_blocked_reason if zone else None,
            "max_ordinary_deferral_seconds": zone.max_deferral if zone else 0,
            "next_transition_in_seconds": max(0.0, self._next_at - self._now()) if self._next_at is not None else None,
            "projected_high_weight_overlap_seconds": self.schedule.high_weight_overlap_seconds if self.schedule else 0,
        }
