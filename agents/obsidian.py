"""
Obsidian Agent
Writes structured notes directly to an Obsidian vault as Markdown files.
No LLM needed — pure Python file I/O.
"""

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import List

from models import ActionItem, CalendarEvent, DailyBriefing, ProcessedEmail, Urgency
import config

_URGENCY_EMOJI = {Urgency.HIGH: "🔴", Urgency.MEDIUM: "🟡", Urgency.LOW: "🟢"}

# Canonical vault folders to create on first run
_VAULT_FOLDERS = [
    "Daily Briefings",
    "Meeting Notes",
    "People/Investors",
    "People/Clients",
    "People/Team",
    "Deals",
    "Projects",
    "Tasks",
    "Company/OKRs",
    "Company/Decision Log",
    "Company/Retrospectives",
    "Templates",
]

# Source templates bundled with the repo
_TEMPLATES_SRC = Path(__file__).parent.parent / "vault_templates"


class ObsidianAgent:
    """Writes daily briefings and task notes to an Obsidian vault."""

    def __init__(self):
        self.vault = config.OBSIDIAN_VAULT_PATH
        self._ensure_structure()

    def run(self, briefing: DailyBriefing) -> str:
        """Create daily briefing note + high-priority task notes. Returns briefing path."""
        print(f"[ObsidianAgent] Writing to vault: {self.vault}")

        briefing_path = self._create_daily_briefing(briefing)

        task_count = 0
        for item in briefing.action_items:
            if item.priority == Urgency.HIGH:
                self._create_task_note(item, briefing.date)
                task_count += 1

        print(f"[ObsidianAgent] Created briefing + {task_count} task notes")
        return str(briefing_path)

    # ------------------------------------------------------------------
    # Vault structure
    # ------------------------------------------------------------------

    def _ensure_structure(self):
        """Create all vault folders and install templates on first run."""
        for folder in _VAULT_FOLDERS:
            (self.vault / folder).mkdir(parents=True, exist_ok=True)

        self._install_templates()
        self._install_task_boards()

    def _install_templates(self):
        """
        Copy Templates/ from vault_templates/ into the vault's Templates/ folder.
        Skips files that already exist so live edits aren't overwritten.
        """
        src = _TEMPLATES_SRC / "Templates"
        if not src.exists():
            return
        dest = self.vault / "Templates"
        for tmpl in src.glob("*.md"):
            target = dest / tmpl.name
            if not target.exists():
                shutil.copy2(tmpl, target)
                print(f"[ObsidianAgent] Installed template: {tmpl.name}")

    def _install_task_boards(self):
        """
        Copy pre-built team task boards into Tasks/ on first run.
        Skips files that already exist.
        """
        src = _TEMPLATES_SRC / "Tasks"
        if not src.exists():
            return
        dest = self.vault / "Tasks"
        for board in src.glob("*.md"):
            target = dest / board.name
            if not target.exists():
                shutil.copy2(board, target)
                print(f"[ObsidianAgent] Installed task board: {board.name}")

    # ------------------------------------------------------------------
    # Daily briefing
    # ------------------------------------------------------------------

    def _create_daily_briefing(self, briefing: DailyBriefing) -> Path:
        path = self.vault / "Daily Briefings" / f"{briefing.date} Daily Briefing.md"
        path.write_text(self._render_briefing(briefing), encoding="utf-8")
        return path

    def _render_briefing(self, b: DailyBriefing) -> str:
        urgent = [e for e in b.processed_emails if e.urgency == Urgency.HIGH]
        medium = [e for e in b.processed_emails if e.urgency == Urgency.MEDIUM]
        low    = [e for e in b.processed_emails if e.urgency == Urgency.LOW]

        lines = [
            "---",
            f"date: {b.date}",
            f"type: daily-briefing",
            f"emails_processed: {len(b.processed_emails)}",
            f"action_items: {len(b.action_items)}",
            "---",
            "",
            f"# Daily Briefing — {b.date}",
            "",
            "## Executive Summary",
            "",
            b.executive_summary or "_No summary generated._",
            "",
            "---",
            "",
            "## Email Triage",
            "",
            f"**{len(urgent)} urgent · {len(medium)} medium · {len(low)} low**",
            "",
        ]

        if urgent:
            lines += ["### 🔴 Urgent"]
            for e in urgent:
                lines += self._render_email(e)

        if medium:
            lines += ["", "### 🟡 Medium Priority"]
            for e in medium:
                lines += self._render_email(e)

        if low:
            lines += ["", "### 🟢 Low / FYI"]
            for e in low:
                lines += self._render_email(e, compact=True)

        lines += [
            "",
            "---",
            "",
            "## Upcoming Events",
            "",
        ]
        if b.upcoming_events:
            for ev in b.upcoming_events:
                lines += self._render_event(ev)
        else:
            lines.append("_No upcoming events._")

        lines += [
            "",
            "---",
            "",
            "## Action Items",
            "",
        ]
        if b.action_items:
            for item in b.action_items:
                emoji = _URGENCY_EMOJI.get(item.priority, "")
                due = f" · due {item.due_date}" if item.due_date else ""
                lines.append(f"- [ ] {emoji} **{item.title}**{due}")
                lines.append(f"  - {item.description}")
        else:
            lines.append("_No action items._")

        lines += [
            "",
            "---",
            "",
            f"_Generated by AI Chief of Staff · {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        ]
        return "\n".join(lines)

    def _render_email(self, e: ProcessedEmail, compact: bool = False) -> List[str]:
        lines = [
            "",
            f"#### {e.subject}",
            f"**From:** {e.sender} · **Type:** {e.category.value.replace('_', ' ').title()}",
            "",
            e.summary,
        ]
        if not compact and e.action_items:
            lines += ["", "**Action items:**"]
            lines += [f"- {a}" for a in e.action_items]
        if not compact and e.draft_reply:
            lines += [
                "",
                "<details>",
                "<summary>📝 Draft Reply</summary>",
                "",
                "```",
                e.draft_reply,
                "```",
                "",
                "</details>",
            ]
        return lines

    def _render_event(self, ev: CalendarEvent) -> List[str]:
        start = ev.start.strftime("%b %d %I:%M %p")
        end   = ev.end.strftime("%I:%M %p")
        lines = [f"### {ev.title}", f"**{start} — {end}**"]
        if ev.location:
            lines.append(f"📍 {ev.location}")
        if ev.attendees:
            shown = ev.attendees[:3]
            extra = f" +{len(ev.attendees)-3}" if len(ev.attendees) > 3 else ""
            lines.append(f"👥 {', '.join(shown)}{extra}")
        if ev.description:
            lines += ["", f"_{ev.description[:200]}_"]
        lines.append("")
        return lines

    # ------------------------------------------------------------------
    # Task notes
    # ------------------------------------------------------------------

    def _create_task_note(self, item: ActionItem, date: str) -> Path:
        safe = re.sub(r'[<>:"/\\|?*]', "", item.title)[:50].strip()
        path = self.vault / "Tasks" / f"{date} — {safe}.md"
        content = "\n".join([
            "---",
            f"date: {date}",
            "type: task",
            f"priority: {item.priority.value}",
            f"source: {item.source_type}/{item.source_id}",
            "status: open",
            "---",
            "",
            f"# {item.title}",
            "",
            f"**Priority:** {_URGENCY_EMOJI.get(item.priority, '')} {item.priority.value.title()}",
            f"**Source:** {item.source_type.title()} · `{item.source_id}`",
            "",
            "## Description",
            "",
            item.description,
            "",
            "## Notes",
            "",
            "_(add notes here)_",
            "",
            "---",
            "",
            f"_Linked from [[{date} Daily Briefing]]_",
        ])
        path.write_text(content, encoding="utf-8")
        return path
