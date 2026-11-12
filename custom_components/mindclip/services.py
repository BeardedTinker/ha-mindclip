"""Response-only actions for the MindClip integration."""

from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import asdict
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import service

from .api import (
    FullRecordingSummary,
    MindClipApiError,
    MindClipAuthError,
    MindClipCommunicationError,
    MindClipRateLimitError,
    RecordingDetail,
    RecordingTranscript,
)
from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_RECORDING_ID,
    CONF_DEVICE_ID,
    DOMAIN,
    MAX_STATE_LENGTH,
    SERVICE_GET_RECORDING,
    SERVICE_GET_SUMMARY,
    SERVICE_GET_TRANSCRIPT,
)


def _recording_id(value: Any) -> str:
    """Validate and normalize a recording ID without exposing it in errors."""
    recording_id = cv.string(value).strip()
    if not recording_id or len(recording_id) > MAX_STATE_LENGTH:
        raise vol.Invalid("invalid recording ID")
    return recording_id


ACTION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_RECORDING_ID): _recording_id,
    }
)


async def _async_api_call[T](awaitable: Awaitable[T]) -> T:
    """Translate sanitized API failures into localized action failures."""
    try:
        return await awaitable
    except MindClipApiError as err:
        if isinstance(err, MindClipAuthError):
            translation_key = "action_invalid_auth"
        elif isinstance(err, MindClipRateLimitError):
            translation_key = "action_rate_limited"
        elif isinstance(err, MindClipCommunicationError):
            translation_key = "action_cannot_connect"
        else:
            translation_key = "action_invalid_response"
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
        ) from err


def _recording_response(detail: RecordingDetail) -> dict[str, Any]:
    """Serialize recording details for an action response."""
    return asdict(detail)


def _transcript_response(transcript: RecordingTranscript) -> dict[str, Any]:
    """Serialize a transcript for an action response."""
    return {
        "recording_id": transcript.recording_id,
        "transcription_status": transcript.transcription_status,
        "transcription": transcript.transcription,
        "speakers": [
            {
                "speaker": speaker.speaker,
                "speaker_name": speaker.speaker_name,
            }
            for speaker in transcript.speakers
        ],
    }


def _summary_response(summary: FullRecordingSummary) -> dict[str, Any]:
    """Serialize a complete summary for an action response."""
    return {
        "recording_id": summary.recording_id,
        "transcription_status": summary.transcription_status,
        "transcription": summary.transcription,
        "summary": summary.summary,
        "template": summary.template,
        "atmosphere": summary.atmosphere,
        "todos": [asdict(todo) for todo in summary.todos],
        "speakers": [asdict(speaker) for speaker in summary.speakers],
    }


def async_setup_services(hass: HomeAssistant) -> None:
    """Register response-only MindClip actions."""

    async def async_get_recording(call: ServiceCall) -> dict[str, Any]:
        """Return validated recording details."""
        entry = service.async_get_config_entry(
            hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
        )
        detail = await _async_api_call(
            entry.runtime_data.api.async_get_recording_detail(
                call.data[ATTR_RECORDING_ID], entry.data[CONF_DEVICE_ID]
            )
        )
        return _recording_response(detail)

    async def async_get_transcript(call: ServiceCall) -> dict[str, Any]:
        """Return a validated transcript after checking recording ownership."""
        entry = service.async_get_config_entry(
            hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
        )
        recording_id = call.data[ATTR_RECORDING_ID]
        await _async_api_call(
            entry.runtime_data.api.async_get_recording_detail(
                recording_id, entry.data[CONF_DEVICE_ID]
            )
        )
        transcript = await _async_api_call(
            entry.runtime_data.api.async_get_transcript(recording_id)
        )
        return _transcript_response(transcript)

    async def async_get_summary(call: ServiceCall) -> dict[str, Any]:
        """Return a validated full summary after checking recording ownership."""
        entry = service.async_get_config_entry(
            hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
        )
        recording_id = call.data[ATTR_RECORDING_ID]
        device_id = entry.data[CONF_DEVICE_ID]
        await _async_api_call(
            entry.runtime_data.api.async_get_recording_detail(recording_id, device_id)
        )
        summary = await _async_api_call(
            entry.runtime_data.api.async_get_full_summary(recording_id, device_id)
        )
        return _summary_response(summary)

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_RECORDING,
        async_get_recording,
        schema=ACTION_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_TRANSCRIPT,
        async_get_transcript,
        schema=ACTION_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_SUMMARY,
        async_get_summary,
        schema=ACTION_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
