# Patient Intake Agent — Portfolio Case Study

A terminal-based AI agent that walks a patient through intake and scheduling, using GPT-4o for conversation and deterministic Python tools for data-bearing operations. Skim time: 3 minutes.

## The brief

Build a working intake agent that:
- conducts a natural conversation
- validates user-provided data through real tool calls (not by trusting the LLM)
- triages urgency
- handles emergency escalation as a hard gate
- writes an audit log
- ships with a demo mode that needs no API keys

## The engineering I'd defend

### 1. LLM drives the conversation; tools own the data

The system prompt orchestrates intake. **Every data-bearing operation** — address validation, provider ranking — goes through a deterministic Python function exposed as an OpenAI tool. The LLM cannot invent an address, hallucinate a provider, or fabricate a slot. The contract is auditable. See [decisions.md, ADR-001](decisions.md#adr-001--llm-drives-the-conversation-tools-own-the-data).

### 2. Emergency escalation is a hard gate, not a recommendation

The LLM is instructed to classify chest pain / breathing difficulty / stroke / consciousness loss as **emergency** and short-circuit to a 911 directive. The `rank_providers` tool also returns an empty list for emergency urgencies — so even if the LLM tried to continue past the 911 prompt, the tool layer refuses to schedule. **Two-layer defense** because one layer alone could fail. See [ADR-002](decisions.md#adr-002--emergency-is-a-hard-gate-not-a-recommendation).

### 3. Demo mode needs no API keys

`python main.py --demo` runs the same flow without OpenAI or Google Maps. Reviewers can see the UX (intro, name capture, address validation, urgency classification, provider selection, slot booking, confirmation) without spinning up keys or paying for tokens. The demo uses the **same tool functions** as the real agent — they cannot diverge. See [ADR-009](decisions.md#adr-009----demo-and-agent-share-the-same-tool-layer).

### 4. Single-file `main.py`

~24 KB. ~12 top-level functions. No submodule sprawl. At this scope, the single file is faster to read top-to-bottom than the equivalent multi-module package would be. When the project grows past ~500 lines or gets a second surface, the function boundaries are clean enough to refactor in a day. See [ADR-004](decisions.md#adr-004--single-file-mainpy-instead-of-a-package).

### 5. `intake.log` for every session, gitignored

Every agent message, user input, tool call, and tool result writes to `intake.log` with timestamps. Session terminal status (`completed` / `emergency` / `abandoned`) closes each block. The log is **gitignored** — per-session contents may include patient input that shouldn't ship. See [ADR-005](decisions.md#adr-005--intakelog-is-gitignored-not-committed).

### 6. Tool seam is the production-swap boundary

`rank_providers` reads from `MOCK_PROVIDERS` / `MOCK_SLOTS` in-memory. A production deployment swaps that for an EHR / scheduling-system API call. The tool schema (`{id, name, specialty, location}` per provider, `{slot_id, datetime}` per slot) doesn't change. See [ADR-007](decisions.md#adr-007--mock-providers--slots-not-a-real-ehr-integration).

## The honest part

- **Not a clinical triage tool.** Demo of the workflow shape, not certified medical decision support.
- **Not HIPAA-compliant.** Audit log is plaintext on local disk; real PHI handling requires more.
- **Mock providers + mock slots.** Real EHR integration is a roadmap item.
- **English-only, terminal-only.** Web/SMS/voice surfaces and i18n are roadmap items.
- **No retries on transient OpenAI errors.** Production hardening is roadmap.

Full gap list in [limitations.md](limitations.md). Phased plan in [roadmap.md](roadmap.md).

## What I'd do next

Phase 2 of the roadmap: add a web surface (FastAPI + WebSocket streaming + a minimal chat UI) using the **same tool layer**. The terminal version is the right baseline because it forces a clean separation between I/O and logic.

## What this signals to a recruiter

- I can build a working LLM-driven agent that uses tool calls for *the things the LLM shouldn't decide alone*.
- I understand layered defense (system-prompt instruction + tool-layer enforcement) for safety-critical branches.
- I write **demo modes** that exercise the same code paths as production — not stubs that lie about what the system does.
- I keep audit logs out of version control because I read the implications, not just the convenience.
- I document ADRs even on a single-file agent. The boundary between LLM-decided and tool-decided is the most important architectural decision; saying it explicitly is the point.
