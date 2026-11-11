from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.state import devices


client = TestClient(app)


def test_send_record_command_to_existing_device():
    device_id = "camera-123"

    devices[device_id] = {
        "id": device_id,
        "name": "Living Room Camera",
        "last_seen": None,
    }

    with (
        patch("backend.app.core.activity.uuid.uuid4", return_value="command-fixed-id"),
        patch("backend.app.routers.devices.save_devices"),
        patch(
            "backend.app.routers.devices.ws_manager.push_command",
            new_callable=AsyncMock,
        ) as mock_push_command,
    ):
        response = client.post(
            f"/devices/{device_id}/command",
            json={
                "type": "record",
                "seconds": 10,
            },
        )

    assert response.status_code == 200

    response_data = response.json()
    assert response_data["ok"] is True
    assert response_data["message"] == "Command queued for online device"

    command = response_data["command"]
    assert command["id"] == "command-fixed-id"
    assert command["type"] == "record"
    assert command["seconds"] == 10
    assert command["status"] == "queued"
    assert command["error"] is None
    assert command["created_at"]
    assert command["updated_at"] == command["created_at"]
    assert devices[device_id]["commands"][0] == command

    mock_push_command.assert_awaited_once_with(
        device_id,
        {
            "type": "record",
            "seconds": 10,
            "id": "command-fixed-id",
        },
    )

    devices.pop(device_id, None)


def test_send_command_to_missing_device_returns_404():
    missing_device_id = "does-not-exist"

    devices.pop(missing_device_id, None)

    with patch(
        "backend.app.routers.devices.ws_manager.push_command",
        new_callable=AsyncMock,
    ) as mock_push_command:
        response = client.post(
            f"/devices/{missing_device_id}/command",
            json={
                "type": "record",
                "seconds": 10,
            },
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Device not found"}
    mock_push_command.assert_not_awaited()


def test_command_without_type_returns_422():
    device_id = "camera-123"

    devices[device_id] = {
        "id": device_id,
        "name": "Living Room Camera",
        "last_seen": None,
    }

    with patch(
        "backend.app.routers.devices.ws_manager.push_command",
        new_callable=AsyncMock,
    ) as mock_push_command:
        response = client.post(
            f"/devices/{device_id}/command",
            json={"seconds": 10},
        )

    assert response.status_code == 422

    error_details = response.json()["detail"]
    assert error_details[0]["loc"] == ["body", "type"]
    assert error_details[0]["type"] == "missing"
    mock_push_command.assert_not_awaited()

    devices.pop(device_id, None)


def test_record_duration_out_of_range_is_rejected_before_dispatch():
    device_id = "camera-validate-seconds"
    devices[device_id] = {"id": device_id, "name": "Camera", "last_seen": None}

    with patch(
        "backend.app.routers.devices.ws_manager.push_command",
        new_callable=AsyncMock,
    ) as mock_push:
        for seconds in (-1, 0, 61):
            response = client.post(
                f"/devices/{device_id}/command",
                json={"type": "record", "seconds": seconds},
            )
            assert response.status_code == 422

    mock_push.assert_not_awaited()
    devices.pop(device_id, None)


def test_unsupported_command_type_is_rejected_by_api():
    device_id = "camera-validate-type"
    devices[device_id] = {"id": device_id, "name": "Camera", "last_seen": None}

    with patch(
        "backend.app.routers.devices.ws_manager.push_command",
        new_callable=AsyncMock,
    ) as mock_push:
        response = client.post(
            f"/devices/{device_id}/command",
            json={"type": "factory_reset"},
        )

    assert response.status_code == 422
    mock_push.assert_not_awaited()
    devices.pop(device_id, None)
