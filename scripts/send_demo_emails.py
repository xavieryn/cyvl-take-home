"""
send_demo_emails.py
Reads all Gmail template .md files from xtemp/Gmail Templates/ and sends
each one from xavier.nishikawa@gmail.com to kaisayshi12@gmail.com via gws.

Usage:
    python scripts/send_demo_emails.py
    python scripts/send_demo_emails.py --dry-run   # print what would be sent
"""

import argparse
import base64
import json
import re
import subprocess
import sys
import time
from email.header import Header
from email.mime.text import MIMEText
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.parent / "xtemp" / "Gmail Templates"
SENDER = "Xavier Nishikawa <xavier.nishikawa@gmail.com>"
RECIPIENT = "kaisayshi12@gmail.com"


def gws(*args) -> dict:
    result = subprocess.run(["gws", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"gws error: {result.stderr.strip()}")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def parse_template(path: Path) -> dict | None:
    """Extract From persona, Subject, and body from a Gmail template .md file."""
    text = path.read_text()

    # --- From line (persona, not necessarily a real sender)
    from_match = re.search(r"\*\*From:\*\*\s*(.+)", text)
    from_persona = from_match.group(1).strip() if from_match else "Unknown Sender"

    # --- Subject
    subject_match = re.search(r"\*\*Subject:\*\*\s*(.+)", text)
    if not subject_match:
        print(f"  [SKIP] No subject found in {path.name}")
        return None
    subject = subject_match.group(1).strip()

    # --- Body: prefer content after --- separator; fall back to content after last **Field:** line
    parts = re.split(r"\n---+\n", text, maxsplit=1)
    if len(parts) >= 2:
        raw_body = parts[1].strip()
    else:
        # No separator — find the end of the last **Field:** header line and take everything after
        last_header = list(re.finditer(r"\*\*[^*]+:\*\*\s*.+", text))
        if not last_header:
            print(f"  [SKIP] Could not find body in {path.name}")
            return None
        body_start = last_header[-1].end()
        raw_body = text[body_start:].strip()

    # Strip any trailing "Notes for AI" section that leaked in (shouldn't happen but safe)
    notes_idx = raw_body.find("**Notes for AI")
    if notes_idx != -1:
        raw_body = raw_body[:notes_idx].strip()

    return {
        "from_persona": from_persona,
        "subject": subject,
        "body": raw_body,
    }


def build_raw_message(from_persona: str, subject: str, body: str) -> str:
    """Build a base64url-encoded RFC 2822 email message.

    Uses Python's email library so that non-ASCII characters (emojis, accents)
    in the Subject and body are correctly encoded — no garbled characters.
    Gmail will override the From envelope with the authenticated sender,
    but Reply-To preserves the persona for the AI pipeline.
    """
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = SENDER
    msg["To"] = RECIPIENT
    msg["Reply-To"] = from_persona
    # Header() encodes non-ASCII (emojis etc.) using RFC 2047 base64
    msg["Subject"] = Header(subject, "utf-8")
    raw_bytes = msg.as_bytes()
    return base64.urlsafe_b64encode(raw_bytes).decode("utf-8")


def send_email(raw: str, dry_run: bool) -> bool:
    if dry_run:
        return True
    try:
        gws(
            "gmail", "users", "messages", "send",
            "--params", json.dumps({"userId": "me"}),
            "--json", json.dumps({"raw": raw}),
        )
        return True
    except RuntimeError as e:
        print(f"    ERROR: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Send demo CEO emails via gws")
    parser.add_argument("--dry-run", action="store_true", help="Print without sending")
    args = parser.parse_args()

    templates = sorted(TEMPLATES_DIR.glob("*.md"))
    if not templates:
        print(f"No templates found in {TEMPLATES_DIR}")
        sys.exit(1)

    print(f"Found {len(templates)} email templates")
    print(f"Sending from: {SENDER}")
    print(f"Sending to:   {RECIPIENT}")
    if args.dry_run:
        print("DRY RUN — no emails will actually be sent\n")
    else:
        print()

    sent = 0
    failed = 0

    for tmpl in templates:
        print(f"  [{tmpl.stem}]")
        data = parse_template(tmpl)
        if not data:
            failed += 1
            continue

        print(f"    Subject: {data['subject']}")
        print(f"    Persona: {data['from_persona']}")

        raw = build_raw_message(data["from_persona"], data["subject"], data["body"])
        ok = send_email(raw, args.dry_run)

        if ok:
            print(f"    {'(dry run — would send)' if args.dry_run else 'Sent ✓'}")
            sent += 1
        else:
            failed += 1

        # Brief pause to avoid Gmail rate limits
        if not args.dry_run:
            time.sleep(0.5)

    print(f"\nDone: {sent} sent, {failed} failed / skipped")


if __name__ == "__main__":
    main()
