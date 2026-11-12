// Bundled MindClip card. Private recording content is fetched only after an
// explicit click and is kept only in this card instance's browser memory.

const CARD_VERSION = "0.7.0";

const I18N = {
  en: {
    default_title: "MindClip recordings",
    select_entry: "Select a MindClip in the card settings.",
    empty: "No recordings found.",
    refresh: "Refresh recordings",
    summary: "Summary",
    transcript: "Transcript",
    hide: "Hide",
    unavailable: "Available after transcription completes",
    loading: "Loading private content…",
    failed: "Could not load this content.",
    retry: "Try again",
    atmosphere: "Atmosphere",
    todos: "Extracted To-Dos",
    template: "Formatted notes",
    speakers: "Speakers",
    no_summary: "No summary text was returned.",
    no_transcript: "No transcript text was returned.",
    shown: (shown, total) => `${shown} of ${total}`,
    duration: (value) => value,
    statuses: {
      0: "Not transcribed",
      1: "In progress",
      2: "Ready",
      3: "Failed",
      4: "Timed out",
      5: "Speech-to-text failed",
    },
    f_config_entry_id: "MindClip",
    f_title: "Card title",
    f_limit: "Number of recent recordings",
    f_enable_summary: "Allow loading summaries",
    f_enable_transcript: "Allow loading transcripts",
  },
  hr: {
    default_title: "MindClip snimke",
    select_entry: "Odaberite MindClip u postavkama kartice.",
    empty: "Nema pronađenih snimki.",
    refresh: "Osvježi snimke",
    summary: "Sažetak",
    transcript: "Transkript",
    hide: "Sakrij",
    unavailable: "Dostupno nakon dovršetka transkripcije",
    loading: "Učitavanje privatnog sadržaja…",
    failed: "Sadržaj nije moguće učitati.",
    retry: "Pokušaj ponovno",
    atmosphere: "Atmosfera",
    todos: "Izdvojeni zadaci",
    template: "Oblikovane bilješke",
    speakers: "Govornici",
    no_summary: "Nije vraćen tekst sažetka.",
    no_transcript: "Nije vraćen tekst transkripta.",
    shown: (shown, total) => `${shown} od ${total}`,
    duration: (value) => value,
    statuses: {
      0: "Nije transkribirano",
      1: "U tijeku",
      2: "Spremno",
      3: "Neuspješno",
      4: "Isteklo vrijeme",
      5: "Pretvaranje govora nije uspjelo",
    },
    f_config_entry_id: "MindClip",
    f_title: "Naslov kartice",
    f_limit: "Broj posljednjih snimki",
    f_enable_summary: "Omogući dohvat sažetaka",
    f_enable_transcript: "Omogući dohvat transkripata",
  },
};

const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[char],
  );

class MindClipCard extends HTMLElement {
  static getConfigForm() {
    const language = (
      document.querySelector("home-assistant")?.hass?.locale?.language || "en"
    ).slice(0, 2);
    const translations = I18N[language] || I18N.en;
    return {
      schema: [
        {
          name: "config_entry_id",
          required: true,
          selector: { config_entry: { integration: "mindclip" } },
        },
        { name: "title", selector: { text: {} } },
        {
          name: "limit",
          selector: { number: { min: 1, max: 50, mode: "box" } },
        },
        { name: "enable_summary", selector: { boolean: {} } },
        { name: "enable_transcript", selector: { boolean: {} } },
      ],
      computeLabel: (schema) => translations[`f_${schema.name}`],
    };
  }

  static getStubConfig() {
    return { limit: 10, enable_summary: true, enable_transcript: false };
  }

  setConfig(config) {
    if (!config || typeof config !== "object") {
      throw new Error("Invalid MindClip card configuration");
    }
    const limit = Number(config.limit ?? 10);
    this._config = {
      ...config,
      limit: Number.isFinite(limit) ? Math.min(50, Math.max(1, limit)) : 10,
      enable_summary: config.enable_summary !== false,
      enable_transcript: config.enable_transcript === true,
    };
    this._recordings = null;
    this._total = 0;
    this._more = false;
    this._error = null;
    this._loading = false;
    this._details = new Map();
    this._listRequest = (this._listRequest || 0) + 1;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    if (this._hass && this.isConnected) this._load();
  }

