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
from homeassistant.util.yaml import load_yaml
from homeassistant.components.template import CONFIG_SCHEMA

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
        permission_result = "not_run_root_or_nonposix"
        if os.name == "posix" and os.geteuid() != 0:
            parent = path.parent
            parent.chmod(0o500)
            try:
                await rejected({"revision": 3})
            finally:
                parent.chmod(0o700)
            assert path.read_bytes() == original_bytes
            permission_result = "PASS"

        entered, release = threading.Event(), threading.Event()

        def suspended_writer(*args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test writer timed out")
            return original_writer(*args, **kwargs)

        storage.write_utf8_file_atomic = suspended_writer
        try:
            # A queued delayed callback can consume the next explicit payload.
            # An OLDER successful write must not acknowledge that payload if
            # serialization of the newer payload subsequently fails.
            older = asyncio.create_task(store.async_save({"revision": 10}))
            await asyncio.wait_for(asyncio.to_thread(entered.wait), 5)
            delayed = asyncio.create_task(store._async_handle_write_data())
            await asyncio.sleep(0)
            bad = asyncio.create_task(store.async_save({"bad": object()}))
            await asyncio.sleep(0)
            release.set()
            await older
            await delayed
            try:
                await bad
            except RuntimeError:
                pass
            else:
                raise AssertionError("An old write cannot acknowledge a newer failed payload")
            assert json.loads(path.read_text())["data"] == {"revision": 10}
            entered.clear()
            release.clear()
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
        CONFIG_SCHEMA(load_yaml(str(Path(__file__).parents[1] / "examples/pwm-hydraulic-sensors.yaml")))
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
                    "real_permission_failure": permission_result,
                    "exact_payload_acknowledgement": "PASS",
                    "template_yaml_schema": "PASS",
                    "stored_bytes": path.stat().st_size,
                }
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
