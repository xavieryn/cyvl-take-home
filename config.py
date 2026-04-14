import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# API keys — Anthropic primary, Groq fallback
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Google OAuth paths (only needed for live mode)
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
GOOGLE_TOKEN_PATH = os.getenv("GOOGLE_TOKEN_PATH", "token.json")

# Obsidian vault — defaults to ~/Documents/ObsidianVault
OBSIDIAN_VAULT_PATH = Path(
    os.getenv("OBSIDIAN_VAULT_PATH", "~/Documents/ObsidianVault")
).expanduser()

# Pipeline behaviour
MAX_EMAILS = int(os.getenv("MAX_EMAILS", "3"))
CALENDAR_DAYS_AHEAD = int(os.getenv("CALENDAR_DAYS_AHEAD", "3"))

# Inbox to read from — must match the account currently authenticated in gws
# (gws auth login switches which account "userId: me" resolves to)
INBOX_EMAIL = os.getenv("INBOX_EMAIL", "me")  # "me" = whoever gws is authed as

# Model settings
MODEL = "claude-opus-4-6"                  # Anthropic primary
OLLAMA_MODEL = "qwen2.5"           # Ollama local fallback
OLLAMA_BASE_URL = "http://localhost:11434/v1"
MAX_TOKENS = 8096
