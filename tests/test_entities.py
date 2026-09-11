"""Tests for MindClip entities."""

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.todo import TodoItemStatus
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mindclip import MindClipRuntimeData
from custom_components.mindclip.api import RecordingSummary
from custom_components.mindclip.binary_sensor import MindClipChargingSensor
from custom_components.mindclip.const import (
    CONF_API_SECRET,
    CONF_API_TOKEN,
    CONF_DEVICE_ID,
    DOMAIN,
)
from custom_components.mindclip.coordinator import MindClipCoordinator, MindClipData
from custom_components.mindclip.sensor import (
    SENSOR_DESCRIPTIONS,
    MindClipSensor,
    MindClipSummarySensor,
)
from custom_components.mindclip.todo import MindClipTodoListEntity
from custom_components.mindclip.todo_store import PendingTodo

DEVICE_ID = "MINDCLIP-TEST-001"


def _entry_with_data(hass) -> MockConfigEntry:
    """Return an entry with initialized coordinator data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="MindClip ST-001",
        data={
            CONF_API_TOKEN: "private-token",
            CONF_API_SECRET: "private-secret",
            CONF_DEVICE_ID: DEVICE_ID,
        },
        unique_id=DEVICE_ID,
    )
    api = MagicMock()
    coordinator = MindClipCoordinator(hass, entry, api, DEVICE_ID)
    coordinator.async_set_updated_data(
        MindClipData(
            open_todo_count=4,
            pending_todos=(PendingTodo("a" * 64, "Call the office", 1000, 2000),),
            recording_count=7,
            latest_recording_title="Synthetic meeting",
            latest_summary=RecordingSummary("recording-one", "Short summary"),
            charging=True,
            todos_truncated=False,
            recordings_truncated=False,
            device_status_healthy=True,
            recordings_healthy=True,
            summary_healthy=True,
            updated_at=datetime(2026, 9, 11, tzinfo=UTC),
        )
    )
    entry.runtime_data = MindClipRuntimeData(api=api, coordinator=coordinator)
    return entry


def test_sensor_values_and_device_registry_metadata(hass) -> None:
    """Sensors expose only requested values under one device."""
    entry = _entry_with_data(hass)
    sensors = {
        description.key: MindClipSensor(entry, description)
        for description in SENSOR_DESCRIPTIONS
    }

    assert sensors["open_todo_count"].native_value == 4
    assert sensors["recording_count"].native_value == 7
    assert sensors["latest_recording_title"].native_value == "Synthetic meeting"
    assert sensors["open_todo_count"].device_info["identifiers"] == {
        (DOMAIN, DEVICE_ID)
    }
    assert sensors["open_todo_count"].device_info["manufacturer"] == "SwitchBot"
    assert sensors["open_todo_count"].device_info["model"] == "AI MindClip"


def test_summary_and_charging_entities_are_privacy_limited(hass) -> None:
    """Summary and charging entities expose only their approved fields."""
    entry = _entry_with_data(hass)
    summary = MindClipSummarySensor(entry)
    charging = MindClipChargingSensor(entry)

    assert summary.native_value == "Short summary"
    assert summary.extra_state_attributes == {"recording_id": "recording-one"}
    assert charging.is_on is True
    assert summary.available is True
    assert charging.available is True


async def test_pending_todo_list_acknowledges_completed_items(hass) -> None:
    """The native To-do entity exposes and locally acknowledges pending items."""
    entry = _entry_with_data(hass)
    entity = MindClipTodoListEntity(entry)
    entity.coordinator.async_acknowledge_todo = AsyncMock()

    item = entity.todo_items[0]
    assert item.uid == "a" * 64
    assert item.summary == "Call the office"
    assert item.status == TodoItemStatus.NEEDS_ACTION
    assert item.due == datetime.fromtimestamp(2, UTC)

    item.status = TodoItemStatus.COMPLETED
    await entity.async_update_todo_item(item)

    entity.coordinator.async_acknowledge_todo.assert_awaited_once_with("a" * 64)


def test_truncated_todo_count_is_unavailable(hass) -> None:
    """A bounded lower limit is not exposed as an exact available count."""
    entry = _entry_with_data(hass)
    entry.runtime_data.coordinator.async_set_updated_data(
        replace(entry.runtime_data.coordinator.data, todos_truncated=True)
    )
    description = next(
        item for item in SENSOR_DESCRIPTIONS if item.key == "open_todo_count"
    )

    assert MindClipSensor(entry, description).available is False
