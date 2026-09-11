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
    MindClipResponseError,
    MindClipSchemaError,
    normalize_device_id,
)
from .const import CONF_API_SECRET, CONF_API_TOKEN, CONF_DEVICE_ID, DOMAIN


def _credentials_schema(*, device_id: str | None = None) -> vol.Schema:
    """Return the setup or reconfigure schema."""
    device_key = (
        vol.Required(CONF_DEVICE_ID, default=device_id)
        if device_id is not None
        else vol.Required(CONF_DEVICE_ID)
    )
    return vol.Schema(
        {
            vol.Required(CONF_API_TOKEN): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Required(CONF_API_SECRET): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            device_key: TextSelector(),
        }
    )


def _reauth_schema() -> vol.Schema:
    """Return the credential-only reauthentication schema."""
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


class MindClipConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the MindClip config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up one physical MindClip."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _normalize_input(user_input)
            error = await self._async_validate(data)
            if error is None:
                await self.async_set_unique_id(data[CONF_DEVICE_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=_entry_title(data[CONF_DEVICE_ID]),
                    data=data,
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=_credentials_schema(),
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


def _normalize_input(user_input: dict[str, Any]) -> dict[str, str]:
    """Normalize config entry values."""
    return {
        CONF_API_TOKEN: str(user_input[CONF_API_TOKEN]).strip(),
        CONF_API_SECRET: str(user_input[CONF_API_SECRET]).strip(),
        CONF_DEVICE_ID: normalize_device_id(str(user_input[CONF_DEVICE_ID])),
    }


def _entry_title(device_id: str) -> str:
    """Return a compact title that distinguishes multiple devices."""
    return f"MindClip {device_id[-6:]}"
