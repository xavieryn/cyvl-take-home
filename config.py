import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# API keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Google OAuth paths (only needed for live mode)
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
GOOGLE_TOKEN_PATH = os.getenv("GOOGLE_TOKEN_PATH", "token.json")

# Obsidian vault — defaults to ~/Documents/ObsidianVault
OBSIDIAN_VAULT_PATH = Path(
    os.getenv("OBSIDIAN_VAULT_PATH", "~/Documents/ObsidianVault")
).expanduser()

# Pipeline behaviour
USE_MOCK_DATA = os.getenv("USE_MOCK_DATA", "true").lower() == "true"
MAX_EMAILS = int(os.getenv("MAX_EMAILS", "20"))
CALENDAR_DAYS_AHEAD = int(os.getenv("CALENDAR_DAYS_AHEAD", "3"))

# Claude model settings
MODEL = "claude-opus-4-6"
MAX_TOKENS = 8096
