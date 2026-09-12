## What's changed

- Optional Calendar sync can target any writable Home Assistant Calendar entity.
- Reminder To-Dos create fixed-duration events and are acknowledged only after successful delivery.
- Existing events are detected by hashed To-Do ID or matching title and start time to prevent duplicates.

Calendar sync is disabled by default. Install the update, restart Home Assistant, then open the MindClip integration's Configure dialog to enable it.

[Full changelog](https://github.com/BeardedTinker/ha-mindclip/compare/v0.2.1...v0.3.0)