  set hass(hass) {
    const first = !this._hass;
    const connectionChanged = this._hass?.connection !== hass.connection;
    this._hass = hass;
    if ((first || connectionChanged) && this._config && this.isConnected) this._load();
  }

  connectedCallback() {
    if (this._hass && this._config && this._recordings === null) this._load();
  }

  disconnectedCallback() {
    this._listRequest = (this._listRequest || 0) + 1;
    for (const detail of this._details?.values() || []) detail.request += 1;
    this._details?.clear();
  }

  getCardSize() {
    return Math.min(12, Math.max(3, (this._recordings?.length || 3) + 1));
  }

  getGridOptions() {
    return { columns: 12, rows: "auto", min_columns: 6 };
  }

  get _t() {
    const language = (this._hass?.locale?.language || "en").slice(0, 2);
    return I18N[language] || I18N.en;
  }

  async _call(service, data) {
    const result = await this._hass.callWS({
      type: "call_service",
      domain: "mindclip",
      service,
      service_data: data,
      return_response: true,
    });
    return result.response;
  }

  async _load() {
    if (!this._hass || !this._config) return;
    if (!this._config.config_entry_id) {
      this._recordings = [];
      this._error = null;
      this._render();
      return;
    }
    this._loading = true;
    const request = (this._listRequest || 0) + 1;
    this._listRequest = request;
    this._error = null;
    this._render();
    try {
      const response = await this._call("list_recordings", {
        config_entry_id: this._config.config_entry_id,
        limit: this._config.limit,
      });
      if (request !== this._listRequest) return;
      this._recordings = response.recordings || [];
      this._total = response.total || 0;
      this._more = response.more === true;
      const currentIds = new Set(this._recordings.map((item) => item.recording_id));
      for (const id of this._details.keys()) {
        if (!currentIds.has(id)) this._details.delete(id);
      }
    } catch (error) {
      if (request !== this._listRequest) return;
      this._error = error;
    } finally {
      if (request !== this._listRequest) return;
      this._loading = false;
      this._render();
    }
  }

  _detail(recordingId) {
    if (!this._details.has(recordingId)) {
      this._details.set(recordingId, {
        open: null,
        loading: null,
        error: null,
        summary: null,
        transcript: null,
        request: 0,
      });
    }
    return this._details.get(recordingId);
  }

  async _toggle(recordingId, kind) {
    const detail = this._detail(recordingId);
    if (detail.open === kind) {
      detail.open = null;
      detail.error = null;
      this._render();
      return;
    }
    detail.open = kind;
    detail.error = null;
    if (detail[kind]) {
      this._render();
      return;
    }
    detail.loading = kind;
    const request = detail.request + 1;
    detail.request = request;
    this._render();
    try {
      const response = await this._call(
        kind === "summary" ? "get_summary" : "get_transcript",
        {
          config_entry_id: this._config.config_entry_id,
          recording_id: recordingId,
        },
      );
      if (!this.isConnected || detail.request !== request) return;
      detail[kind] = response;
    } catch (error) {
      if (!this.isConnected || detail.request !== request) return;
      detail.error = error;
    } finally {
      if (!this.isConnected || detail.request !== request) return;
      detail.loading = null;
      this._render();
    }
  }

  _date(timestamp) {
    return new Date(timestamp).toLocaleString(
      this._hass?.locale?.language || undefined,
      {
        weekday: "short",
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      },
    );
  }

