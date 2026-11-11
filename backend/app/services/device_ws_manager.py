import asyncio
from fastapi import HTTPException, WebSocket


class DeviceWSManager:
    def __init__(self):
        # device_id -> websocket
        self.ws_by_device: dict[str, WebSocket] = {}
        # device_id -> outgoing command queue
        self.queue_by_device: dict[str, asyncio.Queue] = {}
        self.lock = asyncio.Lock()

    async def connect(self, device_id: str, ws: WebSocket):
        await ws.accept()
        async with self.lock:
            self.ws_by_device[device_id] = ws
            self.queue_by_device.setdefault(device_id, asyncio.Queue())

    async def disconnect(self, device_id: str, ws: WebSocket | None = None):
        """An old connection must not unregister a newer one after reconnect."""
        async with self.lock:
            if ws is None or self.ws_by_device.get(device_id) is ws:
                self.ws_by_device.pop(device_id, None)

    async def is_connected(self, device_id: str) -> bool:
        async with self.lock:
            return device_id in self.ws_by_device

    async def push_command(self, device_id: str, cmd: dict):
        async with self.lock:
            if device_id not in self.ws_by_device:
                raise HTTPException(status_code=409, detail="Device is offline")
            q = self.queue_by_device.setdefault(device_id, asyncio.Queue())
            await q.put(cmd)

    async def get_queue(self, device_id: str) -> asyncio.Queue:
        async with self.lock:
            return self.queue_by_device.setdefault(device_id, asyncio.Queue())


ws_manager = DeviceWSManager()