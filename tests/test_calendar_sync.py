"""Tests for optional MindClip Calendar synchronization."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.calendar import CREATE_EVENT_SERVICE, SERVICE_GET_EVENTS
from homeassistant.components.calendar.const import (
    DOMAIN as CALENDAR_DOMAIN,
)
from homeassistant.components.calendar.const import (
    EVENT_DESCRIPTION,
    EVENT_END_DATETIME,
    EVENT_START_DATETIME,
    EVENT_SUMMARY,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.exceptions import HomeAssistantError

from custom_components.mindclip.calendar_sync import MindClipCalendarSync
from custom_components.mindclip.const import (
    CONF_CALENDAR_ENTITY,
    CONF_EVENT_DURATION_MINUTES,
)
from custom_components.mindclip.todo_store import PendingTodo

CALENDAR_ENTITY = "calendar.mindclip"
TODO_UID = "a" * 64


def _coordinator(*items: PendingTodo) -> MagicMock:
    """Return a coordinator with pending items."""
    coordinator = MagicMock()
    coordinator.data = SimpleNamespace(pending_todos=items)
    coordinator.async_acknowledge_todo = AsyncMock()
    return coordinator


async def test_sync_creates_event_and_acknowledges(hass) -> None:
    """A reminder creates one event before local acknowledgement."""
    item = PendingTodo(TODO_UID, "Call office", 1000, 2000)
    coordinator = _coordinator(item)
    service_call = AsyncMock(side_effect=[{CALENDAR_ENTITY: {"events": []}}, None])
    sync = MindClipCalendarSync(
        hass,
        {
            CONF_CALENDAR_ENTITY: CALENDAR_ENTITY,
            CONF_EVENT_DURATION_MINUTES: 30,
        },
        coordinator,
    )

    with patch.object(type(hass.services), "async_call", service_call):
        await sync._async_sync()

    assert service_call.await_args_list[0].args[:2] == (
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
    )
    assert service_call.await_args_list[1].args[:2] == (
        CALENDAR_DOMAIN,
        CREATE_EVENT_SERVICE,
    )
    event = service_call.await_args_list[1].args[2]
    assert event[ATTR_ENTITY_ID] == CALENDAR_ENTITY
    assert event[EVENT_SUMMARY] == "Call office"
    assert event[EVENT_START_DATETIME] == datetime.fromtimestamp(2, UTC)
    assert event[EVENT_END_DATETIME] == datetime.fromtimestamp(1802, UTC)
    assert TODO_UID in event[EVENT_DESCRIPTION]
    coordinator.async_acknowledge_todo.assert_awaited_once_with(TODO_UID)


async def test_sync_acknowledges_existing_event_without_duplicate(hass) -> None:
    """An existing UID is acknowledged without creating another event."""
    item = PendingTodo(TODO_UID, "Call office", 1000, 2000)
    coordinator = _coordinator(item)
    service_call = AsyncMock(
        return_value={
            CALENDAR_ENTITY: {
                "events": [
                    {
                        "start": datetime.fromtimestamp(2, UTC).isoformat(),
                        "summary": "Call office",
                        "description": f"MindClip To-Do ID: {TODO_UID}",
                    }
                ]
            }
        }
    )
    sync = MindClipCalendarSync(
        hass, {CONF_CALENDAR_ENTITY: CALENDAR_ENTITY}, coordinator
    )

    with patch.object(type(hass.services), "async_call", service_call):
        await sync._async_sync()

    service_call.assert_awaited_once()
    coordinator.async_acknowledge_todo.assert_awaited_once_with(TODO_UID)


async def test_sync_leaves_items_without_reminders_pending(hass) -> None:
    """Items without a reminder are left for manual acknowledgement."""
    coordinator = _coordinator(PendingTodo(TODO_UID, "No due date", 1000, None))
    service_call = AsyncMock()
    sync = MindClipCalendarSync(
        hass, {CONF_CALENDAR_ENTITY: CALENDAR_ENTITY}, coordinator
    )

    with patch.object(type(hass.services), "async_call", service_call):
        await sync._async_sync()

    service_call.assert_not_awaited()
    coordinator.async_acknowledge_todo.assert_not_awaited()


async def test_sync_failure_leaves_item_pending(hass) -> None:
    """A Calendar failure leaves the item pending for a later retry."""
    coordinator = _coordinator(PendingTodo(TODO_UID, "Call office", 1000, 2000))
    service_call = AsyncMock(side_effect=HomeAssistantError("calendar unavailable"))
    sync = MindClipCalendarSync(
        hass, {CONF_CALENDAR_ENTITY: CALENDAR_ENTITY}, coordinator
    )

    with patch.object(type(hass.services), "async_call", service_call):
        await sync._async_sync()

    coordinator.async_acknowledge_todo.assert_not_awaited()


async def test_sync_skips_invalid_timestamp_and_continues(hass) -> None:
    """An invalid reminder stays pending without blocking later valid items."""
    invalid_uid = "b" * 64
    coordinator = _coordinator(
        PendingTodo(invalid_uid, "Invalid reminder", 1000, 10**30),
        PendingTodo(TODO_UID, "Call office", 1000, 2000),
    )
    service_call = AsyncMock(side_effect=[{CALENDAR_ENTITY: {"events": []}}, None])
    sync = MindClipCalendarSync(
        hass, {CONF_CALENDAR_ENTITY: CALENDAR_ENTITY}, coordinator
    )

    with patch.object(type(hass.services), "async_call", service_call):
        await sync._async_sync()

    assert service_call.await_count == 2
    coordinator.async_acknowledge_todo.assert_awaited_once_with(TODO_UID)
