"""
Data Ingestion Agent
Fetches real emails and calendar events from Gmail and Google Calendar via OAuth2.
Only used when --live flag is passed to main.py.
"""

import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from models import Email, CalendarEvent
import config

# Google API libraries — graceful error if not installed
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    _GOOGLE_AVAILABLE = True
except ImportError:
    _GOOGLE_AVAILABLE = False

_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]


class DataIngestionAgent:
    """Fetches real data from Gmail and Google Calendar."""

    def __init__(self):
        self._gmail = None
        self._calendar = None

    def run(self) -> Tuple[List[Email], List[CalendarEvent]]:
        if not _GOOGLE_AVAILABLE:
            raise ImportError(
                "Google API libraries are not installed.\n"
                "Run: pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client"
            )
        self._authenticate()
        emails = self._fetch_emails()
        events = self._fetch_calendar_events()
        print(
            f"[DataIngestionAgent] Fetched {len(emails)} emails "
            f"and {len(events)} calendar events"
        )
        return emails, events

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _authenticate(self):
        """OAuth2 flow — opens browser on first run, reuses token.json after."""
        creds = None
        token_path = Path(config.GOOGLE_TOKEN_PATH)

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), _SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    config.GOOGLE_CREDENTIALS_PATH, _SCOPES
                )
                creds = flow.run_local_server(port=0)

            token_path.write_text(creds.to_json())

        self._gmail = build("gmail", "v1", credentials=creds)
        self._calendar = build("calendar", "v3", credentials=creds)

    # ------------------------------------------------------------------
    # Gmail
    # ------------------------------------------------------------------

    def _fetch_emails(self) -> List[Email]:
        results = (
            self._gmail.users()
            .messages()
            .list(userId="me", maxResults=config.MAX_EMAILS, q="in:inbox is:unread")
            .execute()
        )
        emails = []
        for ref in results.get("messages", []):
            msg = (
                self._gmail.users()
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
            # Parse "Name <email>" format
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
        """Return plain-text body from a Gmail message payload."""
        if "parts" in payload:
            for part in payload["parts"]:
                if part["mimeType"] == "text/plain":
                    data = part["body"].get("data", "")
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                # Recurse into nested multipart
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

    def _fetch_calendar_events(self) -> List[CalendarEvent]:
        now = datetime.now(tz=timezone.utc)
        end = now + timedelta(days=config.CALENDAR_DAYS_AHEAD)

        result = (
            self._calendar.events()
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
