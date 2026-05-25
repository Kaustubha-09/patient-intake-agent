"""
Clinic Co. — Patient Intake & Scheduling Agent

Usage:
  python main.py           # LLM-powered agent (requires API keys in .env)
  python main.py --demo    # demo mode, no API keys needed
"""

import argparse
import json
import logging
import os
import time
from datetime import date, timedelta

import requests
from dotenv import load_dotenv
from openai import OpenAI

# ── ANSI colors ────────────────────────────────────────────────────────────────
CYAN   = "\033[96m"
WHITE  = "\033[97m"
YELLOW = "\033[93m"
GREEN  = "\033[92m"
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"

# ── Mock data ──────────────────────────────────────────────────────────────────
_today = date.today()

MOCK_PROVIDERS = [
    {"id": "P001", "name": "Dr. Sarah Chen",   "specialty": "Primary Care",      "location": "Downtown Clinic"},
    {"id": "P002", "name": "Dr. James Rivera", "specialty": "Family Medicine",   "location": "Westside Medical Center"},
    {"id": "P003", "name": "Dr. Priya Patel",  "specialty": "Internal Medicine", "location": "Eastpark Health"},
]

MOCK_SLOTS: dict[str, list[dict]] = {
    "P001": [
        {"slot_id": "S1", "datetime": f"{_today + timedelta(days=3)} 9:00 AM"},
        {"slot_id": "S2", "datetime": f"{_today + timedelta(days=3)} 10:30 AM"},
        {"slot_id": "S3", "datetime": f"{_today + timedelta(days=4)} 2:00 PM"},
    ],
    "P002": [
        {"slot_id": "S4", "datetime": f"{_today + timedelta(days=2)} 11:00 AM"},
        {"slot_id": "S5", "datetime": f"{_today + timedelta(days=4)} 9:30 AM"},
        {"slot_id": "S6", "datetime": f"{_today + timedelta(days=5)} 3:30 PM"},
    ],
    "P003": [
        {"slot_id": "S7", "datetime": f"{_today + timedelta(days=2)} 10:00 AM"},
        {"slot_id": "S8", "datetime": f"{_today + timedelta(days=5)} 1:00 PM"},
        {"slot_id": "S9", "datetime": f"{_today + timedelta(days=6)} 4:00 PM"},
    ],
}

# ── System prompt ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a warm, professional patient intake and scheduling assistant for Clinic Co..
Walk the patient through the following steps in order — never skip ahead.

  Collect: full name, date of birth, insurance payer (all required), and insurance member ID (optional).
  Make clear that the insurance ID is optional.

  Ask what brings the patient in today (their chief complaint / reason for visit).

  After the chief complaint is confirmed, ask three focused follow-up questions one at a time:
    a. Duration  — how long have they been experiencing it?
    b. Severity  — is it mild, moderate, or severe? (offer these three choices)
    c. Location  — where exactly on the body is the symptom?
  Confirm each answer before moving to the next question.

  Once all symptom details are collected, call classify_urgency with one of:
    "routine"   — symptoms are non-urgent; standard scheduling is appropriate.
    "urgent"    — symptoms need attention soon but are not immediately life-threatening.
    "emergency" — symptoms suggest a potentially life-threatening condition.
  Use clinical judgement based on the chief complaint, duration, severity, and location.
  Examples that should be "emergency": chest pain, difficulty breathing, stroke symptoms,
    severe abdominal pain, uncontrolled bleeding, loss of consciousness.

  After calling classify_urgency:
  - If "emergency": IMMEDIATELY warn the patient in clear, urgent language to call 911 or
      go to the nearest emergency room right away. Do NOT continue scheduling. End the conversation.
  - If "urgent" or "routine": briefly inform the patient of the urgency level and continue.

  Ask for the patient's home address.
  Call validate_address with exactly what they provide.
  - If the result shows valid=true: confirm the formatted address back to the patient and move on.
  - If valid=false: apologise briefly and ask them to re-enter their address.

  Call get_available_providers passing the urgency level from Step 4.
  The result returns providers ranked by specialty match, with a "recommended" flag on the best fit:
    - urgent:  Internal Medicine is ranked first. Recommend that provider to the patient
               ("Given your urgency level, I recommend Dr. X — would you like to go with them?")
               and use their choice to proceed.
    - routine: Primary Care / Family Medicine are ranked first. Present all options numbered 1-N
               and let the patient choose freely.

  Call get_available_slots passing the chosen provider's id AND the urgency level.
    - urgent:  The result contains one slot: the earliest available, already auto-selected.
               Inform the patient: "Given the urgency I've booked you into the earliest slot: [datetime]."
               Do NOT ask them to choose — move straight to confirmation.
    - routine: Present all returned slots numbered 1-N and ask the patient to pick one.

  Summarise all collected details and ask the patient to confirm ("Does everything look correct?").
  Only when they confirm (yes / looks good / correct / etc.), call save_appointment with every field.

