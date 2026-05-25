# Limitations

Honest scope for a single-file terminal agent.

## Scope

- **Terminal-only.** No voice, no SMS, no web UI. Real intake systems would have all three.
- **3 mock providers, 3 mock slots each.** Not a real scheduling system.
- **Mock urgency rules.** Triage classification is by keywords in the LLM's reasoning; not clinically validated.
- **English-only.** No multilingual support.
- **No accessibility audit.** ANSI styling is fine for sighted users; screen-reader compatibility unverified.

## Safety / clinical

- **Not a clinical triage tool.** The agent gives a 911 directive on emergency keywords, but the classification is LLM-driven and not certified. Use as a workflow demo, not as clinical decision support.
- **No HIPAA compliance.** Audit log writes to local disk in plaintext. Real PHI handling requires encryption at rest, access controls, audit-log tamper-evidence, BAAs with cloud providers.
- **No PII redaction.** User-provided names, addresses, and symptoms are logged verbatim.

## LLM dependency

- **GPT-4o is required for agent mode.** No graceful degradation to a smaller / cheaper model.
- **No retry on transient OpenAI errors.** A 503 surfaces as a crashed session.
- **No structured output validation.** We trust the LLM to follow the tool-call schema. Malformed tool calls would crash `_dispatch_tool()` rather than degrade gracefully.
- **Token cost is not bounded.** A long conversation could rack up cost. No max-turns counter.

## Operational

- **Single-process.** No concurrency. One terminal = one session.
- **No durable state across sessions.** Each run starts from scratch.
- **No alerting.** A session ending in `emergency` doesn't notify staff.
- **No metrics.** Time-to-complete, drop-off rate, classification confusion matrix are all unmeasured.

## Demo mode

- **Demo flow is one specific path.** Routine scheduling + one emergency variant. Doesn't cover all branches.
- **Demo still calls Google Maps** for address validation unless `GOOGLE_MAPS_API_KEY` is unset, in which case it falls back to a fixed positive response. Pure offline demo requires unsetting the env var.

## What's needed to ship for real

1. Clinical validation of the triage rules by qualified medical personnel.
2. HIPAA-compliant infrastructure (encrypted storage, BAAs, access controls).
3. Real EHR / scheduling-system integration.
4. Multilingual support.
5. Voice + SMS surfaces (most patients don't intake via terminal).
6. Liability insurance.
7. Regulatory pathway (FDA Class II SaMD or equivalent).

This is a workflow demo. The honest gap to clinical deployment is significant.
