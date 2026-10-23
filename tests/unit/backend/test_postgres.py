"""Offline unit tests for PostgreSQL write helpers (no live server required)."""
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from backend.app.core import postgres


def test_insert_camera_uses_parameterized_sql():
    connection = MagicMock()
    with patch("backend.app.core.postgres.connect") as connect:
        connect.return_value.__enter__.return_value = connection
        postgres.insert_camera({"id": "camera-1", "name": "Porch"})

    query, params = connection.execute.call_args.args
    assert "INSERT INTO cameras" in query
    assert "ON CONFLICT" in query
    assert params == ("camera-1", "Porch", None)


def test_insert_media_keeps_public_uuid_and_storage_key():
    connection = MagicMock()
    with patch("backend.app.core.postgres.connect") as connect:
        connect.return_value.__enter__.return_value = connection
        postgres.insert_media("camera-1", {
            "id": "media-uuid",
            "filename": "photo.jpg",
            "media_type": "image",
            "content_type": "image/jpeg",
            "size_bytes": 4,
            "uploaded_at": "2026-10-23T12:00:00+00:00",
        })

    query, params = connection.execute.call_args.args
    assert "INSERT INTO media" in query
    assert params[:6] == (
        "media-uuid", "camera-1", "image", "photo.jpg", "image/jpeg", 4
    )


def test_import_json_only_once_and_keep_original_file(tmp_path):
    path = tmp_path / "devices_db.json"
    original = {
        "existing-camera": {
            "name": "Kitchen",
            "media": [{
                "id": "old-photo-id",
                "filename": "old.jpg",
                "media_type": "image",
                "content_type": "image/jpeg",
                "size_bytes": 10,
            }],
            "commands": [],
        }
    }
    path.write_text(json.dumps(original), encoding="utf-8")

    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None

    postgres.import_legacy_once(conn, str(path))
    statements = [c.args[0] for c in conn.execute.call_args_list]
    assert any("INSERT INTO cameras" in statement for statement in statements)
    assert any("INSERT INTO media" in statement for statement in statements)
    assert any("INSERT INTO legacy_imports" in statement for statement in statements)
    assert json.loads(path.read_text(encoding="utf-8")) == original

    conn.reset_mock()
    conn.execute.return_value.fetchone.return_value = {"?column?": 1}
    postgres.import_legacy_once(conn, str(path))
    assert len(conn.execute.call_args_list) == 1


def test_delete_camera_deletes_children_before_parent():
    conn = MagicMock()
    with patch("backend.app.core.postgres.connect") as connect:
        connect.return_value.__enter__.return_value = conn
        postgres.delete_camera("camera-1")

    sql = [c.args[0] for c in conn.execute.call_args_list]
    assert "DELETE FROM media" in sql[0]
    assert "DELETE FROM commands" in sql[1]
    assert "DELETE FROM cameras" in sql[2]


def test_load_devices_reconstructs_existing_api_shape():
    conn = MagicMock()
    now = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
    conn.execute.side_effect = [
        [{"id": "camera-1", "name": "Kitchen", "last_seen": now}],
        [{
            "public_id": "media-1", "camera_id": "camera-1",
            "media_type": "image", "storage_key": "photo.jpg",
            "content_type": "image/jpeg", "size_bytes": 5, "created_at": now,
        }],
        [{"camera_id": "camera-1", "record": {
            "id": "command-1", "type": "snapshot", "status": "completed"
        }}],
    ]
    with (
        patch("backend.app.core.postgres.connect") as connect,
        patch("backend.app.core.postgres.import_legacy_once"),
    ):
        connect.return_value.__enter__.return_value = conn
        devices = postgres.load_devices("unused.json")

    camera = devices["camera-1"]
    assert camera["name"] == "Kitchen"
    assert camera["last_seen"] == now.isoformat()
    assert camera["media"][0]["id"] == "media-1"
    assert camera["media"][0]["url"] == "/uploads/photo.jpg"
    assert camera["commands"][0]["status"] == "completed"