General guidelines:
- Be conversational; never recite a list of questions at once.
- Confirm each piece of information back to the patient as you collect it.
- Convert date of birth to YYYY-MM-DD before passing to save_appointment.
- Use the formatted_address returned by validate_address as the address in save_appointment.
- Always use exact provider names, IDs, and datetimes as returned by tool calls — never invent or paraphrase them.
- Do not collect or ask about anything beyond what is listed above.
"""

# ── Tool schemas ───────────────────────────────────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "validate_address",
            "description": "Validate and standardise a patient-provided address via Google Maps. Always call this before accepting an address.",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "The raw address string the patient provided."}
                },
                "required": ["address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_available_providers",
            "description": (
                "Return providers ranked by specialty match for the given urgency level. "
                "Always pass the urgency level so results are appropriately ordered."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "urgency": {
                        "type": "string",
                        "enum": ["routine", "urgent"],
                        "description": "Urgency level from classify_urgency.",
                    }
                },
                "required": ["urgency"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_available_slots",
            "description": (
                "Return appointment slots for a provider. "
                "For urgent cases returns only the earliest slot (auto-selected). "
                "For routine returns all available slots."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "provider_id": {"type": "string", "description": "The id of the chosen provider."},
                    "urgency": {
                        "type": "string",
                        "enum": ["routine", "urgent"],
                        "description": "Urgency level from classify_urgency.",
                    },
                },
                "required": ["provider_id", "urgency"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "classify_urgency",
            "description": (
                "Record the urgency level after all symptom details have been collected. "
                "Call this before proceeding to address or provider selection."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "urgency": {
                        "type": "string",
                        "enum": ["routine", "urgent", "emergency"],
                        "description": "Urgency level based on the patient's symptoms.",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Brief clinical reasoning for the chosen urgency level.",
                    },
                },
                "required": ["urgency", "reasoning"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_appointment",
            "description": "Save the complete appointment after the patient has explicitly confirmed all details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "full_name":            {"type": "string"},
                    "date_of_birth":        {"type": "string", "description": "YYYY-MM-DD"},
                    "insurance_payer":      {"type": "string"},
                    "insurance_id":         {"type": "string", "description": "Optional — omit or leave empty if not provided."},
                    "chief_complaint":      {"type": "string"},
                    "symptom_duration":     {"type": "string", "description": "How long the patient has had the symptom."},
                    "symptom_severity":     {"type": "string", "enum": ["mild", "moderate", "severe"]},
                    "symptom_location":     {"type": "string", "description": "Body location of the symptom."},
                    "urgency":              {"type": "string", "enum": ["routine", "urgent"]},
                    "address":              {"type": "string", "description": "Validated formatted address from validate_address."},
                    "provider_id":          {"type": "string"},
                    "provider_name":        {"type": "string"},
                    "appointment_datetime": {"type": "string"},
                },
                "required": [
                    "full_name", "date_of_birth", "insurance_payer",
                    "chief_complaint", "symptom_duration", "symptom_severity",
                    "symptom_location", "urgency", "address",
                    "provider_id", "provider_name", "appointment_datetime",
                ],
            },
        },
    },
]

# ── Shared UI helpers ──────────────────────────────────────────────────────────
def _say(message: str, delay: float = 0.0) -> None:
    print(f"\n{CYAN}{BOLD}Agent:{RESET} {WHITE}{message}{RESET}")
    if delay:
        time.sleep(delay)


def _ask(prompt: str = "You: ") -> str:
    print(f"\n{YELLOW}{prompt}{RESET}", end="")
    return input().strip()


def _print_summary(info: dict) -> None:
    width = 52
    print(f"\n{GREEN}{'=' * width}")
    print("          APPOINTMENT CONFIRMATION SUMMARY")
    print(f"{'=' * width}{RESET}")
    fields = [
        ("Patient Name",     info.get("full_name", "N/A")),
        ("Date of Birth",    info.get("date_of_birth", "N/A")),
        ("Insurance Payer",  info.get("insurance_payer", "N/A")),
        ("Insurance ID",     info.get("insurance_id") or "Not provided"),
        ("Chief Complaint",  info.get("chief_complaint", "N/A")),
        ("Symptom Duration", info.get("symptom_duration", "N/A")),
        ("Symptom Severity", info.get("symptom_severity", "N/A")),
        ("Symptom Location", info.get("symptom_location", "N/A")),
        ("Urgency",          info.get("urgency", "N/A")),
        ("Address",          info.get("address", "N/A")),
        ("Provider",         info.get("provider_name", "N/A")),
        ("Appointment",      info.get("appointment_datetime", "N/A")),
    ]
    for label, value in fields:
        print(f"  {BOLD}{label:<20}{RESET}: {value}")
    print(f"{GREEN}{'=' * width}{RESET}\n")

# ── Tool implementations ───────────────────────────────────────────────────────
_URGENT_SPECIALTIES  = {"internal medicine"}
_ROUTINE_SPECIALTIES = {"primary care", "family medicine", "general practice"}


def _validate_address(address: str) -> dict:
    try:
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"address": address, "key": os.getenv("GOOGLE_MAPS_API_KEY")},
            timeout=6,
        )
        data = resp.json()
        if data.get("status") == "OK":
            return {"valid": True, "formatted_address": data["results"][0]["formatted_address"]}
        if data.get("status") == "ZERO_RESULTS":
            return {"valid": False, "error": "Address not found. Please check and re-enter."}
        return {"valid": False, "status": data.get("status"), "error": "Address could not be validated."}
    except Exception as exc:
        return {"valid": False, "error": str(exc)}


def _rank_providers(urgency: str) -> list[dict]:
    preferred = _URGENT_SPECIALTIES if urgency == "urgent" else _ROUTINE_SPECIALTIES
    ranked, others = [], []
    for p in MOCK_PROVIDERS:
        entry = {**p, "recommended": p["specialty"].lower() in preferred}
        (ranked if entry["recommended"] else others).append(entry)
    return ranked + others


def _dispatch_tool(name: str, args: dict, logger: logging.Logger) -> str:
    if name == "validate_address":
        result = _validate_address(args["address"])
    elif name == "get_available_providers":
        result = {"providers": _rank_providers(args.get("urgency", "routine"))}
    elif name == "get_available_slots":
        slots = MOCK_SLOTS.get(args.get("provider_id", ""), [])
        result = {"slots": slots[:1], "auto_selected": True} if args.get("urgency") == "urgent" \
            else {"slots": slots, "auto_selected": False}
    elif name == "classify_urgency":
        urgency = args["urgency"]
        result = {
            "urgency": "emergency",
            "action": "end_booking",
            "instruction": (
                "STOP. Do not continue scheduling. Tell the patient clearly and urgently "
                "that they must call 911 or go to the nearest emergency room immediately. "
                "Express care and concern, then end the conversation."
            ),
        } if urgency == "emergency" else {"urgency": urgency, "action": "continue"}
    elif name == "save_appointment":
        _print_summary(args)
        result = {"status": "confirmed", "message": "Appointment booked successfully."}
    else:
        result = {"error": f"Unknown tool: {name}"}

    serialized = json.dumps(result)
    logger.info("[TOOL RESULT] %s | %s", name, serialized)
    return serialized

# ── Session logging ────────────────────────────────────────────────────────────
def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("intake")
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        handler = logging.FileHandler("intake.log", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(handler)
    return logger

# ── Agent mode ─────────────────────────────────────────────────────────────────
def _chat(messages: list, client: OpenAI) -> object:
    return client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
    ).choices[0].message


def _resolve_tool_calls(msg, messages: list, logger: logging.Logger) -> bool:
    done = False
    for tc in msg.tool_calls:
        args = json.loads(tc.function.arguments)
        logger.info("[TOOL CALL]   %s | %s", tc.function.name, json.dumps(args))
        result = _dispatch_tool(tc.function.name, args, logger)
        messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
        if tc.function.name == "save_appointment" or (
            tc.function.name == "classify_urgency" and args.get("urgency") == "emergency"
        ):
            done = True
    return done


def _agent_turn(messages: list, client: OpenAI, logger: logging.Logger) -> bool:
    while True:
        msg = _chat(messages, client)
        messages.append(msg)
        if msg.content:
            _say(msg.content)
            logger.info("[AGENT]  %s", msg.content)
        if not msg.tool_calls:
            return False
        if _resolve_tool_calls(msg, messages, logger):
            closing = _chat(messages, client)
            messages.append(closing)
            if closing.content:
                _say(closing.content)
                logger.info("[AGENT]  %s", closing.content)
            return True


def run_agent() -> None:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        print(f"{YELLOW}Error: OPENAI_API_KEY not set. Create a .env file or run with --demo.{RESET}")
        raise SystemExit(1)

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    logger = _setup_logger()

    print(f"\n{BOLD}{'=' * 52}\n  Clinic Co. — Patient Intake & Scheduling\n{'=' * 52}{RESET}")
    print(f"{DIM}(type 'quit' to exit){RESET}\n")

    logger.info("─── SESSION START ───────────────────────────────────")
    messages: list = [{"role": "system", "content": SYSTEM_PROMPT}]
    _agent_turn(messages, client, logger)

    while True:
        try:
            user_input = _ask()
        except (EOFError, KeyboardInterrupt):
            _say("Session ended. Goodbye!")
            logger.info("─── SESSION END (interrupted) ───────────────────────")
            break
        if not user_input:
            continue
        if user_input.lower() in {"quit", "exit", "bye"}:
            _say("Thank you for visiting Clinic Co.. Goodbye!")
            logger.info("─── SESSION END (user quit) ─────────────────────────")
            break
        logger.info("[USER]   %s", user_input)
        messages.append({"role": "user", "content": user_input})
        if _agent_turn(messages, client, logger):
            logger.info("─── SESSION END (completed) ─────────────────────────")
            break

# ── Demo mode ──────────────────────────────────────────────────────────────────
def run_demo() -> None:
    collected: dict = {}

    print(f"\n{BOLD}{'=' * 52}\n  Clinic Co. — Patient Intake Agent (DEMO)\n{'=' * 52}{RESET}")

    _say(
        "Hello! Thank you for calling Clinic Co.. My name is Alex, "
        "and I'll be helping you schedule your appointment today. "
        "Can I start by getting your full name?",
        delay=0.3,
    )

    collected["full_name"] = _ask()
    _say(f"Nice to meet you, {collected['full_name'].split()[0]}! And could I get your date of birth?", delay=0.3)
    collected["date_of_birth"] = _ask()

    _say("Now let's get your insurance information. What is your insurance provider?", delay=0.3)
    collected["insurance_payer"] = _ask()
    _say("Do you have your insurance ID handy? If not, that's okay — just press Enter to skip.", delay=0.3)
    collected["insurance_id"] = _ask() or None

    _say("What is the reason for your visit today?", delay=0.3)
    collected["chief_complaint"] = _ask()
    _say("I understand. How long have you been experiencing this?", delay=0.3)
    collected["symptom_duration"] = _ask()
    _say("Is the severity mild, moderate, or severe?", delay=0.3)
    collected["symptom_severity"] = _ask()
    _say("And where on your body is the symptom located?", delay=0.3)
    collected["symptom_location"] = _ask()
    _say("Thank you — I'll make sure the physician is aware before your appointment.", delay=0.3)

    _say("I'll also need your home address — street, city, state, and zip.", delay=0.3)
    collected["address"] = _ask()
    _say("Let me verify that address one moment...", delay=0.3)
    time.sleep(1.2)
    if any(ch.isdigit() for ch in collected["address"]):
        _say("Great, I was able to verify your address. Thank you!", delay=0.3)
    else:
        _say(
            "I wasn't able to verify that. Could you double-check and include "
            "the street number, city, state, and zip?",
            delay=0.3,
        )
        collected["address"] = _ask()

    # Build provider+slot list from shared mock data (no duplication)
    providers = [
        {**p, "slots": [s["datetime"] for s in MOCK_SLOTS[p["id"]][:2]]}
        for p in MOCK_PROVIDERS
    ]

    _say("Now let's find you an appointment. Here are our available providers:\n", delay=0.3)
    for i, p in enumerate(providers, 1):
        print(f"  {BOLD}{i}. {p['name']}{RESET} — {p['specialty']}")
        for slot in p["slots"]:
            print(f"       {DIM}• {slot}{RESET}")

    _say("Which provider would you prefer? Please enter 1, 2, or 3.", delay=0.3)
    while True:
        choice = _ask()
        if choice in ("1", "2", "3"):
            provider = providers[int(choice) - 1]
            break
        _say("Please enter 1, 2, or 3.", delay=0.3)

    _say(f"Great choice! {provider['name']} has these times available:", delay=0.3)
    for i, slot in enumerate(provider["slots"], 1):
        print(f"  {i}. {slot}")

    _say("Which time works best for you? Enter 1 or 2.", delay=0.3)
    while True:
        slot_choice = _ask()
        if slot_choice in ("1", "2"):
            collected["provider_name"] = provider["name"]
            collected["appointment_datetime"] = provider["slots"][int(slot_choice) - 1]
            collected["urgency"] = "routine"
            break
        _say("Please enter 1 or 2.", delay=0.3)

    _say("Perfect! Let me read back a summary for you.", delay=0.5)
    _print_summary(collected)

    _say(
        "Your appointment is confirmed! You'll receive a reminder 24 hours before. "
        "Is there anything else I can help you with today?",
        delay=0.3,
    )
    _ask()
    _say("Wonderful. Thank you for choosing Clinic Co.. Have a great day!")

# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clinic Co. Patient Intake Agent")
    parser.add_argument("--demo", action="store_true", help="Run in demo mode (no API keys required)")
    args = parser.parse_args()
    run_demo() if args.demo else run_agent()
