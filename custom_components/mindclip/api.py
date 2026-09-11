"""Async client for the SwitchBot AI MindClip API."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import aiohttp

from .const import (
    API_BASE_URL,
    API_MAX_PAGES,
    API_PAGE_SIZE,
    API_REQUEST_TIMEOUT,
    MAX_STATE_LENGTH,
    SUMMARY_ATTRIBUTE_LIMIT,
)

_SUCCESS_STATUS = 100
_AUTH_STATUS_CODES = {401}
_AUTH_MESSAGE_PARTS = (
    "authentication failed",
    "invalid signature",
    "invalid token",
    "unauthorized",
)


class MindClipApiError(Exception):
    """Base exception for MindClip API failures."""


class MindClipAuthError(MindClipApiError):
    """Raised when SwitchBot rejects authentication."""


class MindClipCommunicationError(MindClipApiError):
    """Raised when the SwitchBot service cannot be reached."""


class MindClipResponseError(MindClipApiError):
    """Raised when SwitchBot returns an unsuccessful API status."""

    def __init__(self, status_code: int) -> None:
        """Initialize a response error without retaining response content."""
        self.status_code = status_code
        super().__init__(f"SwitchBot API request failed with status {status_code}")


class MindClipSchemaError(MindClipApiError):
    """Raised when a SwitchBot response has an unexpected schema."""


@dataclass(frozen=True, slots=True)
class MindClipDevice:
    """A discovered AI MindClip available to the account."""

    device_id: str
    name: str


@dataclass(frozen=True, slots=True)
class DeviceStatus:
    """Privacy-minimized MindClip device status."""

    charging: bool


@dataclass(frozen=True, slots=True)
class Recording:
    """Minimal recording metadata required by entities."""

    recording_id: str
    title: str
    created_time: int
    transcription_status: int


@dataclass(frozen=True, slots=True)
class RecordingCollection:
    """Bounded recording result."""

    total: int
    latest: Recording | None
    latest_transcribed: Recording | None
    truncated: bool


@dataclass(frozen=True, slots=True)
class MindClipTodo:
    """Minimal To-Do data required for local pending tracking."""

    uid: str
    title: str
    created_time: int
    reminder_time: int | None


@dataclass(frozen=True, slots=True)
class OpenTodoCount:
    """Bounded device-specific open To-Do count."""

    count: int
    truncated: bool
    items: tuple[MindClipTodo, ...] = ()


@dataclass(frozen=True, slots=True)
class RecordingSummary:
    """Privacy-minimized summary for one recording."""

    recording_id: str
    short_text: str | None


class MindClipApi:
    """Minimal async client for ingestion-only MindClip API access."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        token: str,
        secret: str,
        *,
        clock: Callable[[], float] = time.time,
        nonce_factory: Callable[[], object] = uuid4,
        request_timeout: float = API_REQUEST_TIMEOUT,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._token = token
        self._secret = secret
        self._clock = clock
        self._nonce_factory = nonce_factory
        self._request_timeout = request_timeout

    def _request_headers(self) -> dict[str, str]:
        """Return fresh SwitchBot v1.1 authentication headers."""
        timestamp = str(int(self._clock() * 1000))
        nonce = str(self._nonce_factory())
        message = f"{self._token}{timestamp}{nonce}".encode()
        signature = base64.b64encode(
            hmac.new(self._secret.encode(), message, hashlib.sha256).digest()
        ).decode()
        return {
            "Authorization": self._token,
            "sign": signature,
            "nonce": nonce,
            "t": timestamp,
            "Content-Type": "application/json",
        }

    async def _async_request(
        self, path: str, *, params: Mapping[str, str | int] | None = None
    ) -> Mapping[str, Any]:
        """Make one request and return a validated successful response body."""
        try:
            async with asyncio.timeout(self._request_timeout):
                async with self._session.get(
                    f"{API_BASE_URL}{path}",
                    headers=self._request_headers(),
                    params=params,
                ) as response:
                    if response.status in _AUTH_STATUS_CODES:
                        raise MindClipAuthError("SwitchBot authentication failed")
                    if not 200 <= response.status < 300:
                        raise MindClipCommunicationError(
                            f"SwitchBot HTTP request failed with status {response.status}"
                        )
                    try:
                        payload = await response.json(content_type=None)
                    except (aiohttp.ClientError, ValueError) as err:
                        raise MindClipSchemaError(
                            "SwitchBot returned invalid JSON"
                        ) from err
        except MindClipApiError:
            raise
        except TimeoutError as err:
            raise MindClipCommunicationError("SwitchBot request timed out") from err
        except aiohttp.ClientError as err:
            raise MindClipCommunicationError(
                "Unable to communicate with SwitchBot"
            ) from err

        if not isinstance(payload, Mapping):
            raise MindClipSchemaError("SwitchBot response is not an object")

        message = payload.get("message")
        message_text = message.lower() if isinstance(message, str) else ""
        if any(part in message_text for part in _AUTH_MESSAGE_PARTS):
            raise MindClipAuthError("SwitchBot authentication failed")
        status_code = _parse_status_code(payload.get("statusCode"))
        if status_code in _AUTH_STATUS_CODES:
            raise MindClipAuthError("SwitchBot authentication failed")
        if status_code != _SUCCESS_STATUS:
            raise MindClipResponseError(status_code)

        return _require_mapping(payload.get("body"), "response body")

    async def async_get_devices(self) -> list[MindClipDevice]:
        """Discover AI MindClip devices available to the account."""
        body = await self._async_request("/devices")
        items = body.get("deviceList")
        if not isinstance(items, list):
            raise MindClipSchemaError("SwitchBot returned an invalid device list")

        devices: dict[str, MindClipDevice] = {}
        for raw_item in items:
            item = _require_mapping(raw_item, "device list item")
            if item.get("deviceType") != "AI MindClip":
                continue
            device_id = normalize_device_id(
                _require_string(item.get("deviceId"), "device ID")
            )
            name = item.get("deviceName")
            if not isinstance(name, str) or not (name := name.strip()):
                name = _entry_device_name(device_id)
            devices[device_id] = MindClipDevice(device_id=device_id, name=name)

        return sorted(devices.values(), key=lambda device: device.name.casefold())

    async def async_get_device_status(self, device_id: str) -> DeviceStatus:
        """Get and minimize device status."""
        body = await self._async_request(f"/devices/{quote(device_id, safe='')}/status")
        response_device_id = _require_string(body.get("deviceId"), "device ID")
        if normalize_device_id(response_device_id) != normalize_device_id(device_id):
            raise MindClipSchemaError("SwitchBot returned a different device")
        if body.get("deviceType") != "AI MindClip":
            raise MindClipSchemaError("Configured device is not an AI MindClip")
        charging_status = _require_integer(body.get("chargingStatus"), "charge state")
        if charging_status not in (0, 1):
            raise MindClipSchemaError("SwitchBot returned an invalid charge state")
        return DeviceStatus(charging=bool(charging_status))

    async def async_get_open_todo_count(self, device_id: str) -> OpenTodoCount:
        """Get bounded open To-Dos for this device."""
        todos: list[MindClipTodo] = []
        normalized_device_id = normalize_device_id(device_id)
        pages = 1
        for page_number in range(1, API_MAX_PAGES + 1):
            body = await self._async_request(
                "/mindclip/todos",
                params={
                    "completedNum": 0,
                    "pageNum": page_number,
                    "pageSize": API_PAGE_SIZE,
                },
            )
            pages, items = _parse_page(body)
            for item in items:
                item_device_id = _require_string(item.get("deviceID"), "device ID")
                is_completed = item.get("isCompleted")
                if not isinstance(is_completed, bool):
                    raise MindClipSchemaError(
                        "SwitchBot returned an invalid To-Do completion state"
                    )
                if (
                    not is_completed
                    and normalize_device_id(item_device_id) == normalized_device_id
                ):
                    todos.append(_parse_todo(item))
            if page_number >= pages:
                return OpenTodoCount(
                    count=len(todos), truncated=False, items=tuple(todos)
                )
        return OpenTodoCount(
            count=len(todos),
            truncated=pages > API_MAX_PAGES,
            items=tuple(todos),
        )

    async def async_get_recordings(self, device_id: str) -> RecordingCollection:
        """Get a bounded recording count and latest recording metadata."""
        recordings: list[Recording] = []
        pages = 1
        total = 0
        for page_number in range(1, API_MAX_PAGES + 1):
            body = await self._async_request(
                "/mindclip/recordings",
                params={
                    "deviceID": device_id,
                    "pageNum": page_number,
                    "pageSize": API_PAGE_SIZE,
                },
            )
            pages, items = _parse_page(body)
            if page_number == 1:
                total = _require_non_negative_integer(body.get("total"), "total")
            recordings.extend(_parse_recording(item) for item in items)
            if page_number >= pages:
                break

        latest = max(recordings, key=lambda item: item.created_time, default=None)
        latest_transcribed = max(
            (
                recording
                for recording in recordings
                if recording.transcription_status == 2
            ),
            key=lambda item: item.created_time,
            default=None,
        )
        return RecordingCollection(
            total=total,
            latest=latest,
            latest_transcribed=latest_transcribed,
            truncated=pages > API_MAX_PAGES,
        )

    async def async_get_summary(self, recording_id: str) -> RecordingSummary:
        """Get only the short AI summary required by the summary entity."""
        body = await self._async_request(
            f"/mindclip/summaries/{quote(recording_id, safe='')}"
        )
        response_recording_id = _require_string(body.get("fileID"), "recording ID")
        if response_recording_id != recording_id:
            raise MindClipSchemaError("SwitchBot returned a different recording")
        summary = body.get("aiSummaryResult")
        if not isinstance(summary, str):
            raise MindClipSchemaError("SwitchBot returned an invalid summary")
        short_text = summary.strip()[:SUMMARY_ATTRIBUTE_LIMIT] or None
        return RecordingSummary(recording_id=recording_id, short_text=short_text)


