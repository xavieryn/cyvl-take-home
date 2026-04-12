"""
create_demo_events.py
Reads all Calendar template .md files from xtemp/Calendar Templates/ and creates
Google Calendar events via gws on xavier's calendar, with kaisayshi12@gmail.com
as an attendee (Google sends the invite automatically).

Usage:
    python scripts/create_demo_events.py
    python scripts/create_demo_events.py --dry-run
"""

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, date
from pathlib import Path
from zoneinfo import ZoneInfo

TEMPLATES_DIR = Path(__file__).parent.parent / "xtemp" / "Calendar Templates"
INVITE_EMAIL = "kaisayshi12@gmail.com"
CEO_EMAIL = "xavier.nishikawa@gmail.com"
CT = ZoneInfo("America/Chicago")

# Today's date for resolving recurring events
TODAY = date(2026, 4, 11)


# ---------------------------------------------------------------------------
# Date / time parsing helpers
# ---------------------------------------------------------------------------

MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
    "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
}

DAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def next_weekday(target_weekday: int, from_date: date = None) -> date:
    """Return the next occurrence of target_weekday (0=Mon) on or after from_date."""
    base = from_date or TODAY
    days_ahead = target_weekday - base.weekday()
    if days_ahead < 0:
        days_ahead += 7
    return base + timedelta(days=days_ahead)


def parse_date_field(value: str) -> list[date]:
    """
    Parse a **Date:** field value into one or more date objects.
    Returns a list of dates (multiple for conflicts / multi-day).
    """
    value = value.strip()
    v = value.lower()

    # "Weekdays" → next Monday
    if v in ("weekdays", "every weekday", "monday–friday"):
        return [next_weekday(0)]

    # "Every Monday" → next Monday
    for day_name, day_num in DAY_MAP.items():
        if f"every {day_name}" in v:
            return [next_weekday(day_num)]

    # "Every Tuesday & Thursday" → next Tuesday
    m = re.search(r"every (\w+)\s*[&and]+\s*(\w+)", v)
    if m:
        d1 = DAY_MAP.get(m.group(1))
        if d1 is not None:
            return [next_weekday(d1)]

    # "Monday, Wednesday, Friday" → next Monday
    for day_name, day_num in DAY_MAP.items():
        if day_name in v:
            return [next_weekday(day_num)]

    # "April 22–23, 2026"  or  "April 22-23, 2026"
    m = re.search(r"(\w+)\s+(\d+)[–\-](\d+),?\s*(\d{4})", value)
    if m:
        month = MONTH_MAP.get(m.group(1).lower())
        if month:
            d1 = date(int(m.group(4)), month, int(m.group(2)))
            d2 = date(int(m.group(4)), month, int(m.group(3)))
            return [d1, d2]  # multi-day range

    # "April 25, 2026"
    m = re.search(r"(\w+)\s+(\d+),?\s*(\d{4})", value)
    if m:
        month = MONTH_MAP.get(m.group(1).lower())
        if month:
            return [date(int(m.group(3)), month, int(m.group(2)))]

    # "Every Friday" general fallback
    if "friday" in v:
        return [next_weekday(4)]

    return []


def parse_time_field(value: str) -> tuple[str | None, str | None, bool]:
    """
    Parse a **Time:** field.
    Returns (start_iso, end_iso, is_all_day).
    Times returned as HH:MM in 24h, caller adds date and timezone.
    """
    value = value.strip()
    v = value.lower()

    if "all day" in v or v.startswith("all day"):
        return None, None, True

    # "1:00pm – 1:45pm CT"  or  "9:00am – 9:15am CT"
    m = re.search(
        r"(\d{1,2}):(\d{2})\s*(am|pm)\s*[–\-]\s*(\d{1,2}):(\d{2})\s*(am|pm)",
        v,
    )
    if m:
        sh, sm, sa, eh, em, ea = m.groups()
        start_h = _to24(int(sh), int(sm), sa)
        end_h = _to24(int(eh), int(em), ea)
        return start_h, end_h, False

    # "4:30pm – 5:00pm"
    m = re.search(r"(\d{1,2}):(\d{2})\s*(am|pm)", v)
    if m:
        sh, sm, sa = m.groups()
        h = _to24(int(sh), int(sm), sa)
        eh = _to24(int(sh) + 1, int(sm), sa)  # default 1hr
        return h, eh, False

    return None, None, True  # fallback to all-day


def _to24(h: int, m: int, ampm: str) -> str:
    if ampm == "pm" and h != 12:
        h += 12
    elif ampm == "am" and h == 12:
        h = 0
    return f"{h:02d}:{m:02d}"


def make_datetime(d: date, time_str: str) -> str:
    """Combine a date and HH:MM string into an ISO 8601 dateTime with CT offset."""
    h, mn = map(int, time_str.split(":"))
    dt = datetime(d.year, d.month, d.day, h, mn, tzinfo=CT)
    return dt.isoformat()


# ---------------------------------------------------------------------------
# Template parsing
# ---------------------------------------------------------------------------

