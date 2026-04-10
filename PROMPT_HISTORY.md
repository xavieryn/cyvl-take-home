---
type: build-log
candidate: Xavier Nishikawa
date: 2026-04-10
role: AI Intern to the CEO
---

# CYVL AI Chief of Staff — Build Log

> This file logs every prompt given during development of the AI Chief of Staff system, plus concise reasoning for each architectural and technical decision.
> Intended as an interview artifact showing process, not just output.

---

## Prompt History

### [1] — Read the Interview Guide + Switch to Obsidian

> *"read this document to fully understand what I am going to build and then I am going to use obsidian instead of notion for the note taking aspect."*

**Decision:** Swap Notion for Obsidian.

**Why:** Obsidian stores notes as plain Markdown files on the local filesystem. This means zero API rate limits, no vendor lock-in, and the AI can write notes by just creating files — no complex API auth required to get a demo running. It also means the CEO owns their data locally. Obsidian's Local REST API plugin can be added later for richer integration (bidirectional sync, search, graph traversal) without changing the core architecture.

---

### [2] — Design the Agent Team

> *"I want to build a workflow automater. I want to have a few agents, one creating mock data such as for the gmail and the calendar so that when I actually run the app, it is getting real emails. I want a team lead agent that gives the tasks. I want an agent that does the ui for the obsidian stuff, and i want an agent the grabs the data like the back end and integrates it with the app. tell me if i need another agent. 'Create an agent team like this'"*

**Decision:** Identified a missing 5th agent — the Processing/Analysis Agent.

**Why:** The described team had a gap between "fetch data" and "write to Obsidian." Raw emails have no intelligence applied to them — someone (or something) needs to decide what's urgent, what action items exist, and what the CEO should read first. Without a dedicated processing layer, the Obsidian agent would receive raw unstructured email blobs and wouldn't know what to write. The Processing Agent is the intelligence layer that makes the system useful rather than just a file mover.

**Final agent team:**

| # | Agent | Role |
|---|-------|------|
| 1 | **Team Lead Agent** | Claude orchestrator; plans and sequences the pipeline |
| 2 | **Mock Data Agent** | Generates realistic fake emails/events for dev/testing |
| 3 | **Data Agent** | Fetches real Gmail + Google Calendar data via OAuth2 |
| 4 | **Processing Agent** | Claude w/ adaptive thinking; triages, extracts, drafts |
| 5 | **Obsidian Agent** | Writes structured Markdown notes to the vault |

**Decision:** Mock Data Agent separate from Data Agent (not a flag on one class).

**Why:** Keeping them as separate classes means you can run the full end-to-end pipeline during development without real credentials. The Team Lead passes `use_mock=true` to `fetch_data`, which routes to MockDataAgent. When you're ready for production you flip one env var (`USE_MOCK_DATA=false`) — no code changes. The mock data is also realistic enough to validate the Processing Agent's output format before touching real emails.

**Decision:** Python over TypeScript.

**Why:** Python has better ecosystem support for Google API client libraries, Pydantic data validation, and is the dominant language in AI/ML tooling. The Anthropic Python SDK is also the most mature. Since this is a backend automation pipeline (not a UI), Python is the pragmatic choice.

**Decision:** Manual tool loops (not the beta `@beta_tool` runner).

**Why:** The beta tool runner is convenient for simple cases but the manual loop gives visibility into each tool call, lets us accumulate state across multiple tool calls in a single agent run (needed for the Processing Agent), and makes it obvious what's happening at each step — important for a demo where you need to walk someone through the code.

**Decision:** `claude-opus-4-6` with `thinking={"type":"adaptive"}` for AI agents.

**Why:** Adaptive thinking lets Claude decide how deeply to reason per request. For email triage, some decisions are obvious (newsletter = low priority) and some require more thought (contract amendment with two legal clauses from a city government client). Adaptive thinking handles both efficiently without paying for extended thinking on every token. Opus 4.6 is used because this is the most capable model and the CEO's time is the scarcest resource — we want the analysis to be good, not just cheap.

**Decision:** Pydantic models for all data structures.

**Why:** Strict typing between agents prevents bugs at integration points. If the Processing Agent returns a badly-formed action item, Pydantic throws at the boundary rather than silently passing bad data into Obsidian notes. It also makes the data shape self-documenting — important when adding agents later or onboarding another engineer.

---

### [3] — Design Obsidian Templates First

> *"Before integrating anything else, I want to just start with a good obsidian template that would have the basic parts of a company for meeting notes, task lists for different groups within the company (help me think about anything else I might need within this)"*

**Decision:** Design the vault structure before wiring the AI to write to it.

**Why:** If you let the AI generate notes before defining the schema, you end up with inconsistent formats that are hard to search or automate later. Defining templates first means every AI-generated note is consistent, linkable, and queryable. It also means the Obsidian agent knows exactly which template to use for which type of content.

**Templates identified:**

