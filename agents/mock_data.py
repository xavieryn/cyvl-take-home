"""
Mock Data Agent
Generates realistic fake emails and calendar events for development/testing.
No LLM needed — pure Python.
"""

from datetime import datetime, timedelta
from typing import List, Tuple

from models import Email, CalendarEvent


# ---------------------------------------------------------------------------
# Realistic mock email templates
# ---------------------------------------------------------------------------
_EMAIL_TEMPLATES = [
    {
        "subject": "URGENT: Q2 Budget Review — Sign-Off Required by EOD",
        "sender": "Sarah Chen",
        "sender_email": "sarah.chen@investor.com",
        "labels": ["important"],
        "body": (
            "Hi,\n\n"
            "I need your sign-off on the Q2 budget allocation before EOD tomorrow. "
            "The board is waiting on this to proceed with the infrastructure investment.\n\n"
            "Key items pending your approval:\n"
            "  • $2.3M engineering headcount expansion\n"
            "  • $450K new data center lease\n"
            "  • $180K marketing budget increase\n\n"
            "Please review the attached spreadsheet and confirm we can proceed.\n\n"
            "Best,\nSarah"
        ),
    },
    {
        "subject": "Contract Renewal — Somerville Dept. of Public Works",
        "sender": "James Whitmore",
        "sender_email": "j.whitmore@somerville.gov",
        "labels": ["important", "client"],
        "body": (
            "Hi,\n\n"
            "Thanks for the updated contract. Legal has reviewed it and we have two minor "
            "amendments before signing:\n\n"
            "  1. Section 4.2 — data retention period (requesting 3 years → 5 years)\n"
            "  2. Section 7.1 — SLA for emergency response (24h → 12h)\n\n"
            "Can we set up a call early next week? I have Monday and Tuesday open.\n\n"
            "Thanks,\nJames"
        ),
    },
    {
        "subject": "Partnership Proposal — TechCorp Integration",
        "sender": "Mike Rodriguez",
        "sender_email": "mike.r@techcorp.io",
        "labels": [],
        "body": (
            "Hey,\n\n"
            "Following up on our call last week. We'd love to move forward with the integration. "
            "Could we schedule a 30-minute call this week to align on next steps?\n\n"
            "Our team has prepared a technical proposal I think you'll find compelling — "
            "specifically around the ML pipeline and how it maps to your existing data model.\n\n"
            "Let me know your availability.\n\nMike"
        ),
    },
    {
        "subject": "Intro: City of Buffalo — Infrastructure Assessment RFP",
        "sender": "Amanda Foster",
        "sender_email": "a.foster@buffalony.gov",
        "labels": ["lead"],
        "body": (
            "Hello,\n\n"
            "I was connected to you by Tom Hughes at the ASCE conference. "
            "Buffalo is issuing an RFP for an infrastructure condition assessment platform "
            "and your company was recommended as a strong candidate.\n\n"
            "Would you be available for a 20-minute intro call this week or next? "
            "Our deadline for vendor selection is end of this month.\n\n"
            "Best,\nAmanda Foster\nDeputy Director of Public Works, Buffalo, NY"
        ),
    },
    {
        "subject": "Team Lunch Tomorrow — Catering Confirmed",
        "sender": "Office Manager",
        "sender_email": "office@cyvl.com",
        "labels": ["team"],
        "body": (
            "Hi team,\n\n"
            "Just a reminder that we have our monthly team lunch tomorrow at 12:30 PM. "
            "Catering from The Italian Place is confirmed — vegetarian options available.\n\n"
            "No action needed, just show up hungry!\n\n:)"
        ),
    },
    {
        "subject": "Monthly Newsletter — Infrastructure Industry Insights",
        "sender": "InfraWeekly",
        "sender_email": "newsletter@infraweekly.com",
        "labels": ["newsletter"],
        "body": (
            "This month in infrastructure:\n\n"
            "  • Smart city initiatives growing 23% YoY\n"
            "  • New federal funding for road condition monitoring\n"
            "  • Case study: How Nashville saved $4M with predictive maintenance\n\n"
            "Read more at infraweekly.com\n\nUnsubscribe | Manage preferences"
        ),
    },
]

# ---------------------------------------------------------------------------
# Realistic mock calendar event templates
# ---------------------------------------------------------------------------
_EVENT_TEMPLATES = [
    {
        "title": "Daily Standup",
        "hour": 9,
        "duration_hours": 0.25,
        "days_offset": 0,
        "attendees": ["engineering@cyvl.com", "product@cyvl.com"],
        "description": "Daily sync — blockers, priorities, progress.",
        "location": "Zoom",
    },
    {
        "title": "1:1 with CTO",
        "hour": 10,
        "duration_hours": 1.0,
        "days_offset": 0,
        "attendees": ["cto@cyvl.com"],
        "description": "Weekly sync — discuss Q3 roadmap priorities and hiring plan.",
        "location": "Conference Room B",
    },
    {
        "title": "Investor Update Call — Series B",
        "hour": 14,
        "duration_hours": 1.0,
        "days_offset": 1,
        "attendees": ["partners@sequoia.com", "cfo@cyvl.com"],
        "description": "Monthly update. Prep needed: Q2 metrics deck, churn analysis, pipeline summary.",
        "location": "Zoom",
    },
    {
        "title": "Product Demo — Nashville City Council",
        "hour": 11,
        "duration_hours": 1.5,
        "days_offset": 2,
        "attendees": ["council@nashville.gov", "dpw@nashville.gov", "sales@cyvl.com"],
        "description": "Live demo of CYVL infrastructure assessment platform for 3-city expansion.",
        "location": "Nashville City Hall — Rm 204",
    },
    {
        "title": "Board Meeting Prep",
        "hour": 15,
        "duration_hours": 2.0,
        "days_offset": 2,
        "attendees": ["cfo@cyvl.com", "cto@cyvl.com", "vp-sales@cyvl.com"],
        "description": "Prepare Q2 board deck. Assign slide owners, review financials, confirm key messages.",
        "location": "War Room",
    },
]


class MockDataAgent:
    """Generates realistic mock emails and calendar events for dev/testing."""

    def run(self) -> Tuple[List[Email], List[CalendarEvent]]:
        emails = self._generate_emails()
        events = self._generate_calendar_events()
        print(
            f"[MockDataAgent] Generated {len(emails)} emails "
            f"and {len(events)} calendar events"
        )
        return emails, events

    def _generate_emails(self) -> List[Email]:
        now = datetime.now()
        emails = []
        for i, t in enumerate(_EMAIL_TEMPLATES):
            emails.append(
                Email(
                    id=f"mock_email_{i + 1}",
                    subject=t["subject"],
                    sender=t["sender"],
                    sender_email=t["sender_email"],
                    body=t["body"],
                    timestamp=now - timedelta(hours=i * 1.5 + 0.5),
                    labels=t.get("labels", []),
                )
            )
        return emails

    def _generate_calendar_events(self) -> List[CalendarEvent]:
        today = datetime.now().replace(second=0, microsecond=0)
        events = []
        for i, t in enumerate(_EVENT_TEMPLATES):
            start = today.replace(hour=t["hour"], minute=0) + timedelta(
                days=t["days_offset"]
            )
            end = start + timedelta(hours=t["duration_hours"])
            events.append(
                CalendarEvent(
                    id=f"mock_event_{i + 1}",
                    title=t["title"],
                    start=start,
                    end=end,
                    attendees=t.get("attendees", []),
                    description=t.get("description", ""),
                    location=t.get("location", ""),
                )
            )
        return events
