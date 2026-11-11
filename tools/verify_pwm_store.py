"""Run outside pytest's HA mocks, against an installed real Home Assistant."""

import asyncio
import errno
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading

from homeassistant.core import HomeAssistant, CoreState
from homeassistant.helpers import storage
from homeassistant.util.file import WriteError

spec = importlib.util.spec_from_file_location(
    "pwm_storage_probe", Path(__file__).parents[1] / "custom_components/adaptive_climate/managers/pwm_storage.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


async def main():
    with tempfile.TemporaryDirectory(prefix="pwm-real-ha-store-") as directory:
        hass = HomeAssistant(directory)
        store = module.create_store(hass, "pwm_probe", 1)
        await module.durable_save(store, {"revision": 1})
        path = Path(directory) / ".storage/pwm_probe"
        assert json.loads(path.read_text())["data"] == {"revision": 1}
        original_bytes = path.read_bytes()

        async def rejected(payload):
            try:
                await module.durable_save(store, payload)
            except RuntimeError as error:
                assert "acknowledged" in str(error)
            else:
                raise AssertionError("A failed HA Store write must not acknowledge a safety barrier")

        await rejected({"not_serializable": object()})
        assert path.read_bytes() == original_bytes
        original_writer = storage.write_utf8_file_atomic

        def disk_full(*args, **kwargs):
            raise WriteError("injected ENOSPC") from OSError(errno.ENOSPC, "No space left on device")

        storage.write_utf8_file_atomic = disk_full
        try:
            await rejected({"revision": 2})
        finally:
            storage.write_utf8_file_atomic = original_writer
        assert path.read_bytes() == original_bytes

        # A genuine OS permission failure, rather than a mocked Store exception.
        if os.name == "posix" and os.geteuid() != 0:
            parent = path.parent
            parent.chmod(0o500)
            try:
                await rejected({"revision": 3})
            finally:
                parent.chmod(0o700)
            assert path.read_bytes() == original_bytes

        entered, release = threading.Event(), threading.Event()

        def suspended_writer(*args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test writer timed out")
            return original_writer(*args, **kwargs)

        storage.write_utf8_file_atomic = suspended_writer
        try:
            task = asyncio.create_task(module.durable_save(store, {"revision": 4}))
            await asyncio.wait_for(asyncio.to_thread(entered.wait), 5)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done()
            release.set()
            try:
                await task
            except asyncio.CancelledError:
                pass
            assert json.loads(path.read_text())["data"] == {"revision": 4}
        finally:
            release.set()
            storage.write_utf8_file_atomic = original_writer
        await module.durable_save(store, {"revision": 5})
        assert json.loads(path.read_text())["data"] == {"revision": 5}
        hass.state = CoreState.stopping
        await rejected({"revision": 6})  # HA defers this; no ON may rely on it.
        assert json.loads(path.read_text())["data"] == {"revision": 5}
        print(
            json.dumps(
                {
                    "real_ha_store": "PASS",
                    "atomic_replacement": "PASS",
                    "serialization_failure": "PASS",
                    "enospc_fault_injection": "PASS",
                    "cancelled_executor_write_drained": "PASS",
                    "shutdown_deferred_write_rejected": "PASS",
                    "stored_bytes": path.stat().st_size,
                }
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
