## What's changed

- Added response-only `get_recording`, `get_transcript`, and `get_summary` actions.
- Full private content is returned only to the explicit action caller and is not stored in entities, diagnostics, or Recorder.
- Transcript strings are preserved exactly as returned by SwitchBot, including JSON-encoded strings.
- Recording ownership, response fields, collection sizes, and text sizes are validated before data is returned.
- Added English and Croatian action descriptions, icons, privacy guidance, and regression tests.

Install the update and restart Home Assistant to load the new integration code.

[Full changelog](https://github.com/BeardedTinker/ha-mindclip/compare/v0.5.0...v0.6.0)
