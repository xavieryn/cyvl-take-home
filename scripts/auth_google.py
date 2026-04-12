"""
auth_google.py
OAuth2 login for the inbox account (kaisayshi12@gmail.com).
Run this once — it opens a browser, you approve, and it saves token.json.

Usage:
    python scripts/auth_google.py
"""

import json
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

CLIENT_SECRET = Path.home() / ".config" / "gws" / "client_secret.json"
TOKEN_PATH = Path(__file__).parent.parent / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def main():
    if not CLIENT_SECRET.exists():
        print(f"ERROR: client_secret.json not found at {CLIENT_SECRET}")
        return

    print("Opening browser for Google sign-in...")
    print("Sign in as kaisayshi12@gmail.com\n")

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)

    TOKEN_PATH.write_text(creds.to_json())
    print(f"\nSaved token to {TOKEN_PATH}")
    print("Pipeline is ready — run: python main.py --live")


if __name__ == "__main__":
    main()
