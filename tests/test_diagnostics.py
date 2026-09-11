"""Tests for MindClip diagnostics privacy."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mindclip import MindClipRuntimeData
from custom_components.mindclip.api import RecordingSummary
from custom_components.mindclip.const import (
    CONF_API_SECRET,
    CONF_API_TOKEN,
    CONF_DEVICE_ID,
    DOMAIN,
)
from custom_components.mindclip.coordinator import MindClipCoordinator, MindClipData
from custom_components.mindclip.diagnostics import async_get_config_entry_diagnostics
from custom_components.mindclip.todo_store import PendingTodo


async def test_diagnostics_exclude_credentials_identifiers_and_content(hass) -> None:
    """Diagnostics contain health metadata but no sensitive values."""
    private_values = (
        "private-token",
        "private-secret",
        "private-device-id",
        "private-recording-id",
        "private recording title",
        "private summary body",
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Private device title",
        data={
            CONF_API_TOKEN: private_values[0],
            CONF_API_SECRET: private_values[1],
            CONF_DEVICE_ID: private_values[2],
        },
        unique_id=private_values[2],
    )
    api = MagicMock()
    coordinator = MindClipCoordinator(hass, entry, api, private_values[2])
    coordinator.async_set_updated_data(
        MindClipData(
            open_todo_count=2,
            pending_todos=(PendingTodo("a" * 64, private_values[4], 1000, 2000),),
            recording_count=3,
            latest_recording_title=private_values[4],
            latest_summary=RecordingSummary(private_values[3], private_values[5]),
            charging=False,
            todos_truncated=False,
            recordings_truncated=True,
            device_status_healthy=True,
            recordings_healthy=True,
            summary_healthy=True,
            updated_at=datetime(2026, 9, 11, tzinfo=UTC),
        )
    )
    entry.runtime_data = MindClipRuntimeData(api=api, coordinator=coordinator)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    serialized = repr(diagnostics)

    assert diagnostics["health"]["status"] == "degraded"
    assert diagnostics["data"]["open_todo_count"] == 2
    assert diagnostics["data"]["pending_todo_count"] == 1
    assert diagnostics["data"]["recordings_truncated"] is True
    for private_value in private_values:
        assert private_value not in serialized
