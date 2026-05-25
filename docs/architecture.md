# Architecture

A single-file (`main.py`) terminal agent: GPT-4o drives the conversation, deterministic Python tools handle the data-bearing operations, and every session is appended to an audit log.

## Layer diagram

```
       ┌───────────────────────────────────────────┐
       │           main.py (CLI loop)              │
       │  argparse · ANSI styling · _setup_logger  │
       └─────────────────┬─────────────────────────┘
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
  ┌───────────────────┐      ┌──────────────────┐
  │   run_agent()     │      │   run_demo()     │
  │   GPT-4o + tools  │      │   scripted flow  │
  └────────┬──────────┘      └──────────────────┘
           │
           │ tool_calls (OpenAI function calling)
           ▼
  ┌───────────────────────────────────────────┐
  │  _resolve_tool_calls() / _dispatch_tool() │
  │   ├─ validate_address  → Google Maps API  │
  │   └─ rank_providers    → urgency policy   │
  └───────────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │     intake.log       │
              │  per-session audit   │
              │  trail (gitignored)  │
              └──────────────────────┘
```

## The contract — LLM drives, tools own the data

The system prompt walks the patient through:

1. Name + address (street, city, state, zip)
2. Symptoms + urgency classification (emergency / urgent / routine)
3. Provider ranking (deterministic, by urgency)
4. Slot selection
5. Confirmation + audit-log close-out

**The LLM never invents an address, a provider, or a slot.** When it needs validated data, it issues a `tool_calls[]` entry; the dispatch layer runs the real Python function (Google Maps or in-memory provider table), formats the result, and feeds it back into the chat history. The LLM then composes the user-facing response *based on* that result.

## Tools

| Tool | Implementation | Purpose |
|---|---|---|
| `validate_address` | `requests.get` against Google Maps Geocoding API | Returns `{valid: bool, formatted_address: str}`. Catches typos, normalizes formatting. |
| `rank_providers` | In-memory ordering over `MOCK_PROVIDERS` | Orders by urgency: urgent → Internal Medicine first; routine → Primary Care / Family Medicine first. Emergency → returns empty (escalation gate). |

Tool schemas are passed to `client.chat.completions.create(... tools=[...])`. The OpenAI client returns structured `tool_calls[]` entries; we dispatch each via `_dispatch_tool()` and append the result back to `messages[]` for the next round-trip.

## Triage classification

| Class | Trigger words / phrases | Outcome |
|---|---|---|
| **Emergency** | chest pain, can't breathe, stroke, loss of consciousness, severe bleeding, suicidal | Immediate 911 redirect. No scheduling. Log status `ended (emergency)`. |
| **Urgent** | high fever, persistent vomiting, signs of infection, severe pain | Internal Medicine first; earliest available slot auto-selected. |
| **Routine** | annual check-up, mild cold, prescription refill, general wellness | Primary Care / Family Medicine first; patient chooses slot. |

Emergency classification is a **gate**, not a recommendation — the agent terminates the booking flow entirely. The `rank_providers` tool returns no providers for emergency urgencies, so even if the LLM tried to schedule, it would fail.

## Mock providers + slots

```python
MOCK_PROVIDERS = [
    {"id": "P001", "name": "Dr. Sarah Chen",   "specialty": "Primary Care"},
    {"id": "P002", "name": "Dr. James Rivera", "specialty": "Family Medicine"},
    {"id": "P003", "name": "Dr. Priya Patel",  "specialty": "Internal Medicine"},
]
MOCK_SLOTS: dict[str, list[dict]] = { ... }  # 3 slots per provider, next 5 days
```

In a real deployment these would be backed by a clinic scheduling system; the agent's logic doesn't change.

## Audit logging

`_setup_logger()` configures a `logging.FileHandler` on `intake.log` with a custom formatter:

```
2026-04-19 10:30:00  ─── SESSION START ───────────────────────────────────
2026-04-19 10:30:01  [AGENT]  Could you please provide your full name?
2026-04-19 10:30:05  [USER]   Jane Doe
2026-04-19 10:30:06  [TOOL CALL]   validate_address | {"address": "..."}
2026-04-19 10:30:06  [TOOL RESULT] validate_address | {"valid": true, ...}
2026-04-19 10:30:10  ─── SESSION END (completed) ──────────────────────────
```

Every agent message, user input, tool call, and tool result is captured. Terminal status (`completed` / `emergency` / `abandoned`) closes each session block. The log is **gitignored** — per-session contents may include user input that should not be checked in.

## Demo mode

`python main.py --demo` runs a scripted flow with no API calls. The conversation is hand-rolled to demonstrate the routine and emergency branches; address validation uses a fixed positive response; provider ranking uses the same in-memory function. Reviewers can see the full UX without an OpenAI or Google Maps key.

## What runs where

| Concern | Lives in (`main.py`) |
|---|---|
| CLI entry point | `__main__` block + `argparse.ArgumentParser` |
| Logging setup | `_setup_logger()` |
| ANSI-styled console output | `_say()`, color constants |
| LLM call | `_chat()` → `client.chat.completions.create(...)` |
| Tool dispatch | `_resolve_tool_calls()`, `_dispatch_tool()` |
| Address validation | `_validate_address()` (Google Maps Geocoding) |
| Provider ranking | `_rank_providers()` |
| Demo flow | `run_demo()` |
| Real-agent flow | `run_agent()` + `_agent_turn()` |
| Session summary | `_print_summary()` |
