"""Privacy-redacted diagnostics for the MindClip integration."""

from typing import Any

from homeassistant.core import HomeAssistant

from . import MindClipConfigEntry
from .const import (
    CONF_CALENDAR_ENTITY,
    CONF_EVENT_DURATION_MINUTES,
    DEFAULT_EVENT_DURATION_MINUTES,
    UPDATE_INTERVAL,
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MindClipConfigEntry
) -> dict[str, Any]:
    """Return diagnostics containing no content or identifiers."""
    data = entry.runtime_data.coordinator.data
    return {
        "config": {
            "poll_interval_minutes": int(UPDATE_INTERVAL.total_seconds() / 60),
            "calendar_sync_configured": bool(entry.options.get(CONF_CALENDAR_ENTITY)),
            "calendar_event_duration_minutes": entry.options.get(
                CONF_EVENT_DURATION_MINUTES, DEFAULT_EVENT_DURATION_MINUTES
            ),
        },
        "data": {
            "open_todo_count": data.open_todo_count,
            "pending_todo_count": len(data.pending_todos),
            "recording_count": data.recording_count,
            "latest_recording_present": data.latest_recording_title is not None,
            "summary_present": data.latest_summary is not None,
            "charging": data.charging,
            "todos_truncated": data.todos_truncated,
            "recordings_truncated": data.recordings_truncated,
            "updated_at": data.updated_at.isoformat(),
        },
        "health": {
            "status": "degraded" if data.degraded else "healthy",
            "device_status": data.device_status_healthy,
            "recordings": data.recordings_healthy,
            "summary": data.summary_healthy,
        },
    }
