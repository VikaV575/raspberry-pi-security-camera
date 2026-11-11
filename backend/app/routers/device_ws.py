import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..core.activity import update_command_status
from ..core.state import devices
from ..core.storage import save_devices
from ..services.device_ws_manager import ws_manager

router = APIRouter(prefix="/devices", tags=["device-ws"])


@router.websocket("/{device_id}/ws")
async def device_ws(device_id: str, websocket: WebSocket):
    if device_id not in devices:
        await websocket.close(code=1008)
        return

    await ws_manager.connect(device_id, websocket)

    devices[device_id]["last_seen"] = datetime.now(timezone.utc).isoformat()
    save_devices()

    q = await ws_manager.get_queue(device_id)

    async def sender_loop():
        while True:
            print("waiting for command...")
            cmd = await q.get()
            print("got command from queue:", cmd)
            payload = {"type": "command", "command": cmd}
            print("about to send:", payload)

            try:
                await websocket.send_json(payload)
                print("send_json finished")
            except Exception as e:
                print("send_json error:", repr(e))
                raise

    async def receiver_loop():
        while True:
            msg = await websocket.receive_json()
            print("[ws from device]", device_id, msg)

            device = devices[device_id]
            device["last_seen"] = datetime.now(timezone.utc).isoformat()

            if msg.get("type") == "status":
                command = msg.get("command") or {}
                command_id = command.get("id")
                if command_id:
                    update_command_status(
                        device,
                        command_id=command_id,
                        agent_status=str(msg.get("status") or "unknown"),
                        error=msg.get("error"),
                        meta=msg.get("meta"),
                    )

            save_devices()

    # Stop both loops as soon as either side closes. Otherwise an abandoned
    # sender may keep reading the shared queue and steal future commands.
    sender = asyncio.create_task(sender_loop())
    receiver = asyncio.create_task(receiver_loop())
    try:
        done, _ = await asyncio.wait(
            {sender, receiver}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in done:
            task.result()
    except WebSocketDisconnect:
        print("WebSocketDisconnect")
    except Exception as e:
        print("WS route exception:", repr(e))
    finally:
        for task in (sender, receiver):
            task.cancel()
        await asyncio.gather(sender, receiver, return_exceptions=True)
        await ws_manager.disconnect(device_id, websocket)
        try:
            await websocket.close()
        except Exception:
            pass