def normalize_device_id(device_id: str) -> str:
    """Normalize a stable SwitchBot device identifier."""
    return device_id.strip().upper()


def _entry_device_name(device_id: str) -> str:
    """Return a fallback name for a discovered device."""
    return f"MindClip {device_id[-6:]}"


def _parse_page(body: Mapping[str, Any]) -> tuple[int, list[Mapping[str, Any]]]:
    """Validate the common paginated response fields."""
    pages = _require_non_negative_integer(body.get("pages"), "page count")
    items = body.get("list")
    if not isinstance(items, list):
        raise MindClipSchemaError("SwitchBot response has no valid item list")
    parsed_items: list[Mapping[str, Any]] = []
    for item in items:
        parsed_items.append(_require_mapping(item, "list item"))
    return pages, parsed_items


def _parse_recording(item: Mapping[str, Any]) -> Recording:
    """Return only safe recording fields needed for entity state."""
    recording_id = _require_string(item.get("id"), "recording ID")
    if len(recording_id) > MAX_STATE_LENGTH:
        raise MindClipSchemaError("SwitchBot returned an invalid recording ID")
    title = _require_string(item.get("displayName"), "recording title")[
        :MAX_STATE_LENGTH
    ]
    created_time = _require_non_negative_integer(
        item.get("createdTime"), "recording creation time"
    )
    transcription_status = _require_non_negative_integer(
        item.get("transcribeStatus"), "transcription status"
    )
    if transcription_status > 5:
        raise MindClipSchemaError("SwitchBot returned an invalid transcription status")
    return Recording(
        recording_id=recording_id,
        title=title,
        created_time=created_time,
        transcription_status=transcription_status,
    )


