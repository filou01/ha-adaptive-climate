"""Compact, acknowledged HA Store journals; no delayed safety barriers."""

from __future__ import annotations

import asyncio
import copy
from typing import Any

STORAGE_KEY = "adaptive_climate_pwm_coordination"
STORAGE_VERSION = 1
MIGRATION_MARKER = "pwm_coordination_migrated"


async def durable_save(store: Any, data: dict[str, Any]) -> None:
    """Keep the writer lock until an executor-backed write really finishes.

    Cancelling an awaiting task does not stop a filesystem executor thread.
    Drain the shielded write before propagating cancellation, so an older
    atomic replacement cannot land after a newer barrier.
    """
    task = asyncio.create_task(store.async_save(data))
    cancelled = False
    while True:
        try:
            await asyncio.shield(task)
            break
        except asyncio.CancelledError:
            if task.cancelled():
                raise
            cancelled = True
    if cancelled:
        raise asyncio.CancelledError


def create_store(hass: Any, key: str, version: int) -> Any:
    """Use HA atomic writes and acknowledge the actual completed write hook.

    Store.async_save catches SerializationError/WriteError in HA 2026.11.
    This narrow compatibility hook detects that swallowed failure, deferred
    shutdown saves, and cancellation; returning without a write is not success.
    No custom filesystem access or delayed save is used.
    """
    from homeassistant.helpers.storage import Store

    if not callable(getattr(Store, "_async_write_data", None)):
        raise RuntimeError("HA Store does not expose the required write acknowledgement hook")

    class AcknowledgedStore(Store):
        _completed_writes = 0
        pwm_write_acknowledged = True

        async def _async_write_data(self, data: dict) -> None:
            await super()._async_write_data(data)
            self._completed_writes += 1

        async def async_save(self, data: Any) -> None:
            completed = self._completed_writes
            await super().async_save(data)
            if self._completed_writes == completed:
                raise RuntimeError("PWM journal write was not acknowledged by HA Store")

    return AcknowledgedStore(hass, version, key, atomic_writes=True)


def _canonical(value: Any) -> Any:
    """Remove sub-microsecond wall/monotonic conversion noise, not real time."""
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, dict):
        return {k: _canonical(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_canonical(v) for v in value]
    return value


def durable_signature(state: dict[str, Any]) -> dict[str, Any]:
    """Ignore only reconstructible/diagnostic changes, never active delivery.

    Active elapsed consumption is deliberately retained: an active update is
    not debounced to enlarge the pre-crash uncertainty interval. Idle wall time
    and closed-allocation PID revisions cannot grant another ordinary start.
    The complete snapshot is still saved whenever this signature changes.
    """
    result = copy.deepcopy(state)
    result.pop("at", None)
    for row in result["zones"].values():
        controller = row["controller"]
        if not controller["on"] and not row["pending_on"]:
            row.pop("at", None)
        for key in (
            "priority_count",
            "priority_latency",
            "blocked_count",
            "blocked_reason",
            "max_deferral",
            "suppressed_ordinary_starts",
        ):
            row.pop(key, None)
        if controller["accumulator"] == 0:
            controller["accumulator_at"] = None
        closed = (
            not controller["on"]
            and not row["pending_on"]
            and not row["priority"]
            and row["credit"] == 0
            and row["allocation_started"]
        )
        if closed:
            for key in ("allocation", "output", "requested", "cancelled", "pulse"):
                row.pop(key, None)
    return _canonical(result)


class PWMJournalStore:
    """One lock across groups; immutable copies prevent stale writer overwrite."""

    def __init__(self, learning: Any) -> None:
        self.learning = learning
        self._store = create_store(learning.hass, STORAGE_KEY, STORAGE_VERSION)
        self._lock = asyncio.Lock()
        self.data: dict[str, Any] = {}
        self._signatures: dict[str, Any] = {}
        self.requests = self.completed_writes = self.skipped_writes = 0
        self.critical_writes = self.noncritical_writes = 0

    async def async_load(self) -> dict[str, Any]:
        raw = await self._store.async_load()
        if raw is None:
            if self.learning._data.get(MIGRATION_MARKER):
                raise ValueError("Dedicated PWM journal missing after migration; refusing stale legacy data")
            legacy = self.learning.load_pwm_coordination()
            if not isinstance(legacy, dict):
                raise ValueError("Invalid legacy PWM journals")
            raw = {"version": STORAGE_VERSION, "pwm_coordination": legacy}
            await durable_save(self._store, copy.deepcopy(raw))
            self.completed_writes += 1
        if (
            not isinstance(raw, dict)
            or raw.get("version") != STORAGE_VERSION
            or not isinstance(raw.get("pwm_coordination"), dict)
        ):
            raise ValueError("Invalid dedicated PWM journal")
        # Complete migration before any group can authorize ON. Retain legacy
        # data, but persist a tombstone so a missing new file cannot resurrect it.
        if not self.learning._data.get(MIGRATION_MARKER):
            async with self.learning._save_lock:
                marker_store = self.learning._store
                if getattr(marker_store, "pwm_write_acknowledged", False) is not True:
                    raise RuntimeError("Restart HA to initialize acknowledged learning-store migration")
                # Use the SAME Store and its write lock as delayed learning
                # saves. Publish the marker in memory first so even an already
                # scheduled data_func cannot subsequently erase the tombstone.
                self.learning._data[MIGRATION_MARKER] = STORAGE_VERSION
                await durable_save(marker_store, copy.deepcopy(self.learning._data))
        self.data = copy.deepcopy(raw["pwm_coordination"])
        self._signatures = {name: durable_signature(state) for name, state in self.data.items()}
        return copy.deepcopy(self.data)

    async def async_save(self, name: str, state: dict[str, Any], critical: bool) -> None:
        self.requests += 1
        async with self._lock:
            signature = durable_signature(state)
            if not critical and self._signatures.get(name) == signature:
                self.skipped_writes += 1
                return
            candidate = copy.deepcopy(self.data)
            candidate[name] = copy.deepcopy(state)
            await durable_save(self._store, {"version": STORAGE_VERSION, "pwm_coordination": candidate})
            self.data = candidate
            self._signatures[name] = signature
            self.completed_writes += 1
            if critical:
                self.critical_writes += 1
            else:
                self.noncritical_writes += 1
