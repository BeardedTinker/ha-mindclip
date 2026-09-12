"""Optional pending To-Do synchronization to Home Assistant calendars."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

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
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CALENDAR_ENTITY,
    CONF_EVENT_DURATION_MINUTES,
    DEFAULT_EVENT_DURATION_MINUTES,
)
from .coordinator import MindClipCoordinator
from .todo_store import PendingTodo

_LOGGER = logging.getLogger(__name__)


class MindClipCalendarSyncError(Exception):
    """Raised when Calendar returns an unexpected response."""


class MindClipCalendarSync:
    """Synchronize pending reminder To-Dos to one configured Calendar."""

    def __init__(
        self,
        hass: HomeAssistant,
        options: Mapping[str, Any],
        coordinator: MindClipCoordinator,
    ) -> None:
        """Initialize Calendar synchronization."""
        self._hass = hass
        self._options = options
        self._coordinator = coordinator
        self._remove_listener: CALLBACK_TYPE | None = None
        self._task: asyncio.Task[None] | None = None

    @callback
    def async_start(self) -> None:
        """Start listening for coordinator updates."""
        if not self._options.get(CONF_CALENDAR_ENTITY):
            return
        self._remove_listener = self._coordinator.async_add_listener(
            self._schedule_sync
        )
        self._schedule_sync()

    @callback
    def async_stop(self) -> None:
        """Stop listening and cancel an in-flight sync."""
        if self._remove_listener is not None:
            self._remove_listener()
            self._remove_listener = None
        if self._task is not None:
            self._task.cancel()
            self._task = None

    @callback
    def _schedule_sync(self) -> None:
        """Schedule at most one Calendar sync task."""
        if self._task is not None and not self._task.done():
            return
        self._task = self._hass.async_create_task(
            self._async_sync(), "MindClip Calendar sync"
        )

    async def _async_sync(self) -> None:
        """Create missing Calendar events and acknowledge delivered items."""
        calendar_entity = self._options.get(CONF_CALENDAR_ENTITY)
        if not isinstance(calendar_entity, str) or not calendar_entity:
            return
        duration = timedelta(
            minutes=int(
                self._options.get(
                    CONF_EVENT_DURATION_MINUTES, DEFAULT_EVENT_DURATION_MINUTES
                )
            )
        )

        for item in tuple(self._coordinator.data.pending_todos):
            if item.reminder_time is None:
                continue
            start = datetime.fromtimestamp(item.reminder_time / 1000, UTC)
            end = start + duration
            try:
                if not await self._async_event_exists(
                    calendar_entity, item, start, end
                ):
                    await self._hass.services.async_call(
                        CALENDAR_DOMAIN,
                        CREATE_EVENT_SERVICE,
                        {
                            ATTR_ENTITY_ID: calendar_entity,
                            EVENT_START_DATETIME: start,
                            EVENT_END_DATETIME: end,
                            EVENT_SUMMARY: item.title,
                            EVENT_DESCRIPTION: (
                                "Created automatically from SwitchBot AI MindClip.\n"
                                f"MindClip To-Do ID: {item.uid}"
                            ),
                        },
                        blocking=True,
                    )
                await self._coordinator.async_acknowledge_todo(item.uid)
            except (
                HomeAssistantError,
                MindClipCalendarSyncError,
                ValueError,
            ):
                _LOGGER.warning(
                    "Unable to synchronize a pending MindClip To-Do to Calendar"
                )
                return

    async def _async_event_exists(
        self,
        calendar_entity: str,
        item: PendingTodo,
        start: datetime,
        end: datetime,
    ) -> bool:
        """Return whether the destination already contains this event."""
        response = await self._hass.services.async_call(
            CALENDAR_DOMAIN,
            SERVICE_GET_EVENTS,
            {
                ATTR_ENTITY_ID: calendar_entity,
                EVENT_START_DATETIME: start,
                EVENT_END_DATETIME: end,
            },
            blocking=True,
            return_response=True,
        )
        events = _extract_events(response, calendar_entity)
        for event in events:
            description = event.get(EVENT_DESCRIPTION)
            if isinstance(description, str) and item.uid in description:
                return True
            summary = event.get(EVENT_SUMMARY)
            event_start = _parse_event_start(event.get("start"))
            if (
                summary == item.title
                and event_start is not None
                and int(event_start.timestamp()) == int(start.timestamp())
            ):
                return True
        return False


def _extract_events(response: object, calendar_entity: str) -> list[Mapping[str, Any]]:
    """Extract one calendar's event list from a service response."""
    if not isinstance(response, Mapping):
        raise MindClipCalendarSyncError
    result = response.get(calendar_entity, response)
    if not isinstance(result, Mapping) or not isinstance(result.get("events"), list):
        raise MindClipCalendarSyncError
    events = result["events"]
    if not all(isinstance(event, Mapping) for event in events):
        raise MindClipCalendarSyncError
    return events


def _parse_event_start(value: object) -> datetime | None:
    """Parse a Calendar service event start value."""
    if isinstance(value, Mapping):
        value = value.get("dateTime")
    if not isinstance(value, str):
        return None
    parsed = dt_util.parse_datetime(value)
    return parsed if parsed is not None and parsed.tzinfo is not None else None
