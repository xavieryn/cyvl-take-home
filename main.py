#!/usr/bin/env python3
"""
AI Chief of Staff — Entry Point

Usage:
  python main.py                   # run daily briefing
  python main.py --vault ~/myVault # override Obsidian vault path
  python main.py --task inbox_triage
"""

import sys
import json
import argparse
from pathlib import Path

import config
from agents.team_lead import TeamLeadAgent


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Chief of Staff")
    parser.add_argument(
        "--task",
        default="daily_briefing",
        choices=["daily_briefing", "inbox_triage", "calendar_review"],
    )
    parser.add_argument("--vault", help="Override Obsidian vault path")
    args = parser.parse_args()

    if args.vault:
        config.OBSIDIAN_VAULT_PATH = Path(args.vault).expanduser()

    if not config.ANTHROPIC_API_KEY:
        print("Error: ANTHROPIC_API_KEY not set.")
        print("Copy .env.example → .env and add your key.")
        return 1

    print("AI Chief of Staff")
    print(f"  Vault : {config.OBSIDIAN_VAULT_PATH}")
    print(f"  Task  : {args.task}")

    result = TeamLeadAgent().run(task=args.task)

    print("\nResult:")
    print(json.dumps(result, indent=2))

    if result.get("status") == "success":
        print(f"\nBriefing → {result.get('obsidian_path', 'N/A')}")
        return 0

    print(f"\nFailed: {result.get('summary', 'unknown error')}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
