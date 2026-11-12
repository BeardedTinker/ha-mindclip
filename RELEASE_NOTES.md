## What's changed

- Added battery level, recording, uploading and untransferred-file entities from the existing device status response.
- Added the latest recording timestamp and transcription status without additional API calls.
- Cached the latest summary by recording ID so an unchanged recording does not consume another summary request every 30 minutes.
- Added explicit HTTP rate-limit handling with a bounded `Retry-After` delay.

Install the update and restart Home Assistant to load the new integration code.

[Full changelog](https://github.com/BeardedTinker/ha-mindclip/compare/v0.4.0...v0.5.0)
