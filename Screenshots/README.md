# Patient Intake Agent — Screenshots

Terminal session captures (asciinema-style or `⌘⇧4` screen grabs from iTerm2 / Terminal).

| # | File | Surface |
|---|------|---------|
| 01 | `01_agent_run.png` | Full LLM agent run — intro, name, address validation, slot offering |
| 02 | `02_routine_scheduling.png` | Routine triage path — Primary Care selection, slot pick, confirmation |
| 03 | `03_emergency_escalation.png` | Emergency path — chest pain → 911 redirect, no scheduling |
| 04 | `04_demo_mode.png` | `--demo` mode without API keys |

To capture: run `poetry run python main.py` (or `--demo`), take a terminal screenshot, drop in this folder with the index prefix.
