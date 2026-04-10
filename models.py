from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class Urgency(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EmailCategory(str, Enum):
    ACTION_REQUIRED = "action_required"
    MEETING_REQUEST = "meeting_request"
    FYI = "fyi"
    NEWSLETTER = "newsletter"
    OTHER = "other"


class Email(BaseModel):
    id: str
    subject: str
    sender: str
    sender_email: str
    body: str
    timestamp: datetime
    labels: List[str] = Field(default_factory=list)


class CalendarEvent(BaseModel):
    id: str
    title: str
    start: datetime
    end: datetime
    attendees: List[str] = Field(default_factory=list)
    description: str = ""
    location: str = ""
    is_all_day: bool = False


class ProcessedEmail(BaseModel):
    email_id: str
    subject: str
    sender: str
    urgency: Urgency
    category: EmailCategory
    action_items: List[str] = Field(default_factory=list)
    draft_reply: Optional[str] = None
    summary: str = ""


class ActionItem(BaseModel):
    title: str
    description: str
    source_type: str  # "email" or "calendar"
    source_id: str
    priority: Urgency
    due_date: Optional[str] = None  # ISO date string


class DailyBriefing(BaseModel):
    date: str  # YYYY-MM-DD
    processed_emails: List[ProcessedEmail] = Field(default_factory=list)
    upcoming_events: List[CalendarEvent] = Field(default_factory=list)
    action_items: List[ActionItem] = Field(default_factory=list)
    executive_summary: str = ""
