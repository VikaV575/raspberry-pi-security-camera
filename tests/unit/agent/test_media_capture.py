from unittest.mock import AsyncMock, patch

import pytest

from pi_agent.media import capture_snapshot


@pytest.mark.asyncio
async def test_snapshot_fails_if_camera_created_no_file(tmp_path):
    path = tmp_path / "missing.jpg"
    with (
        patch("pi_agent.media.make_snapshot_path", return_value=path),
        patch("pi_agent.media.run_cmd", new_callable=AsyncMock) as mock_run,
    ):
        with pytest.raises(RuntimeError, match="not created"):
            await capture_snapshot()

    mock_run.assert_awaited_once()


@pytest.mark.asyncio
async def test_snapshot_fails_if_output_is_empty(tmp_path):
    path = tmp_path / "empty.jpg"
    path.write_bytes(b"")

    with (
        patch("pi_agent.media.make_snapshot_path", return_value=path),
        patch("pi_agent.media.run_cmd", new_callable=AsyncMock),
    ):
        with pytest.raises(RuntimeError, match="empty"):
            await capture_snapshot()


@pytest.mark.asyncio
async def test_snapshot_succeeds_with_nonempty_file(tmp_path):
    path = tmp_path / "photo.jpg"
    path.write_bytes(b"jpeg-payload")

    with (
        patch("pi_agent.media.make_snapshot_path", return_value=path),
        patch("pi_agent.media.run_cmd", new_callable=AsyncMock),
    ):
        assert await capture_snapshot() == path
