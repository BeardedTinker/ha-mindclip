## What's changed

- Invalid or out-of-range reminder timestamps no longer stop Calendar synchronization.
- A malformed reminder remains pending while later valid reminders continue to sync.
- Added regression coverage for the failure case.

Install the update and restart Home Assistant to load the new integration code.

[Full changelog](https://github.com/BeardedTinker/ha-mindclip/compare/v0.3.1...v0.3.2)
