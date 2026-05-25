## Prerequisites

- **Python 3.12+**
- **Poetry** ([installation guide](https://python-poetry.org/docs/#installation))
- **OpenAI API key** with access to GPT-4o *(agent mode only)*
- **Google Maps API key** with [Geocoding API](https://console.cloud.google.com/apis/library/geocoding-backend.googleapis.com) enabled *(agent mode only)*

---

## Install

```bash
poetry install
```

---

## Run

**Full LLM agent** (requires API keys):
```bash
cp .env.example .env   # then fill in your keys
poetry run python main.py
```

**Demo mode** (no API keys needed):
```bash
poetry run python main.py --demo
```

---

## Environment variables

```
OPENAI_API_KEY=your-openai-api-key
GOOGLE_MAPS_API_KEY=your-google-maps-api-key
```

The Geocoding API must be explicitly enabled in Google Cloud Console.

---

## Providers & slots

| Provider         | Specialty         | Location                |
|------------------|-------------------|-------------------------|
| Dr. Sarah Chen   | Primary Care      | Downtown Clinic         |
| Dr. James Rivera | Family Medicine   | Westside Medical Center |
| Dr. Priya Patel  | Internal Medicine | Eastpark Health         |

- **Urgent** → Internal Medicine recommended first; earliest slot auto-selected
- **Routine** → Primary Care / Family Medicine first; patient chooses slot

---

## Emergency escalation

If symptoms are classified as **emergency** (chest pain, difficulty breathing, stroke, loss of consciousness, etc.), the agent immediately directs the patient to call 911 and ends the session without scheduling.

---

## Logs

Agent mode appends every session to `intake.log`:

```
2026-04-19 10:30:00  ─── SESSION START ───────────────────────────────────
2026-04-19 10:30:01  [AGENT]  Could you please provide your full name?
2026-04-19 10:30:05  [USER]   Jane Doe
2026-04-19 10:30:06  [TOOL CALL]   validate_address | {"address": "..."}
2026-04-19 10:30:06  [TOOL RESULT] validate_address | {"valid": true, ...}
2026-04-19 10:30:10  ─── SESSION END (completed) ──────────────────────────
```