def _parse_todo(item: Mapping[str, Any]) -> MindClipTodo:
    """Return bounded fields needed for pending tracking."""
    recording_id = _require_string(item.get("fileID"), "recording ID")
    created_time = _require_non_negative_integer(
        item.get("createdTime"), "To-Do creation time"
    )
    title = _require_string(item.get("title"), "To-Do title")[:MAX_STATE_LENGTH]
    reminder_time = _require_non_negative_integer(
        item.get("reminderTime", 0), "To-Do reminder time"
    )
    uid = hashlib.sha256(f"{recording_id}|{created_time}".encode()).hexdigest()
    return MindClipTodo(
        uid=uid,
        title=title,
        created_time=created_time,
        reminder_time=reminder_time or None,
    )


def _require_mapping(value: object, field: str) -> Mapping[str, Any]:
    """Return a mapping or raise a sanitized schema error."""
    if not isinstance(value, Mapping):
        raise MindClipSchemaError(f"SwitchBot returned an invalid {field}")
    return value


def _require_string(value: object, field: str) -> str:
    """Return a non-empty string or raise a sanitized schema error."""
    if not isinstance(value, str) or not value:
        raise MindClipSchemaError(f"SwitchBot returned an invalid {field}")
    return value


def _require_integer(value: object, field: str) -> int:
    """Return an integer or raise a sanitized schema error."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise MindClipSchemaError(f"SwitchBot returned an invalid {field}")
    return value


def _require_non_negative_integer(value: object, field: str) -> int:
    """Return a non-negative integer or raise a sanitized schema error."""
    result = _require_integer(value, field)
    if result < 0:
        raise MindClipSchemaError(f"SwitchBot returned an invalid {field}")
    return result


def _parse_status_code(value: object) -> int:
    """Return a bounded numeric status without retaining arbitrary content."""
    if isinstance(value, str):
        if not (value.isascii() and value.isdigit() and len(value) <= 4):
            raise MindClipSchemaError("SwitchBot response has no valid status")
        value = int(value)
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 9999:
        raise MindClipSchemaError("SwitchBot response has no valid status")
    return value
