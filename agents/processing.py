"""
Processing Agent (the intelligence layer)
Uses Claude (primary) with Gemini fallback to triage emails, extract action items,
draft replies, and produce a structured DailyBriefing.
"""

import json
from datetime import datetime
from typing import Any, Dict, List

import anthropic

from models import (
    ActionItem,
    CalendarEvent,
    DailyBriefing,
    Email,
    EmailCategory,
    ProcessedEmail,
    Urgency,
)
import config

# Anthropic error types that indicate quota exhaustion → trigger Gemini fallback
_QUOTA_ERRORS = (
    anthropic.RateLimitError,
    anthropic.APIStatusError,
)


def _is_quota_error(exc: Exception) -> bool:
    if isinstance(exc, anthropic.RateLimitError):
        return True
    if isinstance(exc, anthropic.APIStatusError) and exc.status_code in (429, 529):
        return True
    # Credit balance exhausted (400 with specific message)
    if isinstance(exc, anthropic.BadRequestError) and "credit balance" in str(exc).lower():
        return True
    return False




class ProcessingAgent:
    """
    Analyzes raw emails and calendar events and produces a DailyBriefing.
    Tries Anthropic first; automatically falls back to Gemini on quota errors.
    """

    # Anthropic tool definitions
    _ANTHROPIC_TOOLS = [
        {
            "name": "save_email_analysis",
            "description": (
                "Save the triage result for every email. "
                "Call once with the full list — don't call per-email."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "processed_emails": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "email_id": {"type": "string"},
                                "subject": {"type": "string"},
                                "sender": {"type": "string"},
                                "urgency": {"type": "string", "enum": ["high", "medium", "low"]},
                                "category": {"type": "string", "enum": ["action_required", "meeting_request", "fyi", "newsletter", "other"]},
                                "action_items": {"type": "array", "items": {"type": "string"}},
                                "draft_reply": {"type": "string"},
                                "summary": {"type": "string"},
                            },
                            "required": ["email_id", "subject", "sender", "urgency", "category", "summary"],
                        },
                    }
                },
                "required": ["processed_emails"],
            },
        },
        {
            "name": "save_action_items",
            "description": (
                "Save all action items extracted from emails AND calendar events. "
                "Include prep tasks for upcoming meetings."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "action_items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                                "source_type": {"type": "string", "enum": ["email", "calendar"]},
                                "source_id": {"type": "string"},
                                "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                                "due_date": {"type": "string"},
                            },
                            "required": ["title", "description", "source_type", "source_id", "priority"],
                        },
                    }
                },
                "required": ["action_items"],
            },
        },
        {
            "name": "save_executive_summary",
            "description": (
                "Save the final executive summary. "
                "2-3 crisp paragraphs — what needs attention NOW, "
                "what requires prep, what decisions are pending."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
            },
        },
    ]

    def __init__(self):
        self._reset_state()

    def _reset_state(self):
        self._processed_emails: List[ProcessedEmail] = []
        self._action_items: List[ActionItem] = []
        self._summary: str = ""

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, emails: List[Email], events: List[CalendarEvent]) -> DailyBriefing:
        print(f"[ProcessingAgent] Analyzing {len(emails)} emails and {len(events)} events...")
        try:
            return self._run_with_anthropic(emails, events)
        except Exception as exc:
            if _is_quota_error(exc) or isinstance(exc, anthropic.AuthenticationError):
                reason = "auth error" if isinstance(exc, anthropic.AuthenticationError) else "quota hit"
                print(f"[ProcessingAgent] Anthropic {reason} — switching to Ollama")
                self._reset_state()
                return self._run_with_ollama(emails, events)
            raise

    # ------------------------------------------------------------------
    # Anthropic implementation
    # ------------------------------------------------------------------

    def _run_with_anthropic(self, emails: List[Email], events: List[CalendarEvent]) -> DailyBriefing:
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        messages = [{"role": "user", "content": self._build_prompt(emails, events)}]

        while True:
            response = client.messages.create(
                model=config.MODEL,
                max_tokens=config.MAX_TOKENS,
                thinking={"type": "adaptive"},
                tools=self._ANTHROPIC_TOOLS,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                break

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = self._execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        })
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

        return self._build_briefing(events)

    # ------------------------------------------------------------------
    # Gemini implementation
    # ------------------------------------------------------------------

    # Groq tool definitions (OpenAI format)
    _GROQ_TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "save_email_analysis",
                "description": "Save the triage result for every email. Call once with the full list — don't call per-email.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "processed_emails": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "email_id": {"type": "string"},
                                    "subject": {"type": "string"},
                                    "sender": {"type": "string"},
                                    "urgency": {"type": "string"},
                                    "category": {"type": "string"},
                                    "action_items": {"type": "array", "items": {"type": "string"}},
                                    "draft_reply": {"type": "string"},
                                    "summary": {"type": "string"},
                                },
                                "required": ["email_id", "subject", "sender", "urgency", "category", "summary"],
                            },
                        }
                    },
                    "required": ["processed_emails"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "save_action_items",
                "description": "Save all action items from emails AND calendar events, including meeting prep tasks.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action_items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "description": {"type": "string"},
                                    "source_type": {"type": "string"},
                                    "source_id": {"type": "string"},
                                    "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                                    "due_date": {"type": "string"},
                                },
                                "required": ["title", "description", "source_type", "source_id", "priority"],
                            },
                        }
                    },
                    "required": ["action_items"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "save_executive_summary",
                "description": "Save the final 2-3 paragraph executive summary for the CEO.",
                "parameters": {
                    "type": "object",
                    "properties": {"summary": {"type": "string"}},
                    "required": ["summary"],
                },
            },
        },
    ]

    def _run_with_ollama(self, emails: List[Email], events: List[CalendarEvent]) -> DailyBriefing:
        from openai import OpenAI

        client = OpenAI(base_url=config.OLLAMA_BASE_URL, api_key="ollama")
        today = datetime.now().strftime("%Y-%m-%d")

        emails_payload = [
            {
                "id": e.id,
                "subject": e.subject,
                "sender": e.sender,
                "body": e.body[:150] + ("…" if len(e.body) > 150 else ""),
            }
            for e in emails
        ]
        events_payload = [
            {"id": ev.id, "title": ev.title, "start": ev.start.isoformat()}
            for ev in events
        ]

        prompt = f"""For each email below, return a JSON array with only "email_id", "subject", and "urgency" (high/medium/low). No markdown, no explanation, only the JSON array.

Example: [{{"email_id":"123","subject":"Hello","urgency":"low"}}]

EMAILS:
{json.dumps(emails_payload)}"""

        response = client.chat.completions.create(
            model=config.OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            extra_body={"num_ctx": 8192},
        )

        raw = response.choices[0].message.content.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw[raw.index("{"):]
        if raw.endswith("```"):
            raw = raw[:raw.rindex("}") + 1]

        # Expect a JSON array of {email_id, subject, urgency}
        data = json.loads(raw)
        if isinstance(data, list):
            processed = [
                {
                    "email_id": item.get("email_id", ""),
                    "subject": item.get("subject", ""),
                    "sender": next((e.sender for e in emails if e.id == item.get("email_id")), ""),
                    "urgency": item.get("urgency", "low"),
                    "category": "other",
                    "summary": item.get("subject", ""),
                    "action_items": [],
                    "draft_reply": "",
                }
                for item in data
            ]
            self._execute_tool("save_email_analysis", {"processed_emails": processed})

        return self._build_briefing(events)

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _build_prompt(self, emails: List[Email], events: List[CalendarEvent]) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        emails_payload = [
            {
                "id": e.id,
                "subject": e.subject,
                "sender": f"{e.sender} <{e.sender_email}>",
                "body": e.body[:300] + ("…" if len(e.body) > 300 else ""),
                "timestamp": e.timestamp.isoformat(),
                "labels": e.labels,
            }
            for e in emails
        ]
        events_payload = [
            {
                "id": ev.id,
                "title": ev.title,
                "start": ev.start.isoformat(),
                "end": ev.end.isoformat(),
                "attendees": ev.attendees,
                "description": ev.description,
                "location": ev.location,
            }
            for ev in events
        ]
        return (
            f"You are the AI Chief of Staff for a startup CEO. Today is {today}.\n\n"
            f"EMAILS TO TRIAGE:\n{json.dumps(emails_payload, indent=2)}\n\n"
            f"UPCOMING CALENDAR EVENTS:\n{json.dumps(events_payload, indent=2)}\n\n"
            "Please:\n"
            "1. Call save_email_analysis — triage every email (urgency, category, "
            "action items, draft reply for action_required/meeting_request emails).\n"
            "2. Call save_action_items — extract ALL action items from emails AND "
            "calendar events (include meeting prep tasks).\n"
            "3. Call save_executive_summary — 2-3 paragraph summary the CEO reads "
            "first thing: what needs immediate attention, decisions pending, prep required."
        )

    def _build_briefing(self, events: List[CalendarEvent]) -> DailyBriefing:
        today = datetime.now().strftime("%Y-%m-%d")
        print(
            f"[ProcessingAgent] Done — {len(self._processed_emails)} emails processed, "
            f"{len(self._action_items)} action items"
        )
        return DailyBriefing(
            date=today,
            processed_emails=self._processed_emails,
            upcoming_events=events,
            action_items=self._action_items,
            executive_summary=self._summary,
        )

    # Map non-standard category strings the model may produce → valid EmailCategory values
    _CATEGORY_MAP = {
        "updates": "fyi", "update": "fyi", "transactional": "fyi",
        "finance": "fyi", "social": "fyi", "shopping": "fyi",
        "travel": "fyi", "work": "action_required", "promo": "newsletter",
        "promotional": "newsletter", "marketing": "newsletter",
        "personal": "fyi", "spam": "newsletter",
    }

    def _execute_tool(self, name: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        if name == "save_email_analysis":
            saved = 0
            for item in input_data.get("processed_emails", []):
                try:
                    raw_cat = item["category"].lower()
                    cat = self._CATEGORY_MAP.get(raw_cat, raw_cat)
                    try:
                        email_cat = EmailCategory(cat)
                    except ValueError:
                        email_cat = EmailCategory.OTHER
                    self._processed_emails.append(ProcessedEmail(
                        email_id=item["email_id"],
                        subject=item["subject"],
                        sender=item["sender"],
                        urgency=Urgency(item["urgency"].lower()),
                        category=email_cat,
                        action_items=item.get("action_items", []),
                        draft_reply=item.get("draft_reply"),
                        summary=item["summary"],
                    ))
                    saved += 1
                except Exception as e:
                    print(f"[ProcessingAgent] Skipping email {item.get('email_id')}: {e}")
            return {"saved": saved}

        if name == "save_action_items":
            saved = 0
            for item in input_data.get("action_items", []):
                try:
                    self._action_items.append(ActionItem(
                        title=item["title"],
                        description=item["description"],
                        source_type=item["source_type"].lower(),
                        source_id=item["source_id"],
                        priority=Urgency(item["priority"].lower()),
                        due_date=item.get("due_date"),
                    ))
                    saved += 1
                except Exception as e:
                    print(f"[ProcessingAgent] Skipping action item '{item.get('title')}': {e}")
            return {"saved": saved}

        if name == "save_executive_summary":
            self._summary = input_data.get("summary", "")
            return {"saved": True}

        return {"error": f"Unknown tool: {name}"}
