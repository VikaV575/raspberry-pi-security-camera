from fastapi import APIRouter, UploadFile, File, HTTPException
import os
import uuid
from datetime import datetime
from pathlib import Path

from ..core.activity import (
    add_command,
    add_media,
    ensure_activity,
    pop_media,
    prune_missing_media,
    trim_command_history,
    update_command_status,
)
from ..core.config import UPLOAD_DIR, ISRAEL_TZ
from ..core.state import devices
from ..core.storage import (
    save_devices,
    persist_camera,
    remove_camera,
    persist_media,
    remove_media,
    persist_command,
)
from ..schemas.device import DeviceCreate
from ..schemas.command import CommandCreate
from ..services.device_ws_manager import ws_manager

router = APIRouter(prefix="/devices", tags=["devices"])


def build_live_info(device_id: str) -> dict:
    stream_key = device_id
    return {
        "stream_key": stream_key,
        "webrtc_url": f"http://YOUR_MEDIAMTX_HOST:8889/live/{stream_key}",
        "hls_url": f"http://YOUR_MEDIAMTX_HOST:8888/live/{stream_key}/index.m3u8",
    }


def safe_filename_part(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in "-_" else "_" for char in value)
    return cleaned.strip("_") or "camera"


def media_path(filename: str) -> Path:
    upload_root = Path(UPLOAD_DIR).resolve()
    path = (upload_root / filename).resolve()
    if path.parent != upload_root:
        raise HTTPException(status_code=400, detail="Invalid media path")
    return path


async def queue_device_command(device_id: str, command: dict) -> dict:
    if device_id not in devices:
        raise HTTPException(status_code=404, detail="Device not found")

    device = devices[device_id]
    payload, record = add_command(device, command)
    persist_command(device_id, record)
    save_devices()

    try:
        await ws_manager.push_command(device_id, payload)
    except Exception as error:
        detail = getattr(error, "detail", str(error))
        update_command_status(device, record["id"], "error", error=str(detail))
        persist_command(device_id, record)
        save_devices()
        raise

    return record


@router.post("")
def create_device(device: DeviceCreate):
    device_id = str(uuid.uuid4())
    new_device = {
        "id": device_id,
        "name": device.name,
        "last_seen": None,
        "media": [],
        "commands": [],
    }
    persist_camera(new_device)
    devices[device_id] = new_device
    save_devices()
    return new_device


@router.delete("/{device_id}/remove")
async def remove_device(device_id: str):
    if device_id not in devices:
        raise HTTPException(status_code=404, detail="Device not found")

    remove_camera(device_id)
    devices.pop(device_id)
    await ws_manager.disconnect(device_id)
    save_devices()
    return {"ok": True, "message": f"Device {device_id} removed"}


@router.post("/{device_id}/upload")
async def upload_file(device_id: str, file: UploadFile = File(...)):
    if device_id not in devices:
        raise HTTPException(status_code=404, detail="Device not found")

    device = devices[device_id]
    name = safe_filename_part(device["name"])
    ts = datetime.now(ISRAEL_TZ).strftime("%Y%m%d_%H%M%S_%f")
    original_name = os.path.basename(file.filename or "file.bin")
    filename = f"{name}_{ts}_{original_name}"
    path = os.path.join(UPLOAD_DIR, filename)
    contents = await file.read()

    with open(path, "wb") as output:
        output.write(contents)

    media = add_media(
        device,
        filename=filename,
        content_type=file.content_type,
        size_bytes=len(contents),
    )
    if media["media_type"] not in ("image", "video"):
        pop_media(device, media["id"])
        os.remove(path)
        raise HTTPException(status_code=415, detail="Only image and video uploads are supported")

    try:
        persist_media(device_id, media)
    except Exception:
        pop_media(device, media["id"])
        os.remove(path)
        raise

    save_devices()

    return {
        "ok": True,
        "saved_to": path,
        "url": media["url"],
        "media": media,
    }


@router.delete("/{device_id}/media/{media_id}")
async def delete_media(device_id: str, media_id: str):
    if device_id not in devices:
        raise HTTPException(status_code=404, detail="Device not found")

    device = devices[device_id]
    item = next((media for media in device.get("media", []) if media.get("id") == media_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Media not found")

    path = media_path(item.get("filename", ""))
    remove_media(device_id, media_id)
    pop_media(device, media_id)
    file_deleted = False
    try:
        path.unlink()
        file_deleted = True
    except FileNotFoundError:
        pass

    save_devices()
    return {
        "ok": True,
        "media_id": media_id,
        "file_deleted": file_deleted,
    }


@router.get("")
async def list_devices():
    result = []
    activity_changed = False

    for device in devices.values():
        ensure_activity(device)
        if trim_command_history(device):
            activity_changed = True
        for missing in prune_missing_media(device, UPLOAD_DIR):
            remove_media(device["id"], missing["id"])
            activity_changed = True

        device_copy = device.copy()
        device_copy["media"] = list(device["media"])
        device_copy["commands"] = list(device["commands"])
        device_copy["online"] = await ws_manager.is_connected(device["id"])
        result.append(device_copy)

    if activity_changed:
        save_devices()

    return result


@router.post("/{device_id}/command")
async def send_command(device_id: str, command: CommandCreate):
    record = await queue_device_command(
        device_id,
        command.model_dump(exclude_none=True),
    )

    return {
        "ok": True,
        "message": "Command queued for online device",
        "command": record,
    }


@router.get("/{device_id}/live")
async def get_live_info(device_id: str):
    if device_id not in devices:
        raise HTTPException(status_code=404, detail="Device not found")

    return {
        "ok": True,
        "device_id": device_id,
        "live": build_live_info(device_id),
    }


@router.post("/{device_id}/live/start")
async def start_live(device_id: str):
    record = await queue_device_command(
        device_id,
        {
            "type": "start_live",
            "stream_key": device_id,
        },
    )

    return {
        "ok": True,
        "message": "Live start command sent",
        "device_id": device_id,
        "command": record,
        "live": build_live_info(device_id),
    }


@router.post("/{device_id}/live/stop")
async def stop_live(device_id: str):
    record = await queue_device_command(
        device_id,
        {
            "type": "stop_live",
        },
    )

    return {
        "ok": True,
        "message": "Live stop command sent",
        "device_id": device_id,
        "command": record,
    }
