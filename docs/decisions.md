# Architecture Decision Records

Append-only.

## ADR-001 · LLM drives the conversation, tools own the data

**Date:** 2026-04
**Status:** Accepted

The system prompt orchestrates the conversation, but every data-bearing operation goes through a deterministic Python function exposed as an OpenAI tool: `validate_address` (Google Maps) and `rank_providers` (in-memory).

**Why:** the LLM is good at language, bad at facts. Asking GPT-4o to "validate" an address would produce confidently wrong outputs. Asking it to "rank" providers would produce different orderings on every run. Tool calls move those decisions into Python.

**Cost:** more code than "just call the LLM". Acceptable — the resulting system is auditable, repeatable, and won't hallucinate a provider that doesn't exist.

---

## ADR-002 · Emergency is a hard gate, not a recommendation

**Date:** 2026-04
**Status:** Accepted

If the LLM classifies symptoms as emergency, the agent prints a 911 directive and ends the session. The `rank_providers` tool returns an empty list for emergency urgencies.

**Why:** triage decisions affect human safety. The escalation path needs to be unbypassable. Even if the LLM somehow continued past the 911 prompt, the tool layer would refuse to schedule. Two layers because one layer alone could fail.

---

## ADR-003 · Demo mode that needs no API keys

**Date:** 2026-04
**Status:** Accepted

`python main.py --demo` runs a scripted flow with hand-rolled responses; no `OPENAI_API_KEY`, no `GOOGLE_MAPS_API_KEY`, no network.

**Why:** anyone reviewing the project (recruiter, interviewer, you in three months) should be able to see the UX without spinning up two API keys + paying for tokens. The demo exercises the same branches (routine, emergency) as the real agent.

---

## ADR-004 · Single-file `main.py` instead of a package

**Date:** 2026-04
**Status:** Accepted

All code lives in `main.py` — ~24 KB, ~12 top-level functions, no submodules.

**Why:** the project is one terminal flow with one set of tools. Splitting into `tools.py` / `agents.py` / `cli.py` would be 4 files instead of 1, with no payoff at this scope. When the project grows past ~500 lines or adds a second surface (web API, voice), a refactor is cheap because the function boundaries are already clean.

---

## ADR-005 · `intake.log` is gitignored, not committed

**Date:** 2026-04
**Status:** Accepted

Per-session audit log is written to `intake.log` and excluded from version control.

**Why:** session contents may include patient PII (name, address, symptoms). Even on a demo, committing those bytes would set the wrong precedent. The log format is documented; rebuild on first run.

---

## ADR-006 · Google Maps Geocoding for address validation

**Date:** 2026-04
**Status:** Accepted

`_validate_address()` calls `https://maps.googleapis.com/maps/api/geocode/json?address=...`.

**Why:** Google Maps Geocoding is the cheapest way to (a) verify an address exists, (b) get a normalized form for the audit log. Alternatives (USPS API for US-only, OpenStreetMap Nominatim with rate-limiting) trade quality for cost. Google has the broadest coverage and a generous free tier.

**Cost:** vendor dependency. Mitigated by isolating the call to one function; swapping for another geocoding service is a one-function change.

---

## ADR-007 · Mock providers + slots, not a real EHR integration

**Date:** 2026-04
**Status:** Accepted, demo-grade

3 providers, 3 slots each, all in-memory in `MOCK_PROVIDERS` / `MOCK_SLOTS`.

**Why:** real EHR integrations are HIPAA-bound, partner-specific, and out of scope for a demo. The agent's logic doesn't care whether the provider list comes from in-memory data or an HL7 FHIR endpoint — the contract is `{id, name, specialty, location}` per provider and `{slot_id, datetime}` per slot.

**Production swap:** replace `MOCK_PROVIDERS` / `MOCK_SLOTS` with a function that hits the clinic's scheduling API. Tool schemas don't change.

---

## ADR-008 · ANSI-styled CLI

**Date:** 2026-04
**Status:** Accepted

The terminal output uses raw ANSI escape codes (`\033[96m` etc.) for color, not a library like `rich` or `colorama`.

**Why:** five colors and a bold style fit in 10 lines of constants. `rich` would add a 400 KB dependency for what we use in 10 lines. The tradeoff is no fancy progress bars or Markdown rendering — fine for this surface.

---

## ADR-009 · `--demo` and agent share the same tool layer

**Date:** 2026-04
**Status:** Accepted

`run_demo()` calls the *same* `_validate_address` and `_rank_providers` functions as `run_agent()` — it just hand-rolls the conversational text instead of calling the LLM.

**Why:** if the tools change behavior, both modes should change together. Two parallel implementations would diverge — demo would lie about what the agent does.

**Cost:** demo mode hits Google Maps (real API call) unless the user has the env var unset, in which case the address validation falls back to a fixed positive response. Acceptable trade.
