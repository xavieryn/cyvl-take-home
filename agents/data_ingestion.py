"""
Data Ingestion Agent
Fetches real emails and calendar events via the Google API Python client.
Requires token.json (created by scripts/auth_google.py).
Only used when --live flag is passed to main.py.
"""

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from models import Email, CalendarEvent
import config

TOKEN_PATH = Path(__file__).parent.parent / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def _get_credentials() -> Credentials:
    if not TOKEN_PATH.exists():
        raise FileNotFoundError(
            f"token.json not found. Run: python scripts/auth_google.py"
        )
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())
    return creds


class DataIngestionAgent:
    """Fetches real data from Gmail and Google Calendar via the Google API client."""

    def run(self) -> Tuple[List[Email], List[CalendarEvent]]:
        creds = _get_credentials()
        emails = self._fetch_emails(creds)
        events = self._fetch_calendar_events(creds)
        print(
            f"[DataIngestionAgent] Fetched {len(emails)} emails "
            f"and {len(events)} calendar events"
        )
        return emails, events

    # ------------------------------------------------------------------
    # Gmail
    # ------------------------------------------------------------------

    def _fetch_emails(self, creds: Credentials) -> List[Email]:
        service = build("gmail", "v1", credentials=creds)
        result = (
            service.users()
            .messages()
            .list(
                userId="me",
                maxResults=config.MAX_EMAILS,
                # Exclude calendar invite notifications; focus on real emails
                q="in:inbox -subject:Invitation: -subject:\"Updated invitation\" -subject:\"Canceled event\"",
            )
            .execute()
        )
        emails = []
        for ref in result.get("messages", []):
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=ref["id"], format="full")
                .execute()
            )
            email = self._parse_message(msg)
            if email:
                emails.append(email)
        return emails

    def _parse_message(self, msg: dict) -> Optional[Email]:
        try:
            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
            body = self._extract_body(msg["payload"])
            timestamp = datetime.fromtimestamp(
                int(msg["internalDate"]) / 1000, tz=timezone.utc
            )
            raw_from = headers.get("From", "Unknown <unknown@unknown.com>")
            if "<" in raw_from:
                sender_name = raw_from.split("<")[0].strip().strip('"')
                sender_email = raw_from.split("<")[-1].strip(">").strip()
            else:
                sender_name = raw_from
                sender_email = raw_from

            return Email(
                id=msg["id"],
                subject=headers.get("Subject", "(no subject)"),
                sender=sender_name,
                sender_email=sender_email,
                body=body,
                timestamp=timestamp,
                labels=msg.get("labelIds", []),
            )
        except Exception as e:
            print(f"[DataIngestionAgent] Could not parse email: {e}")
            return None

    def _extract_body(self, payload: dict) -> str:
        if "parts" in payload:
            for part in payload["parts"]:
                if part["mimeType"] == "text/plain":
                    data = part["body"].get("data", "")
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                if "parts" in part:
                    result = self._extract_body(part)
                    if result:
                        return result
        elif payload.get("mimeType") == "text/plain":
            data = payload["body"].get("data", "")
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        return ""

    # ------------------------------------------------------------------
    # Google Calendar
    # ------------------------------------------------------------------

    def _fetch_calendar_events(self, creds: Credentials) -> List[CalendarEvent]:
        service = build("calendar", "v3", credentials=creds)
        now = datetime.now(tz=timezone.utc)
        end = now + timedelta(days=config.CALENDAR_DAYS_AHEAD)

        result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now.isoformat(),
                timeMax=end.isoformat(),
                maxResults=25,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = []
        for item in result.get("items", []):
            event = self._parse_event(item)
            if event:
                events.append(event)
        return events

    def _parse_event(self, item: dict) -> Optional[CalendarEvent]:
        try:
            start_raw = item["start"]
            end_raw = item["end"]
            is_all_day = "date" in start_raw

            start = datetime.fromisoformat(
                start_raw["date"] if is_all_day else start_raw["dateTime"]
            )
            end = datetime.fromisoformat(
                end_raw["date"] if is_all_day else end_raw["dateTime"]
            )

            attendees = [
                a.get("email", "")
                for a in item.get("attendees", [])
                if a.get("responseStatus") != "declined"
            ]

            return CalendarEvent(
                id=item["id"],
                title=item.get("summary", "(no title)"),
                start=start,
                end=end,
                attendees=attendees,
                description=item.get("description", ""),
                location=item.get("location", ""),
                is_all_day=is_all_day,
            )
        except Exception as e:
            print(f"[DataIngestionAgent] Could not parse event: {e}")
            return None
