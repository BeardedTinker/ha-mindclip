# MindClip for Home Assistant

[![Open your Home Assistant instance and open MindClip in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=BeardedTinker&repository=ha-mindclip&category=integration)

MindClip is an unofficial alpha-quality Home Assistant custom integration for ingesting selected data from a SwitchBot AI MindClip through SwitchBot OpenAPI v1.1.

Version 0.6.0 is intended for early testing. It is not production-ready, is not listed in the default Home Assistant Marketplace catalog, and may need adjustment if SwitchBot changes the new MindClip endpoints.

## Features

Each configured physical MindClip creates these entities:

- Open To-Do count
- Recording count
- Latest recording title
- Latest recording time and transcription status
- Latest summary text capped at 255 characters, with its recording ID as an attribute
- Battery level, charging, recording and upload status
- Indicator for files that have not yet transferred from the MindClip
- Pending To-Dos as a native Home Assistant To-do list
- A Home Assistant event entity that emits `created` for each newly discovered To-Do
- Last successful poll timestamp, retained when a later refresh fails
- Optional synchronization of reminder To-Dos to a writable Home Assistant Calendar
- Response-only actions for recording details, full transcripts, and complete AI summaries

The integration polls every 30 minutes. To-Dos are the primary data source. Device status, recording, and summary failures degrade only their related entities when possible. Authentication failures start Home Assistant's reauthentication flow. The latest summary is requested again only when the newest successfully transcribed recording changes. HTTP rate limits can extend the next polling interval according to SwitchBot's bounded `Retry-After` value.

The event entity exposes the new To-Do's hashed ID, title, creation time and optional reminder time. It does not execute services or interpret To-Do titles as commands. Automations can use the event entity as an explicit, user-controlled trigger.

### On-demand actions

The integration provides three read-only actions that return data only when explicitly called:

- `mindclip.get_recording` returns complete recording metadata.
- `mindclip.get_transcript` returns the transcript string exactly as supplied by SwitchBot plus identified speakers.
- `mindclip.get_summary` returns the transcript, AI summary, template result, atmosphere, extracted To-Dos, and speakers.

Each action requires the MindClip `config_entry_id` and a `recording_id`. Transcript and summary calls first verify that the recording belongs to the selected MindClip. They return action response data and do not create entities or copy the response into entity state, attributes, diagnostics, or Recorder. Action responses can still be retained in Home Assistant automation/script traces, so avoid calling these actions from traced automations when that retention is not acceptable.

Example Developer Tools action data:

```yaml
config_entry_id: 01EXAMPLEMINDCLIPCONFIGENTRY
recording_id: 5f3a1c2e9b7d
```

## Installation

1. Select the Marketplace button above, or open **Settings > Marketplace**, select **Add from link**, and enter `https://github.com/BeardedTinker/ha-mindclip`.
2. If Home Assistant asks for a content type, select **Integration**.
3. Install **MindClip** through the Marketplace.
4. Restart Home Assistant.
5. Go to **Settings > Devices & services > Add integration** and search for **MindClip**.

On Home Assistant 2026.10 and older, add the same repository through HACS as a custom repository with category **Integration**, install **MindClip** through HACS, restart Home Assistant, and add the integration from **Settings > Devices & services**.

Manual installation is also possible by placing `custom_components/mindclip` in the Home Assistant configuration directory and restarting Home Assistant.

## Setup

Create a SwitchBot Open Token and Secret Key from Developer Options in the SwitchBot app. During setup, enter:

- API token
- API secret

The integration discovers AI MindClip devices on the SwitchBot account. A single device is selected automatically; multiple devices are shown in a dropdown. Manual device ID entry is offered only if discovery returns no MindClip. Setup then validates access by requesting device status. One config entry represents one physical MindClip, and multiple MindClips can be configured. Credentials can be replaced through reauthentication; reconfiguration validates updates while preserving the device identity.

### Calendar sync

Open the integration's **Configure** dialog to optionally select a writable Home Assistant Calendar and an event duration. Sync is disabled when no Calendar is selected. Newly pending To-Dos with a reminder create timed events; the integration checks for the same To-Do ID or title and start time before creation. Successful creation or an existing match acknowledges the local pending item. Failures leave it pending for the next poll. Items without reminders always remain available for manual acknowledgement.

SwitchBot documents OpenAPI as limited to personal use and 10,000 calls per user per day. Commercial or large-scale use requires an arrangement with SwitchBot.

## Privacy

The API token and secret are stored in the Home Assistant config entry because they are required to sign requests. They are never placed in request URLs, entity attributes, diagnostics, or log messages generated by this integration.

The integration does not place full transcripts, transcript segments, speaker details, complete summaries, raw API payloads, or credentials in entities or diagnostics. Private recording content is returned only by an explicit on-demand action and may appear in the caller's automation or script trace. Newly discovered To-Do titles and reminder times are stored in Home Assistant and exposed through the pending To-do and event entities. When Calendar sync is enabled, the title, reminder time and a hashed To-Do ID are written to the selected Calendar. The latest recording title, time and transcription status are exposed as separate sensor states. The latest summary sensor exposes at most 255 characters of summary text as its state and the associated recording ID as one attribute.

Diagnostics contain only safe counts, booleans, endpoint health, pagination truncation flags, the polling interval, and the last successful update timestamp. They omit device and recording identifiers and all user content.

## Roadmap

- Continue improving entities, diagnostics and documentation as the MindClip API evolves.

## Known limitations

- SwitchBot uses an `Unauthorized` response for both invalid credentials and exceeding the daily request limit. Reaching the limit can therefore start Home Assistant's reauthentication flow even when the saved credentials remain valid.
- To-Do and recording pagination is capped at 10 pages of 100 items per refresh. Counts based on retrieved To-Dos can therefore be a lower bound for very large accounts.
- The recording and summary APIs are new and their response behavior may evolve.
- An absent latest recording appears as an unknown state when its endpoint is otherwise healthy. The summary sensor uses the newest successfully transcribed recording, so a recording still being processed does not hide the previous summary.
- The first refresh establishes a baseline and does not add existing SwitchBot To-Dos to the pending list. Later items persist until marked complete in Home Assistant. This acknowledgement does not complete or modify the source item in SwitchBot.
- Calendar sync handles reminder To-Dos only and creates fixed-duration events. A failure after the Calendar accepts an event but before local acknowledgement can delay acknowledgement until the next duplicate check.
- Daily/weekly summaries, urgent To-Dos, webhooks, control commands, YAML setup, `command_line`, and `shell_command` are not implemented.

Any change to custom integration code requires a full Home Assistant restart.

## Troubleshooting

- For temporary network failures or request timeouts, leave the integration configured. Home Assistant marks the refresh unsuccessful and tries again at the next polling interval.
- If Home Assistant requests reauthentication, verify the credentials and confirm that the SwitchBot daily API limit has not been reached. SwitchBot can report both conditions as `Unauthorized`.
- Use the integration diagnostics to check endpoint health and the last successful update without exposing credentials or user content.

## Development

The pinned Home Assistant 2026.10.0 test environment requires Python 3.14.2 or newer. Install `requirements_test.txt`, then run `ruff format --check .`, `ruff check .`, and `pytest`. The GitHub Actions test workflow uses Python 3.14 for these checks; Python 3.13 cannot install this test environment.

This project is not affiliated with, endorsed by, or supported by SwitchBot.

## License

[MIT](LICENSE)