def parse_template(path: Path) -> list[dict] | None:
    """
    Returns a list of event dicts (usually 1, but 2 for double-booked conflicts).
    Returns None if the file should be skipped.
    """
    if path.name == "README.md":
        return None

    text = path.read_text()

    # Skip optimization suggestions — they're not real events
    if "OPTIMIZATION" in path.name:
        return None

    def field(name: str) -> str:
        m = re.search(rf"\*\*{name}:\*\*\s*(.+)", text)
        return m.group(1).strip() if m else ""

    title = field("Title")
    date_str = field("Date")
    time_str = field("Time")
    location = field("Location")
    description_m = re.search(r"\*\*Description:\*\*\n(.+?)(?=\n\*\*|\n#|\Z)", text, re.DOTALL)
    description = description_m.group(1).strip() if description_m else ""

    # Strip AI notes from description
    notes_idx = description.find("**Notes for AI")
    if notes_idx != -1:
        description = description[:notes_idx].strip()
    # Strip conflict flags from description
    conflict_idx = description.find("**⚠️")
    if conflict_idx != -1:
        description = description[:conflict_idx].strip()

    dates = parse_date_field(date_str)
    if not dates:
        print(f"  [SKIP] Could not parse date '{date_str}' in {path.name}")
        return None

    start_time, end_time, is_all_day = parse_time_field(time_str)

    events = []

    if is_all_day or (start_time is None):
        # All-day event — use date range if multi-day
        start_date = dates[0]
        # For multi-day, end date is exclusive in Google Calendar
        end_date = dates[-1] + timedelta(days=1) if len(dates) > 1 else start_date + timedelta(days=1)
        events.append({
            "summary": title,
            "description": description,
            "location": location if location and location != "N/A" else "",
            "start": {"date": start_date.isoformat()},
            "end": {"date": end_date.isoformat()},
            "attendees": [
                {"email": CEO_EMAIL, "responseStatus": "accepted"},
                {"email": INVITE_EMAIL},
            ],
        })
    else:
        # Timed event — create on the first date
        target_date = dates[0]
        events.append({
            "summary": title,
            "description": description,
            "location": location if location and location != "N/A" else "",
            "start": {"dateTime": make_datetime(target_date, start_time), "timeZone": "America/Chicago"},
            "end": {"dateTime": make_datetime(target_date, end_time), "timeZone": "America/Chicago"},
            "attendees": [
                {"email": CEO_EMAIL, "responseStatus": "accepted"},
                {"email": INVITE_EMAIL},
            ],
        })

    # ----- Special case: Double-booked conflict needs a SECOND event created -----
    # The "CONFLICT - Double Booked April 17" file contains the Buffalo call;
    # the Sequoia Q2 call is in EXTERNAL - Investor Quarterly Update Call.md.
    # Both get created naturally when we process all files.

    # The "CONFLICT - Back to Back No Buffer" = Board Prep call;
    # the Board Meeting itself is in EXTERNAL - Board Meeting.md.
    # Both created naturally.

    return events if events else None


# ---------------------------------------------------------------------------
# GWS helper
# ---------------------------------------------------------------------------

def gws(*args) -> dict:
    result = subprocess.run(["gws", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"gws error: {result.stderr.strip()}")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def create_event(event: dict, dry_run: bool) -> bool:
    if dry_run:
        return True
    try:
        gws(
            "calendar", "events", "insert",
            "--params", json.dumps({
                "calendarId": "primary",
                "sendUpdates": "all",  # sends invite email to kaisayshi12
            }),
            "--json", json.dumps(event),
        )
        return True
    except RuntimeError as e:
        print(f"    ERROR: {e}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Create demo CEO calendar events via gws")
    parser.add_argument("--dry-run", action="store_true", help="Print without creating")
    args = parser.parse_args()

    templates = sorted(TEMPLATES_DIR.glob("*.md"))
    if not templates:
        print(f"No templates found in {TEMPLATES_DIR}")
        sys.exit(1)

    print(f"Found {len(templates)} calendar template files")
    print(f"Creating events on xavier's calendar with invite to: {INVITE_EMAIL}")
    if args.dry_run:
        print("DRY RUN — no events will actually be created\n")
    else:
        print()

    created = 0
    skipped = 0
    failed = 0

    for tmpl in sorted(templates):
        print(f"  [{tmpl.stem}]")
        events = parse_template(tmpl)

        if events is None:
            print(f"    Skipped")
            skipped += 1
            continue

        for ev in events:
            start = ev["start"].get("dateTime") or ev["start"].get("date")
            print(f"    Title: {ev['summary']}")
            print(f"    Start: {start}")

            ok = create_event(ev, args.dry_run)
            if ok:
                print(f"    {'(dry run)' if args.dry_run else 'Created ✓'}")
                created += 1
            else:
                failed += 1

            if not args.dry_run:
                time.sleep(0.3)  # avoid Calendar API rate limits

    print(f"\nDone: {created} events created, {skipped} skipped, {failed} failed")
    if not args.dry_run and created > 0:
        print(f"\nInvite emails sent to {INVITE_EMAIL} — check that inbox.")
        print(f"Calendar conflicts to demo:")
        print(f"  • April 17 — Sequoia Q2 call (2:00pm) overlaps Buffalo Intro (2:00pm-3:00pm)")
        print(f"  • April 18 — Board Prep (11am-12pm) back-to-back with Board Meeting (12pm)")
        print(f"  • April 22 — Team Leads Sync (8am) conflicts with Nashville flight (7:45am)")


if __name__ == "__main__":
    main()
