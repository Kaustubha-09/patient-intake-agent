# patient-intake-agent — Interview Talking Points

**LLM drives, tools own the data.** This is the most important architectural decision. The LLM's job is conversation: warmth, clarification, intent. The tools' job is facts: this address is real, this provider exists, this slot is available. If you let the LLM "validate" an address by reasoning about it, it will confidently produce wrong outputs. By exposing `validate_address` as a tool that hits Google Maps, the validation is auditable and the LLM is forced to call it. Same logic for provider ranking — the LLM doesn't *decide* which provider to recommend; it *requests* a ranking and presents the result.

**Two-layer emergency gate.** The system prompt tells the LLM: classify chest pain / breathing difficulty / stroke / consciousness loss as emergency and short-circuit to 911. The tool layer reinforces this: `_rank_providers(urgency="emergency")` returns an empty list. Even if the LLM somehow continues past the 911 prompt (jailbreak, confusion, edge phrasing), the tool layer refuses to schedule. **Safety-critical decisions need two layers minimum.**

**Demo mode that exercises the same code.** `--demo` hand-rolls the conversational text — *but it calls the same `_validate_address` and `_rank_providers` functions as the real agent.* This is the difference between a "demo" that lies about what the system does and a demo that actually reproduces the production code path. Reviewers see real behavior; bugs in tools show up in both modes.

**Single-file `main.py`.** ~24 KB. ~12 functions. The project is one terminal flow with one set of tools. Splitting into a `package/__init__.py` + `agent.py` + `tools.py` + `cli.py` would be ceremony, not clarity, at this scope. When the project grows past ~500 lines or gets a second surface (web, voice), the function boundaries are already clean enough to refactor in a day.

**The honest scope.** This is a workflow demo, not a clinical triage tool. The triage rules aren't clinically validated. The audit log is plaintext on local disk, not HIPAA-grade. The providers are mocks, not a real EHR integration. I documented all of this in [limitations.md](docs/limitations.md). The point of a portfolio project is to demonstrate engineering judgment, not to overclaim a regulatory pathway.


