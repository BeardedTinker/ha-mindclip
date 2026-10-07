## What's changed

- Added a Home Assistant event entity that emits `created` for each newly discovered MindClip To-Do.
- Event attributes contain the bounded title, hashed To-Do ID, creation time and optional reminder time.
- The initial baseline, already-seen items and later edits do not emit duplicate creation events.
- The integration does not execute services or interpret To-Do titles as commands; automations remain explicitly under the user's control.
- Events follow the existing 30-minute polling interval and are not intended for time-critical timers.

Install the update and restart Home Assistant to load the new integration code.

[Full changelog](https://github.com/BeardedTinker/ha-mindclip/compare/v0.3.3...v0.4.0)
