"""Tests for the MindClip coordinator."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mindclip.api import (
    DeviceStatus,
    MindClipAuthError,
    MindClipCommunicationError,
    MindClipSchemaError,
    OpenTodoCount,
    Recording,
    RecordingCollection,
)
from custom_components.mindclip.const import (
    CONF_API_SECRET,
    CONF_API_TOKEN,
    CONF_DEVICE_ID,
    DOMAIN,
)
from custom_components.mindclip.coordinator import MindClipCoordinator

DEVICE_ID = "MINDCLIP-TEST-001"


def _entry() -> MockConfigEntry:
    """Return a synthetic config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_TOKEN: "token",
            CONF_API_SECRET: "secret",
            CONF_DEVICE_ID: DEVICE_ID,
        },
        unique_id=DEVICE_ID,
    )


async def test_optional_failures_preserve_todo_and_recording_data(hass) -> None:
    """Optional endpoint failures degrade only related values."""
    api = MagicMock()
    api.async_get_open_todo_count = AsyncMock(
        return_value=OpenTodoCount(count=3, truncated=False)
    )
    api.async_get_device_status = AsyncMock(
        side_effect=MindClipCommunicationError("unavailable")
    )
    api.async_get_recordings = AsyncMock(
        return_value=RecordingCollection(
            total=2,
            latest=Recording("recording-one", "Planning", 1000, 2),
            latest_transcribed=Recording("recording-one", "Planning", 1000, 2),
            truncated=False,
        )
    )
    api.async_get_summary = AsyncMock(
        side_effect=MindClipSchemaError("invalid summary")
    )
    coordinator = MindClipCoordinator(hass, _entry(), api, DEVICE_ID)

    data = await coordinator._async_update_data()

    assert data.open_todo_count == 3
    assert data.device_status_healthy is False
    assert data.charging is None
    assert data.recordings_healthy is True
    assert data.recording_count == 2
    assert data.latest_recording_title == "Planning"
    assert data.summary_healthy is False
    assert data.latest_summary is None
    assert data.degraded is True


async def test_auth_failure_from_optional_endpoint_starts_reauth(hass) -> None:
    """Authentication failure from any endpoint aborts the refresh."""
    api = MagicMock()
    api.async_get_open_todo_count = AsyncMock(
        return_value=OpenTodoCount(count=0, truncated=False)
    )
    api.async_get_device_status = AsyncMock(
        side_effect=MindClipAuthError("authentication failed")
    )
    coordinator = MindClipCoordinator(hass, _entry(), api, DEVICE_ID)

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_successful_refresh_collects_minimal_data(hass) -> None:
    """A successful refresh returns only entity-facing data."""
    api = MagicMock()
    api.async_get_open_todo_count = AsyncMock(
        return_value=OpenTodoCount(count=1, truncated=True)
    )
    api.async_get_device_status = AsyncMock(return_value=DeviceStatus(charging=True))
    api.async_get_recordings = AsyncMock(
        return_value=RecordingCollection(
            total=0,
            latest=None,
            latest_transcribed=None,
            truncated=False,
        )
    )
    coordinator = MindClipCoordinator(hass, _entry(), api, DEVICE_ID)

    data = await coordinator._async_update_data()

    assert data.open_todo_count == 1
    assert data.todos_truncated is True
    assert data.charging is True
    assert data.recording_count == 0
    assert data.summary_healthy is True
    api.async_get_summary.assert_not_awaited()


async def test_summary_uses_latest_transcribed_recording(hass) -> None:
    """A recording still being transcribed does not hide the latest summary."""
    api = MagicMock()
    api.async_get_open_todo_count = AsyncMock(
        return_value=OpenTodoCount(count=0, truncated=False)
    )
    api.async_get_device_status = AsyncMock(return_value=DeviceStatus(charging=False))
    api.async_get_recordings = AsyncMock(
        return_value=RecordingCollection(
            total=2,
            latest=Recording("recording-new", "New recording", 2000, 1),
            latest_transcribed=Recording("recording-ready", "Ready recording", 1000, 2),
            truncated=False,
        )
    )
    api.async_get_summary = AsyncMock()
    coordinator = MindClipCoordinator(hass, _entry(), api, DEVICE_ID)

    data = await coordinator._async_update_data()

    assert data.latest_recording_title == "New recording"
    api.async_get_summary.assert_awaited_once_with("recording-ready")
