"""
Processing Agent (the missing one)
The intelligence layer between raw data and Obsidian.
Uses Claude to triage emails, extract action items, draft replies,
and produce a structured DailyBriefing.
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


class ProcessingAgent:
    """
    Uses Claude (with adaptive thinking) to analyze raw emails and calendar
    events and produce a fully structured DailyBriefing.
    """

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        # Accumulated state filled in by tool calls
        self._processed_emails: List[ProcessedEmail] = []
        self._action_items: List[ActionItem] = []
        self._summary: str = ""

        self.tools = [
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
                                    "urgency": {
                                        "type": "string",
                                        "enum": ["high", "medium", "low"],
                                    },
                                    "category": {
                                        "type": "string",
                                        "enum": [
                                            "action_required",
                                            "meeting_request",
                                            "fyi",
                                            "newsletter",
                                            "other",
                                        ],
                                    },
                                    "action_items": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "draft_reply": {"type": "string"},
                                    "summary": {"type": "string"},
                                },
                                "required": [
                                    "email_id",
                                    "subject",
                                    "sender",
                                    "urgency",
                                    "category",
                                    "summary",
                                ],
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
                                    "source_type": {
                                        "type": "string",
                                        "enum": ["email", "calendar"],
                                    },
                                    "source_id": {"type": "string"},
                                    "priority": {
                                        "type": "string",
                                        "enum": ["high", "medium", "low"],
                                    },
                                    "due_date": {"type": "string"},
                                },
                                "required": [
                                    "title",
                                    "description",
                                    "source_type",
                                    "source_id",
                                    "priority",
                                ],
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
                    "properties": {
                        "summary": {"type": "string"},
                    },
                    "required": ["summary"],
                },
            },
        ]

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(
        self, emails: List[Email], events: List[CalendarEvent]
    ) -> DailyBriefing:
        print(
            f"[ProcessingAgent] Analyzing {len(emails)} emails "
            f"and {len(events)} events..."
        )

        today = datetime.now().strftime("%Y-%m-%d")

        emails_payload = [
            {
                "id": e.id,
                "subject": e.subject,
                "sender": f"{e.sender} <{e.sender_email}>",
                "body": e.body[:600] + ("…" if len(e.body) > 600 else ""),
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

        messages = [
            {
                "role": "user",
                "content": (
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
                ),
            }
        ]

        while True:
            response = self.client.messages.create(
                model=config.MODEL,
                max_tokens=config.MAX_TOKENS,
                thinking={"type": "adaptive"},
                tools=self.tools,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                break

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = self._execute_tool(block.name, block.input)
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(result),
                            }
                        )
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

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

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    def _execute_tool(
        self, name: str, input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        if name == "save_email_analysis":
            for item in input_data.get("processed_emails", []):
                self._processed_emails.append(
                    ProcessedEmail(
                        email_id=item["email_id"],
                        subject=item["subject"],
                        sender=item["sender"],
                        urgency=Urgency(item["urgency"]),
                        category=EmailCategory(item["category"]),
                        action_items=item.get("action_items", []),
                        draft_reply=item.get("draft_reply"),
                        summary=item["summary"],
                    )
                )
            return {"saved": len(input_data.get("processed_emails", []))}

        elif name == "save_action_items":
            for item in input_data.get("action_items", []):
                self._action_items.append(
                    ActionItem(
                        title=item["title"],
                        description=item["description"],
                        source_type=item["source_type"],
                        source_id=item["source_id"],
                        priority=Urgency(item["priority"]),
                        due_date=item.get("due_date"),
                    )
                )
            return {"saved": len(input_data.get("action_items", []))}

        elif name == "save_executive_summary":
            self._summary = input_data.get("summary", "")
            return {"saved": True}

        return {"error": f"Unknown tool: {name}"}
