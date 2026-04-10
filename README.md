# AI Chief of Staff

A Python multi-agent pipeline that acts as a CEO's AI Chief of Staff.

Built as a take-home project for the CYVL "AI Intern to the CEO" role by Xavier Nishikawa.

---

## What It Does

- Fetches Gmail + Google Calendar (or runs on mock data in dev)
- Triages emails by urgency, extracts action items, and drafts replies
- Writes a structured daily briefing and task notes to an [Obsidian](https://obsidian.md) vault

---

## Quickstart

```bash
# 1. Clone and install
git clone https://github.com/xavieryn/cyvl-take-home.git
cd cyvl-take-home
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env

# 3. Run (mock data — no Google auth needed)
python main.py

# 4. Run with real Gmail + Calendar
python main.py --live

# 5. Options
python main.py --vault ~/MyVault --task inbox_triage
```

---

## Agent Architecture

```
TeamLeadAgent (orchestrator)
  ├── fetch_data       →  MockDataAgent  OR  DataIngestionAgent
  ├── analyze_data     →  ProcessingAgent  (Claude w/ adaptive thinking)
  ├── write_to_obsidian→  ObsidianAgent
  └── report_completion→  returns Dict to main.py
```

| Agent | Role |
|-------|------|
| `TeamLeadAgent` | Claude orchestrator with 4 tools; sequences the pipeline |
| `MockDataAgent` | 6 realistic emails + 5 calendar events — no API calls |
| `DataIngestionAgent` | Google OAuth2 for real Gmail + Calendar data |
| `ProcessingAgent` | Claude with adaptive thinking; triages, extracts, drafts |
| `ObsidianAgent` | Pure file I/O; writes vault structure + Markdown notes |

---

## Vault Output

On first run, the agent creates a full Obsidian vault:

```
~/ObsidianVault/CYVL Chief of Staff/
├── Daily Briefings/          ← AI-generated daily briefing
├── Tasks/                    ← Task boards + HIGH-priority items
├── Meeting Notes/
├── People/  (Investors, Clients, Team)
├── Deals/
├── Projects/
├── Company/  (OKRs, Decision Log, Retrospectives)
└── Templates/                ← 13 note templates, installed once
```

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Required |
| `OBSIDIAN_VAULT_PATH` | `~/Documents/ObsidianVault` | Where to write notes |
| `USE_MOCK_DATA` | `true` | Set `false` to use real Gmail/Calendar |
| `MODEL` | `claude-opus-4-6` | Claude model |
| `MAX_EMAILS` | `20` | Emails fetched per run |
| `CALENDAR_DAYS_AHEAD` | `7` | Days of calendar to pull |

For `--live` mode, place your Google OAuth2 `credentials.json` (Gmail + Calendar APIs enabled) in the project root. The first run will open a browser for auth and cache `token.json`.

---

## Project Structure

```
├── main.py              # Entry point
├── config.py            # Env + settings
├── models.py            # Pydantic v2 shared models
├── requirements.txt
├── agents/
│   ├── team_lead.py     # Orchestrator
│   ├── mock_data.py     # Dev data
│   ├── data_ingestion.py# Live Gmail/Calendar
│   ├── processing.py    # AI triage + drafts
│   └── obsidian.py      # Vault writer
└── vault_templates/     # Pre-built templates installed into vault
```

---

## Key Models

```python
Urgency         # HIGH | MEDIUM | LOW
EmailCategory   # ACTION_REQUIRED | MEETING_REQUEST | FYI | NEWSLETTER | OTHER
ProcessedEmail  # Email + urgency + category + action_items + draft_reply
ActionItem      # title + description + priority + due_date
DailyBriefing   # date + processed_emails + events + action_items + summary
```
