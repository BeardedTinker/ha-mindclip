## What's changed

- Recordings with a missing, empty, or whitespace-only display name now use `Untitled recording`.
- One malformed title no longer makes the recording count, latest recording and latest summary unavailable.
- Sanitized recording endpoint failures are logged without response payloads, identifiers or credentials.
- Added regression coverage for all observed invalid-title variants.

Install the update and restart Home Assistant to load the new integration code.

[Full changelog](https://github.com/BeardedTinker/ha-mindclip/compare/v0.3.2...v0.3.3)