  _duration(seconds) {
    const value = Math.max(0, Number(seconds) || 0);
    const hours = Math.floor(value / 3600);
    const minutes = Math.floor((value % 3600) / 60);
    const remainder = Math.floor(value % 60);
    if (hours) return `${hours}:${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
    return `${minutes}:${String(remainder).padStart(2, "0")}`;
  }

  _statusClass(status) {
    if (status === 2) return "ready";
    if (status === 1) return "working";
    if (status >= 3) return "failed";
    return "waiting";
  }

  _summaryContent(summary) {
    const t = this._t;
    const todos = (summary.todos || [])
      .map(
        (todo) => `<li class="todo${todo.is_completed ? " done" : ""}">
          <ha-icon icon="${todo.is_completed ? "mdi:check-circle" : "mdi:checkbox-blank-circle-outline"}"></ha-icon>
          <span>${esc(todo.title)}</span>
        </li>`,
      )
      .join("");
    const speakers = (summary.speakers || [])
      .map((speaker) => speaker.speaker_name || speaker.speaker)
      .filter(Boolean)
      .map((name) => `<span class="chip"><ha-icon icon="mdi:account-voice"></ha-icon>${esc(name)}</span>`)
      .join("");
    return `<div class="private-content summary-content">
      <div class="private-heading"><ha-icon icon="mdi:text-box-check-outline"></ha-icon>${t.summary}</div>
      <div class="summary-text">${esc(summary.summary || t.no_summary)}</div>
      ${summary.atmosphere ? `<div class="atmosphere"><span>${t.atmosphere}</span>${esc(summary.atmosphere)}</div>` : ""}
      ${todos ? `<div class="subheading">${t.todos}</div><ul class="todos">${todos}</ul>` : ""}
      ${speakers ? `<div class="subheading">${t.speakers}</div><div class="chips">${speakers}</div>` : ""}
      ${summary.template ? `<details><summary>${t.template}</summary><div class="template-text">${esc(summary.template)}</div></details>` : ""}
    </div>`;
  }

  _transcriptContent(transcript) {
    const t = this._t;
    const speakers = (transcript.speakers || [])
      .map((speaker) => speaker.speaker_name || speaker.speaker)
      .filter(Boolean)
      .map((name) => `<span class="chip"><ha-icon icon="mdi:account-voice"></ha-icon>${esc(name)}</span>`)
      .join("");
    return `<div class="private-content">
      <div class="private-heading"><ha-icon icon="mdi:text-box-search-outline"></ha-icon>${t.transcript}</div>
      ${speakers ? `<div class="chips">${speakers}</div>` : ""}
      <div class="transcript-text">${esc(transcript.transcription || t.no_transcript)}</div>
    </div>`;
  }

  _expanded(recording) {
    const t = this._t;
    const detail = this._detail(recording.recording_id);
    if (!detail.open) return "";
    if (detail.loading === detail.open) {
      return `<div class="private-content loading-content"><span class="spinner"></span>${t.loading}</div>`;
    }
    if (detail.error) {
      return `<div class="private-content error-content">
        <ha-icon icon="mdi:alert-circle-outline"></ha-icon>
        <span>${esc(detail.error.message || t.failed)}</span>
        <button class="text-button" data-retry="${esc(recording.recording_id)}" data-kind="${detail.open}">${t.retry}</button>
      </div>`;
    }
    return detail.open === "summary"
      ? this._summaryContent(detail.summary || {})
      : this._transcriptContent(detail.transcript || {});
  }

  _row(recording) {
    const t = this._t;
    const detail = this._detail(recording.recording_id);
    const ready = recording.transcription_status === 2;
    const buttons = [];
    if (this._config.enable_summary) {
      buttons.push(`<button class="action-button${detail.open === "summary" ? " active" : ""}" data-id="${esc(recording.recording_id)}" data-kind="summary" ${ready ? "" : "disabled"} title="${ready ? t.summary : t.unavailable}">
        <ha-icon icon="mdi:text-box-check-outline"></ha-icon>${detail.open === "summary" ? t.hide : t.summary}
      </button>`);
    }
    if (this._config.enable_transcript) {
      buttons.push(`<button class="action-button${detail.open === "transcript" ? " active" : ""}" data-id="${esc(recording.recording_id)}" data-kind="transcript" ${ready ? "" : "disabled"} title="${ready ? t.transcript : t.unavailable}">
        <ha-icon icon="mdi:text-box-search-outline"></ha-icon>${detail.open === "transcript" ? t.hide : t.transcript}
      </button>`);
    }
    const statusClass = this._statusClass(recording.transcription_status);
    return `<article class="recording ${detail.open ? "expanded" : ""}">
      <div class="recording-main">
        <div class="recording-icon ${statusClass}"><ha-icon icon="mdi:waveform"></ha-icon></div>
        <div class="recording-copy">
          <div class="recording-title">${esc(recording.title)}</div>
          <div class="recording-meta">
            <span><ha-icon icon="mdi:calendar-clock"></ha-icon>${esc(this._date(recording.created_time))}</span>
            <span><ha-icon icon="mdi:timer-outline"></ha-icon>${esc(this._duration(recording.recording_length))}</span>
          </div>
        </div>
        <span class="status ${statusClass}">${esc(t.statuses[recording.transcription_status] || recording.transcription_status)}</span>
      </div>
      ${buttons.length ? `<div class="actions">${buttons.join("")}</div>` : ""}
      ${this._expanded(recording)}
    </article>`;
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    const t = this._t;
    let body = "";
    if (!this._config.config_entry_id) {
      body = `<div class="empty"><ha-icon icon="mdi:devices"></ha-icon>${t.select_entry}</div>`;
    } else if (this._loading && !this._recordings) {
      body = Array.from(
        { length: Math.min(3, this._config.limit) },
        () => `<div class="skeleton"><span></span><div><b></b><i></i></div></div>`,
      ).join("");
    } else if (this._error) {
      body = `<div class="empty error"><ha-icon icon="mdi:cloud-alert-outline"></ha-icon>${esc(this._error.message || t.failed)}</div>`;
    } else if (this._recordings && !this._recordings.length) {
      body = `<div class="empty"><ha-icon icon="mdi:waveform"></ha-icon>${t.empty}</div>`;
    } else {
      body = (this._recordings || []).map((recording) => this._row(recording)).join("");
    }

    const title = this._config.title || t.default_title;
    const count = this._recordings
      ? t.shown(this._recordings.length, this._total || this._recordings.length)
      : "";
    this.shadowRoot.innerHTML = `<style>
      :host { display: block; }
      ha-card { overflow: hidden; }
      .card-header { display: flex; align-items: center; gap: 12px; padding: 18px 18px 14px;
        background: linear-gradient(135deg, color-mix(in srgb, var(--primary-color) 12%, transparent), transparent 70%); }
      .hero-icon { width: 42px; height: 42px; border-radius: 14px; display: grid; place-items: center; flex: none;
        color: var(--text-primary-color, white); background: linear-gradient(135deg, var(--primary-color), var(--accent-color, var(--primary-color)));
        box-shadow: 0 8px 20px color-mix(in srgb, var(--primary-color) 28%, transparent); }
      .hero-icon ha-icon { --mdc-icon-size: 24px; }
      .header-copy { flex: 1; min-width: 0; }
      .card-title { color: var(--primary-text-color); font-size: 19px; line-height: 1.25; font-weight: 650; overflow-wrap: anywhere; }
      .card-count { color: var(--secondary-text-color); font-size: 12px; margin-top: 3px; }
      .refresh { width: 38px; height: 38px; border: 0; border-radius: 50%; display: grid; place-items: center; cursor: pointer;
        color: var(--secondary-text-color); background: color-mix(in srgb, var(--card-background-color) 82%, var(--primary-color) 18%); }
      .refresh:hover { color: var(--primary-color); transform: rotate(12deg); }
      .refresh:disabled { opacity: .45; cursor: wait; }
      .refresh ha-icon { --mdc-icon-size: 21px; }
      .list { display: flex; flex-direction: column; gap: 10px; padding: 4px 14px 16px; }
      .recording { border: 1px solid var(--divider-color); border-radius: 16px; background: var(--card-background-color);
        transition: border-color .18s ease, box-shadow .18s ease, transform .18s ease; overflow: hidden; }
      .recording:hover { border-color: color-mix(in srgb, var(--primary-color) 38%, var(--divider-color));
        box-shadow: 0 7px 22px rgba(0,0,0,.08); transform: translateY(-1px); }
      .recording.expanded { border-color: color-mix(in srgb, var(--primary-color) 55%, var(--divider-color)); }
      .recording-main { display: flex; align-items: center; gap: 12px; padding: 13px 14px 10px; }
      .recording-icon { width: 38px; height: 38px; border-radius: 12px; display: grid; place-items: center; flex: none; }
      .recording-icon ha-icon { --mdc-icon-size: 21px; }
      .recording-icon.ready { color: var(--success-color, #2e9d62); background: color-mix(in srgb, var(--success-color, #2e9d62) 14%, transparent); }
      .recording-icon.working { color: var(--warning-color, #f0a020); background: color-mix(in srgb, var(--warning-color, #f0a020) 14%, transparent); }
      .recording-icon.failed { color: var(--error-color); background: color-mix(in srgb, var(--error-color) 12%, transparent); }
      .recording-icon.waiting { color: var(--secondary-text-color); background: var(--secondary-background-color); }
      .recording-copy { flex: 1; min-width: 0; }
      .recording-title { color: var(--primary-text-color); font-size: 15px; font-weight: 650; line-height: 1.3; overflow-wrap: anywhere; }
      .recording-meta { display: flex; flex-wrap: wrap; gap: 5px 12px; margin-top: 5px; color: var(--secondary-text-color); font-size: 12px; }
      .recording-meta span { display: inline-flex; align-items: center; gap: 4px; }
      .recording-meta ha-icon { --mdc-icon-size: 14px; }
      .status { flex: none; max-width: 120px; padding: 4px 9px; border-radius: 999px; font-size: 10px; line-height: 1.2; font-weight: 700;
        text-align: center; text-transform: uppercase; letter-spacing: .035em; }
      .status.ready { color: var(--success-color, #2e9d62); background: color-mix(in srgb, var(--success-color, #2e9d62) 12%, transparent); }
      .status.working { color: var(--warning-color, #c77e00); background: color-mix(in srgb, var(--warning-color, #f0a020) 13%, transparent); }
      .status.failed { color: var(--error-color); background: color-mix(in srgb, var(--error-color) 11%, transparent); }
      .status.waiting { color: var(--secondary-text-color); background: var(--secondary-background-color); }
      .actions { display: flex; flex-wrap: wrap; gap: 8px; padding: 0 14px 13px 64px; }
      .action-button, .text-button { border: 1px solid var(--divider-color); background: var(--secondary-background-color); color: var(--primary-text-color);
        border-radius: 999px; font: inherit; font-size: 12px; font-weight: 650; cursor: pointer; }
      .action-button { display: inline-flex; align-items: center; gap: 6px; padding: 6px 11px; }
      .action-button ha-icon { --mdc-icon-size: 17px; color: var(--primary-color); }
      .action-button:hover, .action-button.active { border-color: var(--primary-color); color: var(--primary-color);
        background: color-mix(in srgb, var(--primary-color) 9%, var(--card-background-color)); }
      .action-button:disabled { opacity: .4; cursor: not-allowed; }
      .private-content { margin: 0 12px 12px; padding: 14px; border-radius: 13px; color: var(--primary-text-color);
        background: color-mix(in srgb, var(--primary-color) 5%, var(--secondary-background-color)); border: 1px solid color-mix(in srgb, var(--primary-color) 18%, var(--divider-color)); }
      .private-heading { display: flex; align-items: center; gap: 7px; margin-bottom: 10px; font-size: 13px; font-weight: 750; color: var(--primary-color); }
      .private-heading ha-icon { --mdc-icon-size: 18px; }
      .summary-text, .template-text, .transcript-text { white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.55; font-size: 14px; }
      .transcript-text { max-height: 380px; overflow: auto; padding-inline-end: 5px; }
      .atmosphere { display: flex; gap: 8px; align-items: baseline; margin-top: 12px; font-size: 13px; }
      .atmosphere span { color: var(--secondary-text-color); font-size: 11px; font-weight: 700; text-transform: uppercase; }
      .subheading { margin-top: 14px; margin-bottom: 7px; color: var(--secondary-text-color); font-size: 11px; font-weight: 750; text-transform: uppercase; letter-spacing: .04em; }
      .todos { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 7px; }
      .todo { display: flex; align-items: flex-start; gap: 7px; font-size: 13px; }
      .todo ha-icon { --mdc-icon-size: 17px; color: var(--primary-color); flex: none; margin-top: 1px; }
      .todo.done { opacity: .6; text-decoration: line-through; }
      .chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 7px 0; }
      .chip { display: inline-flex; align-items: center; gap: 4px; border-radius: 999px; padding: 4px 8px; font-size: 11px;
        background: var(--card-background-color); border: 1px solid var(--divider-color); }
      .chip ha-icon { --mdc-icon-size: 14px; color: var(--primary-color); }
      details { margin-top: 13px; border-top: 1px solid var(--divider-color); padding-top: 10px; }
      details summary { cursor: pointer; color: var(--secondary-text-color); font-size: 12px; font-weight: 700; }
      .template-text { margin-top: 10px; }
      .loading-content, .error-content { display: flex; align-items: center; justify-content: center; gap: 9px; color: var(--secondary-text-color); font-size: 13px; }
      .error-content ha-icon { color: var(--error-color); --mdc-icon-size: 19px; }
      .text-button { padding: 5px 9px; color: var(--primary-color); }
      .spinner { width: 16px; height: 16px; border: 2px solid var(--divider-color); border-top-color: var(--primary-color); border-radius: 50%; animation: spin .8s linear infinite; }
      .empty { min-height: 92px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 9px;
        padding: 16px; text-align: center; color: var(--secondary-text-color); font-size: 13px; }
      .empty ha-icon { --mdc-icon-size: 30px; color: var(--primary-color); opacity: .75; }
      .empty.error ha-icon { color: var(--error-color); }
      .skeleton { display: flex; align-items: center; gap: 12px; height: 62px; padding: 0 14px; border: 1px solid var(--divider-color); border-radius: 16px; }
      .skeleton > span, .skeleton b, .skeleton i { display: block; background: linear-gradient(90deg, var(--secondary-background-color), color-mix(in srgb, var(--primary-color) 9%, var(--secondary-background-color)), var(--secondary-background-color));
        background-size: 200% 100%; animation: shimmer 1.4s infinite; }
      .skeleton > span { width: 38px; height: 38px; border-radius: 12px; }
      .skeleton > div { flex: 1; }
      .skeleton b { width: 55%; height: 12px; border-radius: 6px; }
      .skeleton i { width: 38%; height: 9px; border-radius: 5px; margin-top: 8px; }
      @keyframes spin { to { transform: rotate(360deg); } }
      @keyframes shimmer { to { background-position: -200% 0; } }
      @media (max-width: 520px) {
        .card-header { padding: 15px 14px 12px; }
        .list { padding-inline: 10px; }
        .recording-main { align-items: flex-start; gap: 10px; padding-inline: 11px; }
        .recording-icon { width: 34px; height: 34px; border-radius: 10px; }
        .status { max-width: 88px; font-size: 9px; }
        .actions { padding-inline-start: 55px; padding-inline-end: 10px; }
        .private-content { margin-inline: 9px; }
      }
    </style>
    <ha-card>
      <header class="card-header">
        <div class="hero-icon"><ha-icon icon="mdi:microphone-message"></ha-icon></div>
        <div class="header-copy"><div class="card-title">${esc(title)}</div>${count ? `<div class="card-count">${esc(count)}${this._more ? "+" : ""}</div>` : ""}</div>
        <button class="refresh" title="${t.refresh}" aria-label="${t.refresh}" ${this._loading || !this._config.config_entry_id ? "disabled" : ""}><ha-icon icon="mdi:refresh"></ha-icon></button>
      </header>
      <div class="list">${body}</div>
    </ha-card>`;

    this.shadowRoot.querySelector(".refresh")?.addEventListener("click", () => this._load());
    this.shadowRoot.querySelectorAll("button[data-id]").forEach((button) => {
      button.addEventListener("click", () => this._toggle(button.dataset.id, button.dataset.kind));
    });
    this.shadowRoot.querySelectorAll("button[data-retry]").forEach((button) => {
      button.addEventListener("click", () => {
        const detail = this._detail(button.dataset.retry);
        detail[button.dataset.kind] = null;
        detail.error = null;
        detail.open = null;
        this._toggle(button.dataset.retry, button.dataset.kind);
      });
    });
  }
}

if (!customElements.get("mindclip-card")) {
  customElements.define("mindclip-card", MindClipCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "mindclip-card")) {
  window.customCards.push({
    type: "mindclip-card",
    name: "MindClip recordings",
    description: "Recent MindClip recordings with private summaries and transcripts on demand.",
    documentationURL: "https://github.com/BeardedTinker/ha-mindclip",
  });
}

console.info(
  `%c MINDCLIP-CARD %c ${CARD_VERSION} `,
  "background:#6750a4;color:#fff;border-radius:4px 0 0 4px;padding:2px 6px",
  "background:#eee;color:#333;border-radius:0 4px 4px 0;padding:2px 6px",
);
