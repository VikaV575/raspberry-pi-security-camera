"""Temporary compatibility layer: JSON for standalone tests, PostgreSQL in Docker.

The WebSocket manager still uses the in-memory devices cache. Database writes
are targeted to individual records, not full snapshots on each heartbeat.
"""
import json
import os

from . import postgres
from .config import DB_FILE
from .state import devices


def load_devices() -> dict:
    if postgres.enabled():
        return postgres.load_devices(DB_FILE)

    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_devices() -> None:
    # Historical JSON persistence is used outside PostgreSQL mode (unit tests).
    # In PostgreSQL mode, callers must use the targeted methods below.
    if postgres.enabled():
        return

    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(devices, f, indent=4)


def persist_camera(device: dict) -> None:
    if postgres.enabled():
        postgres.insert_camera(device)


def remove_camera(camera_id: str) -> None:
    if postgres.enabled():
        postgres.delete_camera(camera_id)


def persist_media(camera_id: str, media: dict) -> None:
    if postgres.enabled():
        postgres.insert_media(camera_id, media)


def remove_media(camera_id: str, media_id: str) -> None:
    if postgres.enabled():
        postgres.delete_media(camera_id, media_id)


def persist_command(camera_id: str, record: dict | None) -> None:
    if postgres.enabled() and record:
        postgres.insert_or_update_command(camera_id, record)


def persist_last_seen(camera_id: str, value: str) -> None:
    if postgres.enabled():
        postgres.set_last_seen(camera_id, value)
