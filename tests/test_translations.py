"""Tests for translation-only custom integration localization."""

import json
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


async def test_croatian_translations_load(hass) -> None:
    """Croatian config and entity translations load."""
    translations = await translation.async_get_translations(
        hass,
        "hr",
        "config",
        {DOMAIN},
    )
    entity_translations = await translation.async_get_translations(
        hass,
        "hr",
        "entity",
        {DOMAIN},
    )

    assert (
        translations["component.mindclip.config.step.user.data.api_secret"]
        == "API tajna"
    )
    assert (
        entity_translations["component.mindclip.entity.sensor.open_todo_count.name"]
        == "Broj otvorenih zadataka"
    )


def test_croatian_translation_keys_match_english() -> None:
    """Croatian translations contain every English translation key."""
    translation_dir = Path("custom_components/mindclip/translations")
    english = json.loads((translation_dir / "en.json").read_text(encoding="utf-8"))
    croatian = json.loads((translation_dir / "hr.json").read_text(encoding="utf-8"))

    def leaf_paths(value: object, prefix: str = "") -> set[str]:
        if not isinstance(value, dict):
            return {prefix}
        return {
            path
            for key, child in value.items()
            for path in leaf_paths(child, f"{prefix}.{key}" if prefix else key)
        }

    assert leaf_paths(croatian) == leaf_paths(english)
