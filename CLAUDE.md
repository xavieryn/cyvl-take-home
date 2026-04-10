	# AI Chief of Staff — Project Context

Take-home project for the CYVL "AI Intern to the CEO" role.
Candidate: Xavier Nishikawa · Date: 2026-04-10

---

## What This Is

A Python multi-agent pipeline that acts as a CEO's AI Chief of Staff:
- Fetches Gmail + Google Calendar (or generates mock data in dev)
- Triages emails by urgency, extracts action items, drafts replies
- Writes a structured daily briefing + task notes to an Obsidian vault
``
**Run it:**
```bash
cp .env.example .env          # add ANTHROPIC_API_KEY
python main.py                # mock data (default)
python main.py --live         # real Gmail + Calendar
python main.py --vault ~/Vault --task inbox_triage
```

---

## Project Structure

```
cyvl-take-home/
├── main.py                   # Entry point — argparse, calls TeamLeadAgent
├── config.py                 # Loads .env; exports MODEL, OBSIDIAN_VAULT_PATH, etc.
├── models.py                 # Pydantic v2 models (shared contracts between agents)
├── requirements.txt          # anthropic, pydantic, google-auth-*, python-dotenv
├── .env.example              # Template — copy to .env and fill in
│
├── agents/
│   ├── team_lead.py          # Orchestrator: Claude w/ 4 tools sequences the pipeline
│   ├── mock_data.py          # Dev data: 6 realistic emails + 5 calendar events
│   ├── data_ingestion.py     # Live data: Gmail + Calendar via OAuth2 (token.json)
│   ├── processing.py         # Intelligence layer: Claude triages, extracts, drafts
│   └── obsidian.py           # File writer: creates vault structure + Markdown notes
│
├── vault_templates/          # Checked-in Obsidian templates (installed into vault on first run)
│   ├── README.md             # Vault guide for the CEO
│   ├── Templates/            # 13 note templates (Meeting Notes, Deal, OKR, etc.)
│   └── Tasks/                # 5 pre-built team task boards (Engineering, Sales, etc.)
│
├── PROMPT_HISTORY.md         # Build log: every prompt + architectural reasoning
└── CLAUDE.md                 # This file
```

---

## Agent Architecture

```
TeamLeadAgent (team_lead.py)
  ├── fetch_data  →  MockDataAgent  OR  DataIngestionAgent
  ├── analyze_data  →  ProcessingAgent
  ├── write_to_obsidian  →  ObsidianAgent
  └── report_completion  →  returns Dict to main.py
```

**TeamLeadAgent** (`agents/team_lead.py`)
- Claude orchestrator with 4 tools; decides execution order
- Holds pipeline state: `_emails`, `_events`, `_briefing`, `_obsidian_path`
- Uses lazy imports inside tool methods to avoid circular imports

**MockDataAgent** (`agents/mock_data.py`)
- No LLM, no API calls — pure Python
- 6 email templates (budget approval, contract renewal, partnership, Buffalo city intro, team lunch, newsletter)
- 5 calendar events (standup, 1:1, investor call, Nashville demo, board prep)
- Activated when `config.USE_MOCK_DATA = True` or no `--live` flag

**DataIngestionAgent** (`agents/data_ingestion.py`)
- Google OAuth2 via InstalledAppFlow; caches `token.json`
- Requires `credentials.json` from Google Cloud Console (Gmail + Calendar APIs enabled)
- Activated by `--live` flag or `USE_MOCK_DATA=false` in `.env`

**ProcessingAgent** (`agents/processing.py`)
- Claude with adaptive thinking; accumulates state across tool calls
- Tools: `save_email_analysis`, `save_action_items`, `save_executive_summary`
- Returns a `DailyBriefing` Pydantic model

**ObsidianAgent** (`agents/obsidian.py`)
- No LLM — pure file I/O
- On first run: creates all vault folders + installs templates from `vault_templates/`
- Writes: `Daily Briefings/{date} Daily Briefing.md` + `Tasks/{date} — {title}.md` for HIGH priority items
- Templates installed once; skips existing files so the CEO's edits are preserved

---

## Key Models (`models.py`)

```python
Urgency         # HIGH | MEDIUM | LOW
EmailCategory   # ACTION_REQUIRED | MEETING_REQUEST | FYI | NEWSLETTER | OTHER
Email           # Raw email from Gmail or mock data
CalendarEvent   # Raw event
ProcessedEmail  # Email + urgency + category + action_items + draft_reply + summary
ActionItem      # title + description + source_type + source_id + priority + due_date
DailyBriefing   # date + processed_emails + upcoming_events + action_items + executive_summary
```

---

## Config (`config.py`)

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Required. Anthropic API key |
| `OBSIDIAN_VAULT_PATH` | `~/ObsidianVault/CYVL Chief of Staff` | Where to write notes |
| `USE_MOCK_DATA` | `True` | `false` to use real Gmail/Calendar |
| `MODEL` | `claude-opus-4-6` | Claude model for all AI agents |
| `MAX_TOKENS` | `8096` | Max tokens per AI response |
| `GOOGLE_CREDENTIALS_PATH` | `credentials.json` | OAuth2 client secret file |
| `MAX_EMAILS` | `20` | Number of emails to fetch per run |
| `CALENDAR_DAYS_AHEAD` | `7` | How many days of calendar to pull |

---

## Vault Structure (written at runtime)

```
~/ObsidianVault/CYVL Chief of Staff/
├── Daily Briefings/
├── Meeting Notes/
├── People/
│   ├── Investors/
│   ├── Clients/
│   └── Team/
├── Deals/
├── Projects/
├── Tasks/              ← task boards + AI-generated HIGH priority items
├── Company/
│   ├── OKRs/
│   ├── Decision Log/
│   └── Retrospectives/
└── Templates/          ← copied from vault_templates/Templates/ on first run
```

---

## Design Decisions (abbreviated)

- **Obsidian over Notion** — local Markdown files; no API auth needed for MVP
- **5 agents not 4** — ProcessingAgent is the intelligence layer; without it, the system is just a file mover
- **Mock/Live as separate classes** — flip `USE_MOCK_DATA` env var; no code changes needed
- **Manual tool loops** — gives full visibility into each tool call and state accumulation
- **Adaptive thinking** — Claude decides reasoning depth per email; cheap for newsletters, thorough for contracts
- **Pydantic contracts** — breaks loudly at agent boundaries, not silently downstream
- **Templates first** — define the schema before the AI writes to it; consistent notes are automatable notes

Full reasoning in `PROMPT_HISTORY.md`.

---

## Extensibility Roadmap

1. Auto-create City/Client notes when a new municipality appears in email
2. HubSpot sync via MCP when a deal-stage email is detected
3. Slack: post morning briefing to CEO-only channel
4. Calendar prep: generate meeting brief 30 min before each event
5. Obsidian Local REST API for bidirectional sync (instead of direct file I/O)
