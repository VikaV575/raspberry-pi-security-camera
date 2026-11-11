from unittest.mock import AsyncMock

import pytest

from backend.app.services.device_ws_manager import DeviceWSManager


@pytest.mark.asyncio
async def test_stale_disconnect_keeps_new_connection_online():
    manager = DeviceWSManager()
    old_ws = AsyncMock()
    new_ws = AsyncMock()

    await manager.connect("camera-1", old_ws)
    await manager.connect("camera-1", new_ws)

    # Old connection finishes only after the replacement was registered.
    await manager.disconnect("camera-1", old_ws)

    assert await manager.is_connected("camera-1")
    assert manager.ws_by_device["camera-1"] is new_ws

    await manager.disconnect("camera-1", new_ws)
    assert not await manager.is_connected("camera-1")


@pytest.mark.asyncio
async def test_explicit_device_removal_disconnects_regardless_of_socket():
    manager = DeviceWSManager()
    ws = AsyncMock()
    await manager.connect("camera-1", ws)

    await manager.disconnect("camera-1")

    assert not await manager.is_connected("camera-1")
