"""Data coordinator for the MindClip integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    MindClipApi,
    MindClipApiError,
    MindClipAuthError,
    RecordingSummary,
)
from .const import UPDATE_INTERVAL
from .todo_store import MindClipTodoStore, PendingTodo

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MindClipData:
    """Privacy-minimized coordinator output."""

    open_todo_count: int
    pending_todos: tuple[PendingTodo, ...]
    recording_count: int | None
    latest_recording_title: str | None
    latest_summary: RecordingSummary | None
    charging: bool | None
    todos_truncated: bool
    recordings_truncated: bool
    device_status_healthy: bool
    recordings_healthy: bool
    summary_healthy: bool
    updated_at: datetime

    @property
    def degraded(self) -> bool:
        """Return whether any optional endpoint is degraded."""
        return (
            not (
                self.device_status_healthy
                and self.recordings_healthy
                and self.summary_healthy
            )
            or self.todos_truncated
            or self.recordings_truncated
        )


class MindClipCoordinator(DataUpdateCoordinator[MindClipData]):
    """Coordinate cloud polling for one physical MindClip."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api: MindClipApi,
        device_id: str,
        todo_store: MindClipTodoStore | None = None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="MindClip",
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api
        self.device_id = device_id
        self.todo_store = todo_store or MindClipTodoStore(hass, config_entry.entry_id)

    async def async_initialize(self) -> None:
        """Load persistent state before the first refresh."""
        await self.todo_store.async_load()

    async def async_acknowledge_todo(self, uid: str) -> None:
        """Acknowledge one locally pending To-Do."""
        pending = await self.todo_store.async_acknowledge(uid)
        if self.data is not None:
            self.async_set_updated_data(replace(self.data, pending_todos=pending))

    async def _async_update_data(self) -> MindClipData:
        """Fetch primary To-Dos and independently degradable optional data."""
        try:
            todos = await self.api.async_get_open_todo_count(self.device_id)
        except MindClipAuthError as err:
            raise ConfigEntryAuthFailed("SwitchBot authentication failed") from err
        except MindClipApiError as err:
            raise UpdateFailed("Unable to update MindClip To-Do data") from err

        pending_todos = await self.todo_store.async_process(
            todos.items, truncated=todos.truncated
        )

        charging: bool | None = None
        device_status_healthy = False
        try:
            status = await self.api.async_get_device_status(self.device_id)
            charging = status.charging
            device_status_healthy = True
        except MindClipAuthError as err:
            raise ConfigEntryAuthFailed("SwitchBot authentication failed") from err
        except MindClipApiError:
            pass

        recording_count: int | None = None
        latest_recording_title: str | None = None
        latest_summary: RecordingSummary | None = None
        recordings_truncated = False
        recordings_healthy = False
        summary_healthy = False
        try:
            recordings = await self.api.async_get_recordings(self.device_id)
            recording_count = recordings.total
            recordings_truncated = recordings.truncated
            recordings_healthy = True
            if recordings.latest is not None:
                latest_recording_title = recordings.latest.title
            if recordings.latest_transcribed is None:
                summary_healthy = True
            else:
                try:
                    latest_summary = await self.api.async_get_summary(
                        recordings.latest_transcribed.recording_id
                    )
                    summary_healthy = True
                except MindClipAuthError as err:
                    raise ConfigEntryAuthFailed(
                        "SwitchBot authentication failed"
                    ) from err
                except MindClipApiError:
                    pass
        except MindClipAuthError as err:
            raise ConfigEntryAuthFailed("SwitchBot authentication failed") from err
        except MindClipApiError as err:
            _LOGGER.warning(
                "MindClip recordings endpoint degraded: %s: %s",
                type(err).__name__,
                err,
            )

        return MindClipData(
            open_todo_count=todos.count,
            pending_todos=pending_todos,
            recording_count=recording_count,
            latest_recording_title=latest_recording_title,
            latest_summary=latest_summary,
            charging=charging,
            todos_truncated=todos.truncated,
            recordings_truncated=recordings_truncated,
            device_status_healthy=device_status_healthy,
            recordings_healthy=recordings_healthy,
            summary_healthy=summary_healthy,
            updated_at=datetime.now(UTC),
        )
