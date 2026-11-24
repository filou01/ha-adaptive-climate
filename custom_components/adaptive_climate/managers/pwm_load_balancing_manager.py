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
from .pwm_load_balancing_optimizer import Schedule, ZoneRequest, measure, plan
from .pwm_pulse import Pulse
from .pwm_runtime_planner import RuntimeWindow, measure_windows, repair_windows
from ..helpers.hydraulic_metrics import HydraulicTracker

_LOGGER = logging.getLogger(__name__)


class ZoneAdapter(Protocol):
    """Live zone boundary. Commands must go through HeaterController."""

    entity_id: str
    period: float
    outputs: tuple[str, ...]
    restart_force_off: bool

    def continuous_demand(self) -> bool: ...

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
    def minimum_on_seconds(self) -> float: ...
    def invalidate(self) -> None: ...
    def commit_credit(self, seconds: float) -> None: ...
    def suspend_accumulation(self) -> None: ...
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
    budget_anchor_at: float | None = None
    period_delivered: float | None = 0.0
    actual_start_delay: float | None = None
    recovery_not_before: float | None = None
    allocated_now: bool = False
    restart_pending: bool = False
    pending_on: bool = False
    pending_start_epoch: int | None = None
    allocation_started: bool = False
    zero_revision_known: bool = False
    last_start_epoch: int = -1
    last_start_at: float | None = None
    last_ordinary_start_epoch: int = -1
    suppressed_ordinary_starts: int = 0
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
        self.checkpoint_critical = True
        self.reconcile_calls = 0
        self._plan_signature: tuple | None = None
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
        self._runtime_starts: dict[str, float] = {}
        self._runtime_bounds: dict[str, tuple[float, float, float, float]] = {}
        self._runtime_reasons: dict[str, str] = {}
        self._runtime_projected_starts = 0
        self._highest_weight = min(members, key=lambda entity: (-members[entity], entity))
        self._hydraulic = HydraulicTracker(members, now())
        self._timer_generation = 0
        self._timer_token = 0
        self._timer_state: tuple | None = None

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
            if self._origin is not None and self.restored_members:
                return  # A journal already restored earlier members; never reset them.
            self._origin = self._now()
            for zone in self._zones.values():
                zone.sampled_at = self._origin
                zone.observed_on = zone.adapter.active()
                elapsed = zone.adapter.active_elapsed(self._origin) if zone.observed_on else 0.0
                zone.credit = -elapsed
                zone.delivered = elapsed
                if zone.observed_on:
                    zone.last_start_epoch = 0
                    zone.last_start_at = self._origin - elapsed
                    zone.allocation_started = True
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
        self._hydraulic.observe(self._now(), dict.fromkeys(self.members))
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
            if zone.period_delivered is not None:
                zone.period_delivered += elapsed
        if observed and not zone.observed_on:
            zone.allocation_started = True
            zone.last_start_epoch = max(zone.last_start_epoch, self.period_epoch(now))
            zone.last_start_at = now
            zone.actual_start_delay = max(0.0, now - zone.owed_since) if zone.owed_since is not None else None
            # Observed edges spend a reservation; they do not move its clock.
            # next_budget_at advances only when a logical entitlement is issued.
            # A user/priority transaction explicitly starts a fresh cadence and
            # spends its following allowance, unlike a hydraulic timing repair.
            if zone.priority:
                zone.budget_anchor_at = now
                zone.next_budget_at = now + self._period
        if not observed:
            zone.zero_revision_known = False
        zone.observed_on, zone.sampled_at = observed, now
        self._metrics(now)

    def _metrics(self, now: float) -> None:
        elapsed = max(0.0, now - self._pump_sample)
        active = self._observed_group
        if active:
            self.energized_seconds += elapsed
        if len(active) > 1:
            highest = self._highest_weight
            if highest in active:
                self.high_weight_overlap_seconds += elapsed
            ordered = sorted(active)
            self.weighted_overlap_seconds += elapsed * sum(
                self.members[a] * self.members[b] for n, a in enumerate(ordered) for b in ordered[n + 1 :]
            )
        current = {entity for entity, zone in self._zones.items() if zone.adapter.active()}
        self._hydraulic.observe(
            now,
            {
                entity: (zone.adapter.active() if self.mode == "active" and zone.adapter.available() else None)
                for entity, zone in self._zones.items()
            },
        )
        if current and not active:
            self.estimated_starts += 1
        self._observed_group, self._pump_sample = current, now

    def observe(self, entity_id: str) -> None:
        """Stamp observed edges synchronously, including during awaited commands."""
        zone = self._zones.get(entity_id)
        if zone is not None:
            self._sample(zone, self._now())

    def period_epoch(self, now: float) -> int:
        """Stable group-origin period of an observed start, independent of phase."""
        if self._origin is None or self._period <= 0:
            return -1
        return int((now - self._origin) // self._period)

    def _suppress_ordinary_restart(self, zone: Ledger, now: float) -> bool:
        """A prior start also spends ordinary allowance when it was a priority pulse.

        Withdraw unserviceable positive adjustments, keeping signed overdelivery
        debt. They must not become a later minimum-length catch-up pulse.
        """
        if (
            zone.adapter.active()
            or zone.priority
            or zone.pulse.continuous
            or (not zone.allocation_started and zone.last_start_epoch < self.period_epoch(now))
        ):
            return False
        if zone.credit > 0:
            zone.cancelled_balance += zone.credit
            zone.credit = 0.0
            zone.suppressed_ordinary_starts += 1
        zone.owed_since = None
        return True

    def _allocate(self, zone: Ledger, now: float) -> None:
        adapter = zone.adapter
        zone.allocated_now = False
        if zone.restart_pending and not adapter.ready():
            return
        zone.restart_pending = False
        if not adapter.eligible():
            adapter.suspend_accumulation()
            # Revoke only undelivered positive credit. Keep minimum-ON debt
            # and the revision baseline of an already started allocation:
            # a transient zero can leave the physical output ON until its
            # minimum expires. Resetting that baseline would grant a second
            # full ordinary pulse when demand returns before the OFF edge.
            zone.cancelled_balance += max(0.0, zone.credit)
            zone.credit = min(0.0, zone.credit)
            if not zone.allocation_started:
                zone.allocation = 0.0
            zone.pulse = Pulse(0.0)
            zone.priority = False
            zone.owed_since = None
            zone.target_signature = adapter.signature()
            return
        if self._origin is None:
            return
        if zone.epoch < 0 and zone.next_budget_at is not None and zone.observed_on and not adapter.continuous_demand():
            # A restored expired reservation has no allocation, but can still
            # have an ON tail. Let it end under the normal minimum-ON guard
            # before issuing another ordinary budget on the existing lattice.
            return
        output = adapter.output()
        signature = adapter.signature()
        changed = signature != zone.target_signature or zone.pending_priority
        logical_epoch = self.period_epoch(now)
        new_epoch = zone.epoch < 0 or (
            logical_epoch > zone.epoch and (zone.next_budget_at is None or now >= zone.next_budget_at or changed)
        )
        if zone.epoch >= 0 and output < 100:
            # Keep one revisable reservation until it has actually run. A
            # global epoch crossing cannot merge another period into an active
            # or still deferred ordinary pulse. Missed slots are not a backlog.
            if zone.observed_on or (
                not changed
                and (
                    (zone.credit > 0 and not zone.allocation_started)
                    or (zone.next_budget_at is not None and now < zone.next_budget_at)
                )
            ):
                new_epoch = False
        if (
            new_epoch
            and zone.epoch >= 0
            and not changed
            and not zone.pulse.continuous
            and zone.last_start_epoch >= logical_epoch
        ):
            # The previous reservation spent this observed start allowance.
            # Wait for its next boundary, retaining a still-serviceable new
            # window. Only releases ending before that boundary are missed.
            new_epoch = False
            next_start_period = self._origin + (logical_epoch + 1) * self._period
            if zone.next_budget_at is not None and zone.next_budget_at + self._period <= next_start_period:
                zone.next_budget_at += int((next_start_period - zone.next_budget_at) // self._period) * self._period
        low_duty = zone.pulse.accumulator_debit > 0
        if low_duty and (zone.observed_on or zone.credit > 0) and not changed:
            # A reserved accumulator pulse is not replaced on ordinary PID ticks.
            if zone.next_budget_at is not None and zone.next_budget_at <= now:
                skipped = int((now - zone.next_budget_at) // self._period) + 1
                zone.next_budget_at += skipped * self._period
            return
        if (
            low_duty
            and not zone.observed_on
            and zone.credit <= 0
            and not new_epoch
            and not changed
            and output == zone.output_value
            and (zone.allocation_started or zone.last_start_epoch >= logical_epoch)
        ):
            # Keep earning raw low-duty credit without minting repeated pulse
            # reservations while this period's start allowance is consumed.
            adapter.prepare(now)
            return
        if low_duty and not zone.observed_on and zone.credit <= 0:
            zone.allocation = 0.0
            zone.pulse = Pulse(0.0)
        if new_epoch or output != zone.output_value or changed or zone.pulse.seconds == 0:
            pulse = adapter.prepare(now)
            if new_epoch:
                zone.allocation_started = zone.observed_on
                zone.period_delivered = 0.0
                # One entitlement per observed period; never replay missed
                # periods after an event-loop stall or HA restart.
                zone.credit += pulse.seconds
            else:
                adjustment = pulse.seconds - zone.allocation
                retired_baseline = (
                    zone.allocation_started
                    and zone.allocation == 0
                    and zone.pulse.seconds == 0
                    and not zone.zero_revision_known
                    and not changed
                    and not pulse.continuous
                )
                closed = (
                    not changed
                    and not zone.priority
                    and not zone.observed_on
                    and not pulse.continuous
                    and (zone.allocation_started or zone.last_start_epoch >= logical_epoch)
                )
                if retired_baseline:
                    # A v12 journal may already have erased the spent baseline
                    # during a zero-demand minimum-ON tail. It cannot prove a
                    # fresh entitlement; adopt the revision without granting it.
                    zone.cancelled_balance += adjustment
                elif closed:
                    # This period's contiguous pulse has ended. Settle BOTH
                    # signs of a later PID revision into the closed balance;
                    # otherwise alternating increases/decreases ratchet a fake
                    # negative debt when positive revisions are withdrawn.
                    zone.cancelled_balance += adjustment
                    if adjustment > 0:
                        zone.suppressed_ordinary_starts += 1
                else:
                    zone.credit += adjustment
                if changed and not zone.observed_on and pulse.seconds > 0 and zone.credit <= 0:
                    # A fresh eligible target/mode transaction can authorize a
                    # new legacy pulse even after the previous quantum was paid.
                    # Keep all delivered history; do not replay an old slot.
                    zone.credit += zone.allocation
                    zone.requested += zone.allocation
                    zone.allocation_started = False
            # A live eligible revision can legitimately prepare Pulse(0), e.g.
            # positive subminimum PID demand during minimum ON. Remember its
            # provenance: a later return revises the SAME reservation. Legacy
            # journals with an erased baseline still lack this proof and keep
            # the conservative anti-duplicate rule above.
            zone.zero_revision_known = (
                not new_epoch
                and zone.observed_on
                and zone.allocation_started
                and pulse.seconds == 0
                and (zone.allocation > 0 or zone.zero_revision_known)
            )
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
        self._suppress_ordinary_restart(zone, now)

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

    async def save_checkpoint(self, critical: bool = True) -> None:
        """A failed journal must not authorize an unrecorded heater start."""
        if self.checkpoint is not None:
            try:
                self.checkpoint_critical = critical
                await self.checkpoint()
            except Exception as err:
                raise PWMCheckpointError from err

    def _minimum_start_remaining(self, zone: Ledger, now: float) -> float:
        return max(zone.adapter.minimum_remaining(True, now), (zone.recovery_not_before or now) - now)

    def _plan_executable(self, now: float, cycle_start: float) -> None:
        """Repair timing only; all accounting and command eligibility stay authoritative."""
        if self.schedule is None or self._origin is None:
            return
        windows: list[RuntimeWindow] = []
        reasons: dict[str, str] = {}
        self._runtime_bounds = {}
        boundary = cycle_start + self._period
        horizon = boundary + self._period
        for entity, zone in self._zones.items():
            adapter = zone.adapter
            eligible = adapter.eligible()
            if adapter.active():
                remaining = max(0.0, zone.credit) if eligible else 0.0
                duration = max(remaining, adapter.minimum_remaining(False, now))
                if zone.pulse.continuous and eligible:
                    duration = horizon - now
                # Even an expiring output is still ON for this transaction:
                # successors can be commanded before its OFF, without adding
                # heater time. The epsilon is only a planning boundary marker.
                windows.append(RuntimeWindow(entity, zone.weight, now, max(0.001, duration), now, now))
                reasons[entity] = "already_on"
            elif eligible and zone.credit > 0:
                earliest = now + self._minimum_start_remaining(zone, now)
                deadline = (zone.owed_since if zone.owed_since is not None else now) + self.max_deferral
                ordinary = not zone.priority and not zone.pulse.continuous
                slot = cycle_start + self.schedule.phases[entity]
                # The reservation has a stable deadline independent of its ON
                # edge. Keep the whole pulse inside that window when physically
                # feasible, and expose the remaining flexibility to repair.
                duration = max(zone.credit, adapter.minimum_on_seconds())
                budget_end = zone.next_budget_at if zone.next_budget_at is not None else boundary
                latest = max(earliest, min(deadline, budget_end - duration)) if ordinary else earliest
                due = min(latest, max(earliest, min(max(now, slot), deadline))) if ordinary else earliest
                self._runtime_bounds[entity] = (earliest, due, latest, budget_end)
                if zone.pulse.continuous:
                    duration = max(duration, horizon - due)
                windows.append(RuntimeWindow(entity, zone.weight, due, duration, earliest, latest, ordinary))
                reasons[entity] = "ordinary_slot" if ordinary else "priority_or_continuous"
            else:
                reasons[entity] = "no_reserved_demand" if not eligible else "start_quota_or_balance"
                # A closed neighbor's next phase is advisory only. It cannot
                # spend credit, earn an allowance, or dispatch a future ON.
                future = zone.next_budget_at
                duration = zone.allocation + min(0.0, zone.credit)
                if eligible and future is not None and now < future < horizon and duration > 0:
                    future = max(
                        future,
                        self._origin + (zone.last_start_epoch + 1) * self._period,
                        now + self._minimum_start_remaining(zone, now),
                    )
                    if future < horizon:
                        duration = max(duration, adapter.minimum_on_seconds())
                        windows.append(
                            RuntimeWindow(entity, zone.weight, future, duration, future, future, forecast=True)
                        )
        highest = self._highest_weight
        repaired = (
            repair_windows(windows, highest, self.overlap, self._runtime_starts)
            if self.strategy == "minimal"
            else windows
        )
        original = {w.entity_id: w.start for w in windows}
        for window in repaired:
            if window.movable and abs(window.start - original[window.entity_id]) > 0.001:
                reasons[window.entity_id] = (
                    "handover_wait" if window.start > original[window.entity_id] else "handover_advance"
                )
        self._runtime_starts = {w.entity_id: w.start for w in repaired if not w.forecast}
        self._runtime_reasons = reasons
        self._runtime_projected_starts = measure_windows(repaired, highest, self.overlap)[0]

    async def _reconcile(self, reason: str) -> None:
        self.reconcile_calls += 1
        now = self._now()
        if any(not z.adapter.available() for z in self._zones.values()):
            self.fail("unavailable_output")
            return
        for zone in self._zones.values():
            self._sample(zone, now)
            if zone.restart_pending and zone.adapter.restart_force_off:
                if zone.adapter.eligible() and zone.adapter.continuous_demand():
                    zone.adapter.restart_force_off = False
                else:
                    generation, version = self._generation, zone.version
                    await self.save_checkpoint()
                    if generation != self._generation or version != zone.version:
                        return
                    result = await zone.adapter.command(False)
                    self._sample(zone, self._now())
                    await self.save_checkpoint()
                    if generation != self._generation or version != zone.version:
                        return
                    if result not in (ActuationResult.CHANGED, ActuationResult.UNCHANGED):
                        self.fail("restart_reconciliation_failed", release=False)
                        return
            self._allocate(zone, now)
        requests = [
            ZoneRequest(entity, min(self._period, max(0.0, zone.allocation)), zone.weight)
            for entity, zone in self._zones.items()
        ]
        plan_signature = (
            self._period,
            self.overlap,
            self.strategy,
            tuple((r.entity_id, r.on_seconds, r.weight) for r in requests),
        )
        if plan_signature != self._plan_signature:
            self.schedule = plan(requests, self._period, self.overlap, self.strategy)
            self._plan_signature = plan_signature
        self.reason = reason
        self._generation += 1
        generation = self._generation
        next_times: list[float] = []
        if self._origin is None:
            raise RuntimeError("active PWM group has no origin")
        cycle = int((now - self._origin) // self._period)
        cycle_start = self._origin + cycle * self._period
        next_times.append(cycle_start + self._period)
        for zone in self._zones.values():
            if zone.allocated_now:
                if zone.next_budget_at is None:
                    zone.budget_anchor_at = now
                    zone.next_budget_at = now + self._period
                else:
                    # Skip missed releases without adding a backlog, preserving
                    # the original phase even after a delayed execution.
                    skipped = max(1, int((now - zone.next_budget_at) // self._period) + 1)
                    zone.next_budget_at += skipped * self._period
            if zone.next_budget_at is not None and zone.next_budget_at > now:
                next_times.append(zone.next_budget_at)
        self._plan_executable(now, cycle_start)
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
                    if self._suppress_ordinary_restart(zone, self._now()):
                        continue
                    deadline = (zone.owed_since if zone.owed_since is not None else now) + self.max_deferral
                    slot = cycle_start + self.schedule.phases[entity]
                    due = now if zone.priority else min(max(now, slot), deadline)
                    minimum = self._minimum_start_remaining(zone, now)
                    if zone.priority and minimum > 0 and zone.priority_blocked_reason is None:
                        zone.priority_blocked_count += 1
                        zone.priority_blocked_reason = "minimum_off"
                    due = max(due, now + minimum)
                    due = max(now + minimum, self._runtime_starts.get(entity, due))
                else:
                    if not active or (zone.pulse.continuous and eligible):
                        continue
                    due = now + max(0.0, zone.credit) if eligible else now
                    due = max(due, now + adapter.minimum_remaining(False, now))
                if due > now + 0.001:
                    next_times.append(due)
                    continue
                version = zone.version
                was_priority = zone.priority
                was_continuous = zone.pulse.continuous
                zone.pending_on = on
                zone.pending_start_epoch = self.period_epoch(self._now()) if on else None
                await self.save_checkpoint()
                if version != zone.version or generation != self._generation:
                    zone.pending_on = False
                    zone.pending_start_epoch = None
                    return
                # Output observations can change while disk I/O yields without
                # changing demand generation. Re-read both state and allowance.
                if on and (
                    not adapter.eligible()
                    or adapter.active()
                    or zone.credit <= 0
                    or self._suppress_ordinary_restart(zone, self._now())
                ):
                    zone.pending_on = False
                    zone.pending_start_epoch = None
                    continue
                result = await adapter.command(on)
                zone.pending_on = False
                zone.pending_start_epoch = None
                sampled = self._now()
                self._sample(zone, sampled)
                if result == ActuationResult.CHANGED and on:
                    if not was_priority and not was_continuous:
                        zone.last_ordinary_start_epoch = zone.last_start_epoch
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
                if (
                    result == ActuationResult.CHANGED
                    and not on
                    and zone.next_budget_at is not None
                    and zone.next_budget_at <= sampled
                ):
                    next_times.append(sampled + 0.001)
                elif result == ActuationResult.MINIMUM_TIME:
                    next_times.append(sampled + max(1.0, adapter.minimum_remaining(on, sampled)))
        self._metrics(self._now())
        when = min(t for t in next_times if math.isfinite(t) and t > now)
        timer_state = (
            plan_signature,
            tuple(
                (entity, z.target_signature, z.observed_on, z.output_value, z.epoch, z.last_start_epoch, z.priority)
                for entity, z in self._zones.items()
            ),
        )
        reuse = (
            self._cancel is not None
            and self._next_at is not None
            and abs(when - self._next_at) < 0.000001
            and self._timer_state == timer_state
        )
        self._timer_state = timer_state
        self._timer_generation = generation
        if not reuse:
            if self._cancel is not None:
                self._cancel()
            self._next_at = when
            self._timer_token += 1
            timer_token = self._timer_token

            def wake() -> None:
                if timer_token != self._timer_token:
                    return
                self._cancel = None
                if self._timer_generation == self._generation and self.mode == "active":
                    self._task(self.update(next(iter(self._zones)), "timer"))

            self._cancel = self._later(max(0.001, when - self._now()), wake)
        await self.save_checkpoint(critical=False)

    def diagnostics(self, entity_id: str) -> dict[str, object]:
        zone = self._zones.get(entity_id)
        now = self._now()
        planned = self._runtime_starts.get(entity_id)
        safe_start = now
        delay_reason = "no_reserved_demand"
        active_requests = [
            ZoneRequest(entity, min(self._period, max(0.0, z.allocation)), z.weight)
            for entity, z in self._zones.items()
            if z.adapter.eligible()
        ]
        cyclic = measure(self._period, active_requests, self.schedule.phases) if self.schedule is not None else None
        requested_overlap = max(0.0, sum(r.on_seconds for r in active_requests) - self._period)
        if zone is not None:
            minimum = self._minimum_start_remaining(zone, now)
            safe_start += minimum
            ordinary = not zone.priority and not zone.pulse.continuous
            if zone.observed_on:
                delay_reason = "already_on"
            elif not zone.adapter.eligible():
                delay_reason = "ineligible"
            elif minimum > 0:
                delay_reason = "minimum_off"
            elif ordinary and zone.allocation_started:
                delay_reason = "period_start_allowance_spent"
            elif zone.credit <= 0:
                delay_reason = "signed_balance_or_budget_not_due"
            elif planned is not None and planned > safe_start + 0.001:
                delay_reason = "hydraulic_handover_window"
            else:
                delay_reason = "executable_budget_due"
        return {
            "group": self.name,
            "mode": self.mode,
            "reason": self.reason,
            "budget_policy": "stable_release_lattice",
            "runtime_deadline_policy": "complete_budget_within_stable_window",
            "budget_period_drift_seconds": (
                abs(
                    (zone.next_budget_at - zone.budget_anchor_at) / self._period
                    - round((zone.next_budget_at - zone.budget_anchor_at) / self._period)
                )
                * self._period
                if zone is not None
                and zone.budget_anchor_at is not None
                and zone.next_budget_at is not None
                and self._period > 0
                else None
            ),
            "actual_start_delay_seconds": zone.actual_start_delay if zone else None,
            "requested_period_budget_seconds": zone.allocation if zone else None,
            "delivered_period_budget_seconds": zone.period_delivered if zone else None,
            "unmet_period_budget_seconds": max(0.0, zone.credit) if zone else None,
            "observed_group_pump_starts": self.estimated_starts,
            "runtime_window_in_seconds": (
                dict(
                    zip(
                        ("earliest", "due", "latest", "budget_end"),
                        (at - now for at in self._runtime_bounds[entity_id]),
                    )
                )
                if entity_id in self._runtime_bounds
                else None
            ),
            "runtime_window_constraint": (
                "physical_minimum_or_late_demand"
                if entity_id in self._runtime_bounds
                and zone is not None
                and self._runtime_bounds[entity_id][0] + max(zone.credit, zone.adapter.minimum_on_seconds())
                > self._runtime_bounds[entity_id][3] + 0.001
                else None
            ),
            "scheduled_start_delay_seconds": (
                max(0.0, planned - safe_start)
                if planned is not None and zone is not None and not zone.observed_on and zone.credit > 0
                else 0.0
            ),
            "start_delay_reason": delay_reason,
            "overlap_required_seconds": requested_overlap,
            "projected_combined_overlap_seconds": (
                max(0.0, sum(r.on_seconds for r in active_requests) - cyclic.energized_seconds)
                if cyclic is not None
                else None
            ),
            "next_budget_in_seconds": (
                max(0.0, zone.next_budget_at - self._now())
                if zone is not None and zone.next_budget_at is not None
                else None
            ),
            "overlap_strategy": self.strategy,
            "handover_overlap_seconds": self.overlap,
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
            "last_start_epoch": zone.last_start_epoch if zone else -1,
            "ordinary_restart_in_seconds": (
                max(0.0, max(zone.next_budget_at, zone.recovery_not_before or self._now()) - self._now())
                if zone is not None and zone.next_budget_at is not None and zone.allocation_started
                else 0.0
            ),
            "last_ordinary_start_epoch": zone.last_ordinary_start_epoch if zone else -1,
            "suppressed_ordinary_starts": zone.suppressed_ordinary_starts if zone else 0,
            "remaining_credit_seconds": round(zone.credit, 1) if zone else 0.0,
            "unmet_debt_seconds": round(max(0.0, zone.credit), 1) if zone else 0.0,
            "priority_start_count": zone.priority_start_count if zone else 0,
            "priority_start_latency_ms": zone.priority_latency_ms if zone else None,
            "priority_start_blocked_count": zone.priority_blocked_count if zone else 0,
            "priority_start_blocked_reason": zone.priority_blocked_reason if zone else None,
            "max_ordinary_deferral_seconds": zone.max_deferral if zone else 0,
            "next_transition_in_seconds": max(0.0, self._next_at - self._now()) if self._next_at is not None else None,
            "projected_high_weight_overlap_seconds": self.schedule.high_weight_overlap_seconds if self.schedule else 0,
            "runtime_projected_starts": self._runtime_projected_starts,
            "runtime_start_in_seconds": max(0.0, self._runtime_starts[entity_id] - self._now())
            if entity_id in self._runtime_starts and zone is not None and not zone.adapter.active()
            else None,
            "runtime_plan_reason": self._runtime_reasons.get(entity_id),
            "hydraulic_consistency": self._hydraulic.diagnostics(self._now(), entity_id)
            if entity_id in self.members
            else None,
        }
