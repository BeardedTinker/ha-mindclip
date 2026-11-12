## What's changed

- Added a bundled, responsive MindClip recordings dashboard card with a visual editor.
- Configure the recent-recording limit and independently enable summary and transcript buttons.
- Added the bounded response-only `list_recordings` action; the card fetches private content only after an explicit click.
- Private card content stays in browser memory and is cleared when the card is removed.
- The card is registered automatically for storage-managed dashboards and uses a versioned resource URL for cache-safe updates.
- Added English and Croatian card text, backend validation, frontend syntax checks, tests, and privacy documentation.

Install the update and restart Home Assistant to load the new integration code.

[Full changelog](https://github.com/BeardedTinker/ha-mindclip/compare/v0.6.0...v0.7.0)
