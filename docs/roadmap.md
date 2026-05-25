# Roadmap

## Phase 1 — Robustness (1 week)

- Retry with exponential backoff on transient OpenAI errors (429, 503).
- Max-turns counter to bound cost on runaway conversations.
- Tool-call schema validation — reject malformed calls instead of crashing the dispatcher.
- Structured logging via `structlog` JSON output.

## Phase 2 — Surfaces (2 weeks)

- **Web UI** — FastAPI backend with WebSocket streaming + a minimal React/Streamlit chat UI.
- **SMS** — Twilio integration so patients can intake via text message.
- **Voice** — Twilio Voice + Whisper for transcription, Eleven Labs for TTS.

Each surface uses the same tool layer; the only thing that changes is the I/O.

## Phase 3 — Real scheduling integration (1–2 weeks)

- Replace `MOCK_PROVIDERS` / `MOCK_SLOTS` with calls into a clinic scheduling API (Athena, Cerner, Epic FHIR endpoints).
- Tool schemas stay the same; the provider-ranking + slot-fetch logic moves behind a real HTTP boundary.

## Phase 4 — Multilingual (1 week)

- System prompt + slot-confirmation strings i18n'd.
- Spanish, Mandarin, Hindi as initial languages.
- LLM auto-detects patient language from first input.

## Phase 5 — Confidence + escalation (1 week)

- LLM reports a confidence score on the triage classification (HIGH / MEDIUM / LOW).
- LOW-confidence cases route to a human nurse review queue rather than auto-scheduling.

## Phase 6 — Compliance harness (research)

- HIPAA-aligned audit log (tamper-evident, encrypted at rest).
- PII redaction in non-PHI logging contexts (metrics, dashboards).
- BAA-ready cloud deployment (Azure Health Data Services, AWS HealthLake).

## Out of scope

- **Replacing nurse triage.** Augment, don't replace.
- **Direct billing / payment.** Different domain.
- **Clinical decision support for ongoing care.** This is intake, not chronic-care management.