*Core (high daily usage):*
- **Daily Briefing** — AI-generated each morning
- **Meeting Notes** — per meeting: agenda, decisions, action items
- **Task Board** — per team: Engineering, Sales, Ops, Product

*People & deals:*
- **Person / Contact** — key relationships: investors, clients, hires
- **City / Client** — one per municipality — core to CYVL's business
- **Deal** — sales pipeline: stage, value, next step, history

*Strategic:*
- **Weekly Review** — end-of-week: what shipped, blockers, next week
- **Project** — ongoing initiative: goal, owner, status, timeline
- **OKR / Goals** — quarterly objectives with key results + progress
- **Decision Log** — record of major calls + rationale — invaluable later
- **Investor Note** — per fund: commitments, meetings, follow-ups
- **Hire Tracker** — candidate pipeline per role
- **Retrospective** — post-mortems on deals, launches, incidents

*Not included (by design):*
- Calendar events (managed by Google Calendar — no duplication)
- Emails (referenced from notes, not stored in vault)
- Code docs (belong in repo, not Obsidian)

---

### [4] — Keep a Build Log

> *"Also keep a history txt for all of my prompts so that I can present it to the CEO for my interview and then concise reasoning for why I did what I did"*

**Decision:** Create this file.

**Why:** Showing your thinking process is as important as the demo. The CYVL interview guide explicitly asks "How did you prompt? How did you debug? What did you learn?" This file answers those questions directly. It also demonstrates that the build was intentional — not just running tools until something worked, but making deliberate architectural choices at each step.

---

### [5] — Use Obsidian Vault Structure + Convert Log to Markdown

> *"Lets also go with the obsidian structure that you suggested, actually make prompt_history an md file so that I can read it in obsidian"*

**Decision:** Convert `PROMPT_HISTORY.txt` → `PROMPT_HISTORY.md` with proper Obsidian formatting.

**Why:** A `.txt` file works as a plain text log but isn't readable in Obsidian's preview mode. Converting to `.md` means the build log gets YAML frontmatter, collapsible sections, and a table of contents — making it a first-class note in the vault that can link to other notes (e.g., `[[Daily Briefing]]`, `[[Processing Agent]]`).

**Decision:** Implement the full suggested vault folder structure.

**Why:** Consistent folder structure means the AI agent knows exactly where to write each note type. It also means the CEO can navigate the vault without the AI — the structure itself is the interface. The folders mirror how a COO would organize information: daily ops → people → deals → strategy.

**Vault structure:**

```
CYVL Chief of Staff/
├── Daily Briefings/          ← AI-generated each morning
├── Meeting Notes/            ← Per-meeting records
├── People/
│   ├── Investors/            ← VC/angel notes
│   ├── Clients/              ← Municipality + enterprise contacts
│   └── Team/                 ← Internal team profiles
├── Deals/                    ← Sales pipeline opportunities
├── Projects/                 ← Ongoing initiatives
├── Tasks/                    ← High-priority action items (AI-generated)
├── Company/
│   ├── OKRs/                 ← Quarterly objectives
│   ├── Decision Log/         ← Major decisions + rationale
│   └── Retrospectives/       ← Post-mortems
└── Templates/                ← All template files live here
```

---

## Key Architectural Decisions (Summary)

| Decision | Rationale |
|----------|-----------|
| **Obsidian over Notion** | Local files = no API auth needed for MVP, CEO owns data, easy to extend |
| **5 agents, not 4** | Processing Agent is the intelligence layer — without it, you have a file mover |
| **Mock + Live as separate classes** | Flip one env var to go from dev to production. No code changes needed |
| **Team Lead uses Claude** | Claude plans the execution order and handles edge cases. The pipeline is adaptive |
| **Pydantic models as contracts** | Type-safe data flow. Breaks loudly at the boundary, not silently downstream |
| **Adaptive thinking on AI agents** | Claude decides reasoning depth per request — efficient for simple, thorough for complex |
| **Templates before AI writes** | Define the schema first. Consistent notes are automatable notes |

---

## Extensibility Roadmap

1. **Auto-create City/Client notes** — When the Processing Agent detects a new municipality in an email (e.g., Buffalo city official intro), auto-create a City/Client note pre-filled with contact info and next steps.

2. **HubSpot sync** — When the Processing Agent identifies a deal-related email, update the deal stage in HubSpot via MCP and create a Deal note in Obsidian — single source of truth for the CEO.

3. **Slack integration** — Post the Daily Briefing summary to a CEO-only Slack channel every morning. The CEO can reply "approve" or "defer" to action items and the system routes accordingly.

4. **Calendar prep** — 30 minutes before each meeting, generate a prep note in Obsidian with attendee context, recent email threads, open action items from prior meetings, and talking points.

5. **Obsidian Local REST API** — Replace direct file I/O with the Obsidian Local REST API plugin for bidirectional sync — so edits the CEO makes in Obsidian are reflected back in the system's state.

---

*Build log maintained by Xavier Nishikawa · AI Chief of Staff take-home · CYVL · 2026-04-10*
