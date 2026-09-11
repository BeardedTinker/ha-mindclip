"""Tests for translation-only custom integration localization."""

from pathlib import Path

from homeassistant.helpers import translation

from custom_components.mindclip.const import DOMAIN


async def test_english_translations_load_without_strings_json(hass) -> None:
    """English config and entity text loads directly from translations."""
    translations = await translation.async_get_translations(
        hass,
        "en",
        "config",
        {DOMAIN},
    )
    entity_translations = await translation.async_get_translations(
        hass,
        "en",
        "entity",
        {DOMAIN},
    )

    assert (
        translations["component.mindclip.config.step.user.data.api_token"]
        == "API token"
    )
    assert (
        translations["component.mindclip.config.error.invalid_auth"]
        == "SwitchBot rejected the API token or secret."
    )
    assert (
        entity_translations["component.mindclip.entity.sensor.open_todo_count.name"]
        == "Open To-Do count"
    )
    assert not Path("custom_components/mindclip/strings.json").exists()
    assert not any(
        "[%key:" in text
        for text in (*translations.values(), *entity_translations.values())
    )
