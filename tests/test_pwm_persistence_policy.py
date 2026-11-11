"""Safety barriers, semantic idle, migration and cancelled-writer ordering."""

import asyncio
import copy

import pytest

from custom_components.adaptive_climate.managers import pwm_storage
from test_pwm_restart import journal, live


@pytest.mark.asyncio
async def test_unchanged_idle_does_not_write_but_shutdown_flushes(journal):
    for entity in journal.live.entities:
        entity._control_output = 0
    await journal.live.entities[0].apply()
    count = journal.disk.saves
    for _ in range(100):
        journal.advance(10)
        for entity in journal.live.entities:
            await entity.apply()
    assert journal.disk.saves == count
    await journal.live.registry.async_save()
    assert journal.disk.saves == count + 1


@pytest.mark.asyncio
async def test_active_elapsed_delivery_is_not_debounced(journal):
    await journal.live.entities[0].apply()
    count = journal.disk.saves
    for _ in range(10):
        journal.advance(1)
        await journal.live.entities[0].apply()
    assert journal.disk.saves >= count + 10


@pytest.mark.asyncio
async def test_closed_pid_noise_is_not_a_new_durable_entitlement(journal):
    journal.live.entities[1]._control_output = 0
    await journal.complete_first()
    count = journal.disk.saves
    for index in range(50):
        journal.live.entities[0]._control_output = 40 + index % 2
        journal.advance(1)
        await journal.live.entities[0].apply()
    assert journal.disk.saves == count
    assert journal.live.state[f"{journal.live.domain}.a"] == "off"


@pytest.mark.asyncio
async def test_migration_retains_legacy_and_restart_cannot_resurrect_it(journal):
    await journal.complete_first()
    legacy = copy.deepcopy(journal.disk.data["pwm_coordination"])
    journal.disk.learning["pwm_coordination"] = legacy
    journal.disk.learning.pop(pwm_storage.MIGRATION_MARKER)
    journal.disk.data = None
    await journal.reboot(offline=10)
    assert journal.disk.learning["pwm_coordination"] == legacy
    assert journal.disk.learning[pwm_storage.MIGRATION_MARKER] == 1
    await journal.live.entities[0].apply()
    assert journal.live.state[f"{journal.live.domain}.a"] == "off"
    # Loss of the dedicated file AFTER migration may not replay old entitlements.
    journal.disk.data = None
    await journal.reboot(offline=10)
    await journal.live.entities[0].apply()
    assert journal.live.registry.groups[0].reason == "restart_storage_error"
    assert journal.live.state[f"{journal.live.domain}.a"] == "off"


@pytest.mark.asyncio
async def test_failure_between_new_file_and_marker_blocks_on_then_retries(journal):
    await journal.complete_first()
    journal.disk.learning["pwm_coordination"] = copy.deepcopy(journal.disk.data["pwm_coordination"])
    journal.disk.learning.pop(pwm_storage.MIGRATION_MARKER)
    journal.disk.data = None
    journal.disk.fail_learning = True
    await journal.reboot(offline=5)
    assert journal.disk.data is not None  # New journal safely exists, old data retained.
    await journal.live.entities[0].apply()
    assert journal.live.registry.groups[0].reason == "restart_storage_error"
    journal.disk.fail_learning = False
    await journal.reboot(offline=5)
    await journal.live.entities[0].apply()
    assert journal.live.state[f"{journal.live.domain}.a"] == "off"


@pytest.mark.asyncio
async def test_cancelled_write_drains_before_newer_barrier(journal):
    journal.disk.block = True
    task = asyncio.create_task(journal.live.entities[0].apply())
    await asyncio.wait_for(journal.disk.entered.wait(), 1)
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()  # Underlying filesystem work has not finished.
    journal.disk.release.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 1)
    assert not journal.live.commands
    journal.disk.block = False
    await journal.live.entities[0].apply()
    assert journal.live.state[f"{journal.live.domain}.a"] == "on"


@pytest.mark.asyncio
async def test_dedicated_checkpoints_never_rewrite_learning_dataset(journal):
    await journal.store.async_save_zone("a", adaptive_data={"history": [1, 2, 3]})
    learning = copy.deepcopy(journal.disk.learning)
    await journal.live.entities[0].apply()
    for _ in range(30):
        journal.advance(10)
        await journal.live.entities[0].apply()
    assert journal.disk.learning == learning
    assert "zones" not in journal.disk.data  # Only per-group journal rows, not learner histories.
