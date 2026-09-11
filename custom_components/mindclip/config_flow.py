"""Config flow for the MindClip integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    MindClipApi,
    MindClipAuthError,
    MindClipCommunicationError,
    MindClipDevice,
    MindClipResponseError,
    MindClipSchemaError,
    normalize_device_id,
)
from .const import CONF_API_SECRET, CONF_API_TOKEN, CONF_DEVICE_ID, DOMAIN


def _auth_schema() -> vol.Schema:
    """Return the API credential schema."""
    return vol.Schema(
        {
            vol.Required(CONF_API_TOKEN): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Required(CONF_API_SECRET): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
        }
    )


def _credentials_schema(*, device_id: str) -> vol.Schema:
    """Return the reconfigure schema."""
    schema = dict(_auth_schema().schema)
    schema[vol.Required(CONF_DEVICE_ID, default=device_id)] = TextSelector()
    return vol.Schema(schema)


def _device_schema(devices: list[MindClipDevice]) -> vol.Schema:
    """Return a dropdown for discovered MindClip devices."""
    options = {
        device.device_id: f"{device.name} ({device.device_id})" for device in devices
    }
    return vol.Schema({vol.Required(CONF_DEVICE_ID): vol.In(options)})


def _manual_device_schema() -> vol.Schema:
    """Return a fallback manual device ID schema."""
    return vol.Schema({vol.Required(CONF_DEVICE_ID): TextSelector()})


def _reauth_schema() -> vol.Schema:
    """Return the credential-only reauthentication schema."""
    return _auth_schema()


class MindClipConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the MindClip config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up one physical MindClip."""
        errors: dict[str, str] = {}
        if user_input is not None:
            credentials = _normalize_credentials(user_input)
            if not credentials[CONF_API_TOKEN] or not credentials[CONF_API_SECRET]:
                errors["base"] = "invalid_auth"
            else:
                api = MindClipApi(
                    async_get_clientsession(self.hass),
                    credentials[CONF_API_TOKEN],
                    credentials[CONF_API_SECRET],
                )
                try:
                    devices = await api.async_get_devices()
                except MindClipAuthError:
                    errors["base"] = "invalid_auth"
                except MindClipCommunicationError:
                    errors["base"] = "cannot_connect"
                except MindClipResponseError:
                    errors["base"] = "api_error"
                except MindClipSchemaError:
                    errors["base"] = "invalid_response"
                else:
                    self._pending_credentials = credentials
                    if len(devices) == 1:
                        result = await self._async_finish_setup(devices[0].device_id)
                        if not isinstance(result, str):
                            return result
                        errors["base"] = result
                    elif devices:
                        self._discovered_devices = devices
                        return await self.async_step_select_device()
                    else:
                        return await self.async_step_manual_device()

        return self.async_show_form(
            step_id="user",
            data_schema=_auth_schema(),
            errors=errors,
        )

    async def async_step_select_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select one of multiple discovered MindClip devices."""
        errors: dict[str, str] = {}
        if user_input is not None:
            result = await self._async_finish_setup(user_input[CONF_DEVICE_ID])
            if not isinstance(result, str):
                return result
            errors["base"] = result
        return self.async_show_form(
            step_id="select_device",
            data_schema=_device_schema(self._discovered_devices),
            errors=errors,
        )

    async def async_step_manual_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Accept a device ID when discovery returns no MindClip."""
        errors: dict[str, str] = {}
        if user_input is not None:
            result = await self._async_finish_setup(user_input[CONF_DEVICE_ID])
            if not isinstance(result, str):
                return result
            errors["base"] = result
        return self.async_show_form(
            step_id="manual_device",
            data_schema=_manual_device_schema(),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication for an existing config entry."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate and save replacement credentials."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _normalize_input(
                {**user_input, CONF_DEVICE_ID: entry.data[CONF_DEVICE_ID]}
            )
            error = await self._async_validate(data)
            if error is None:
                await self.async_set_unique_id(data[CONF_DEVICE_ID])
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=data,
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_reauth_schema(),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate and update an existing config entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _normalize_input(user_input)
            error = await self._async_validate(data)
            if error is None:
                await self.async_set_unique_id(data[CONF_DEVICE_ID])
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=data,
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_credentials_schema(device_id=entry.data[CONF_DEVICE_ID]),
            errors=errors,
        )

    async def _async_validate(self, data: dict[str, str]) -> str | None:
        """Validate credentials and device access using device status."""
        if not data[CONF_API_TOKEN] or not data[CONF_API_SECRET]:
            return "invalid_auth"
        if not data[CONF_DEVICE_ID] or len(data[CONF_DEVICE_ID]) > 255:
            return "invalid_device"
        api = MindClipApi(
            async_get_clientsession(self.hass),
            data[CONF_API_TOKEN],
            data[CONF_API_SECRET],
        )
        try:
            await api.async_get_device_status(data[CONF_DEVICE_ID])
        except MindClipAuthError:
            return "invalid_auth"
        except MindClipCommunicationError:
            return "cannot_connect"
        except MindClipResponseError as err:
            if err.status_code in (151, 152):
                return "invalid_device"
            return "api_error"
        except MindClipSchemaError:
            return "invalid_response"
        return None

    async def _async_finish_setup(self, device_id: str) -> ConfigFlowResult | str:
        """Validate a selected device and create its config entry."""
        data = {
            **self._pending_credentials,
            CONF_DEVICE_ID: normalize_device_id(str(device_id)),
        }
        error = await self._async_validate(data)
        if error is not None:
            return error
        await self.async_set_unique_id(data[CONF_DEVICE_ID])
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=_entry_title(data[CONF_DEVICE_ID]),
            data=data,
        )


def _normalize_input(user_input: dict[str, Any]) -> dict[str, str]:
    """Normalize config entry values."""
    return {
        CONF_API_TOKEN: str(user_input[CONF_API_TOKEN]).strip(),
        CONF_API_SECRET: str(user_input[CONF_API_SECRET]).strip(),
        CONF_DEVICE_ID: normalize_device_id(str(user_input[CONF_DEVICE_ID])),
    }


def _normalize_credentials(user_input: dict[str, Any]) -> dict[str, str]:
    """Normalize API credentials before device discovery."""
    return {
        CONF_API_TOKEN: str(user_input[CONF_API_TOKEN]).strip(),
        CONF_API_SECRET: str(user_input[CONF_API_SECRET]).strip(),
    }


def _entry_title(device_id: str) -> str:
    """Return a compact title that distinguishes multiple devices."""
    return f"MindClip {device_id[-6:]}"
