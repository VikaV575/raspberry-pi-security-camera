"""PostgreSQL persistence for registered cameras and their activity.

The in-memory devices dictionary remains a live WebSocket/UI cache. PostgreSQL
is the durable source loaded on startup. The legacy JSON file is imported only
once, non-destructively, for existing installations.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .activity import MAX_COMMAND_ITEMS, MAX_MEDIA_ITEMS


def enabled() -> bool:
    return bool(os.getenv("DB_HOST"))


def connect():
    return psycopg.connect(
        host=os.environ["DB_HOST"],
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "camera_db"),
        user=os.getenv("DB_USER", "camera_app"),
        password=os.environ["DB_PASSWORD"],
        connect_timeout=5,
        row_factory=dict_row,
    )


def _insert_camera(conn, device: dict) -> None:
    conn.execute(
        """INSERT INTO cameras (id, name, last_seen)
           VALUES (%s, %s, %s)
           ON CONFLICT (id) DO NOTHING""",
        (device["id"], device.get("name"), device.get("last_seen")),
    )


def _insert_media(conn, camera_id: str, item: dict) -> None:
    if item.get("media_type") not in ("image", "video"):
        return
    conn.execute(
        """INSERT INTO media
           (public_id, camera_id, media_type, storage_key, content_type,
            size_bytes, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT DO NOTHING""",
        (
            item["id"], camera_id, item["media_type"], item["filename"],
            item.get("content_type"), item.get("size_bytes"),
            item.get("uploaded_at") or datetime.now(timezone.utc),
        ),
    )


def _upsert_command(conn, camera_id: str, record: dict) -> None:
    conn.execute(
        """INSERT INTO commands
           (id, camera_id, command_type, status, record, created_at, updated_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (id) DO UPDATE SET
               status = EXCLUDED.status,
               record = EXCLUDED.record,
               updated_at = EXCLUDED.updated_at""",
        (
            record["id"], camera_id, record.get("type", "unknown"),
            record.get("status", "unknown"), Jsonb(record),
            record.get("created_at") or datetime.now(timezone.utc),
            record.get("updated_at") or datetime.now(timezone.utc),
        ),
    )


def import_legacy_once(conn, json_path: str) -> None:
    """Import the old JSON data once, with a marker in the same transaction.

    Keep the original JSON and uploaded files untouched for recovery.
    """
    source = "devices_db.json-v1"
    exists = conn.execute(
        "SELECT 1 FROM legacy_imports WHERE source = %s", (source,)
    ).fetchone()
    if exists:
        return

    legacy = {}
    if Path(json_path).is_file():
        with open(json_path, encoding="utf-8") as f:
            legacy = json.load(f)
    for device_id, device in legacy.items():
        if not isinstance(device, dict):
            continue
        camera = {**device, "id": device_id}
        _insert_camera(conn, camera)
        for item in device.get("media", []):
            if isinstance(item, dict) and item.get("id") and item.get("filename"):
                _insert_media(conn, device_id, item)
        for record in device.get("commands", []):
            if isinstance(record, dict) and record.get("id"):
                _upsert_command(conn, device_id, record)

    conn.execute("INSERT INTO legacy_imports (source) VALUES (%s)", (source,))


def load_devices(json_path: str) -> dict:
    with connect() as conn:
        import_legacy_once(conn, json_path)
        result = {}
        for row in conn.execute("SELECT id, name, last_seen FROM cameras"):
            result[row["id"]] = {
                "id": row["id"],
                "name": row["name"],
                "last_seen": row["last_seen"].isoformat() if row["last_seen"] else None,
                "media": [],
                "commands": [],
            }

        for row in conn.execute(
            """SELECT public_id, camera_id, media_type, storage_key,
                      content_type, size_bytes, created_at
               FROM media
               WHERE public_id IS NOT NULL
               ORDER BY created_at DESC, id DESC"""
        ):
            camera = result.get(row["camera_id"])
            if camera is None or len(camera["media"]) >= MAX_MEDIA_ITEMS:
                continue
            filename = row["storage_key"]
            camera["media"].append({
                "id": row["public_id"],
                "filename": filename,
                "url": f"/uploads/{quote(filename)}",
                "media_type": row["media_type"],
                "content_type": row["content_type"],
                "size_bytes": row["size_bytes"],
                "uploaded_at": row["created_at"].isoformat(),
            })

        for row in conn.execute(
            """SELECT camera_id, record FROM commands
               ORDER BY created_at DESC, id DESC"""
        ):
            camera = result.get(row["camera_id"])
            if camera is not None and len(camera["commands"]) < MAX_COMMAND_ITEMS:
                camera["commands"].append(row["record"])

    return result


def insert_camera(device: dict) -> None:
    with connect() as conn:
        _insert_camera(conn, device)


def delete_camera(camera_id: str) -> None:
    with connect() as conn:
        # The original media FK did not include ON DELETE CASCADE.
        conn.execute("DELETE FROM media WHERE camera_id = %s", (camera_id,))
        conn.execute("DELETE FROM commands WHERE camera_id = %s", (camera_id,))
        conn.execute("DELETE FROM cameras WHERE id = %s", (camera_id,))


def set_last_seen(camera_id: str, value: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE cameras SET last_seen = %s WHERE id = %s",
            (value, camera_id),
        )


def insert_media(camera_id: str, item: dict) -> None:
    with connect() as conn:
        _insert_media(conn, camera_id, item)


def delete_media(camera_id: str, media_id: str) -> None:
    with connect() as conn:
        conn.execute(
            "DELETE FROM media WHERE camera_id = %s AND public_id = %s",
            (camera_id, media_id),
        )


def insert_or_update_command(camera_id: str, record: dict) -> None:
    with connect() as conn:
        _upsert_command(conn, camera_id, record)
