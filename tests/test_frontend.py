"""Tests for the bundled MindClip dashboard card artifact."""

import json
from pathlib import Path

from custom_components.mindclip.frontend import CARD_URL_PATH, CARD_VERSION


def test_card_version_matches_integration_release() -> None:
    """The resource cache key and card artifact follow the integration version."""
    root = Path(__file__).parents[1]
    manifest = json.loads(
        (root / "custom_components/mindclip/manifest.json").read_text(encoding="utf-8")
    )
    card = (root / "custom_components/mindclip/www/mindclip-card.js").read_text(
        encoding="utf-8"
    )

    assert manifest["version"] == CARD_VERSION
    assert f'const CARD_VERSION = "{CARD_VERSION}";' in card
    assert CARD_URL_PATH.endswith("/mindclip-card.js")


def test_card_keeps_private_content_ephemeral() -> None:
    """The card offers opt-in controls without browser persistence APIs."""
    card = Path("custom_components/mindclip/www/mindclip-card.js").read_text(
        encoding="utf-8"
    )

    assert 'name: "enable_summary"' in card
    assert 'name: "enable_transcript"' in card
    assert "localStorage" not in card
    assert "sessionStorage" not in card
    assert "indexedDB" not in card
