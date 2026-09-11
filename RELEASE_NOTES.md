## What's changed

- A new Last successful poll sensor shows when MindClip data was last refreshed.
- The sensor uses the existing coordinator timestamp and makes no additional API requests.
- Its previous timestamp remains visible when a later refresh fails.

Existing config entries need no reconfiguration; install the update and restart Home Assistant.

[Full changelog](https://github.com/BeardedTinker/ha-mindclip/compare/v0.2.0...v0.2.1)
