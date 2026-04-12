"""
Team Lead Agent (Orchestrator)
Uses Claude (primary) with Gemini fallback to plan and execute the full pipeline.
"""

import json
from typing import Any, Dict, List

import anthropic

from models import CalendarEvent, DailyBriefing, Email
import config

_QUOTA_ERRORS = (anthropic.RateLimitError, anthropic.APIStatusError)


def _is_quota_error(exc: Exception) -> bool:
    if isinstance(exc, anthropic.RateLimitError):
        return True
    if isinstance(exc, anthropic.APIStatusError) and exc.status_code in (429, 529):
        return True
    # Credit balance exhausted (400 with specific message)
    if isinstance(exc, anthropic.BadRequestError) and "credit balance" in str(exc).lower():
        return True
    return False



_TOOLS = [
    {
        "name": "fetch_data",
        "description": (
            "Fetch emails and calendar events. "
            "Uses mock data in dev mode, real Gmail/Calendar in production."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "use_mock": {
                    "type": "boolean",
                    "description": "true = mock data, false = live Gmail/Calendar",
                }
            },
            "required": ["use_mock"],
        },
    },
    {
        "name": "analyze_data",
        "description": (
            "Run the Processing Agent to triage emails, extract action items, "
            "draft replies, and build the structured briefing. "
            "Must call fetch_data first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": ["reason"],
        },
    },
    {
        "name": "write_to_obsidian",
        "description": (
            "Write the processed briefing to the Obsidian vault. "
            "Must call analyze_data first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": ["reason"],
        },
    },
    {
        "name": "report_completion",
        "description": "Report final pipeline result. Call this last.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["success", "partial", "failed"]},
                "summary": {"type": "string"},
                "outputs": {"type": "object"},
            },
            "required": ["status", "summary"],
        },
    },
]


class TeamLeadAgent:
    """
    Orchestrates the AI Chief of Staff pipeline.
    Tries Anthropic first; automatically falls back to Gemini on quota errors.
    """

    def __init__(self):
        self._reset_state()

    def _reset_state(self):
        self._emails: List[Email] = []
        self._events: List[CalendarEvent] = []
        self._briefing: DailyBriefing | None = None
        self._obsidian_path: str = ""
        self._result: Dict[str, Any] = {}

    def _build_prompt(self, task: str) -> str:
        return (
            f"You are the AI Chief of Staff pipeline orchestrator.\n\n"
            f"Task: {task}\n"
            f"Mode: {'DEVELOPMENT — use mock data' if config.USE_MOCK_DATA else 'PRODUCTION — use live data'}\n\n"
            f"Execute the full pipeline in order:\n"
            f"1. fetch_data (use_mock={'true' if config.USE_MOCK_DATA else 'false'})\n"
            f"2. analyze_data\n"
            f"3. write_to_obsidian\n"
            f"4. report_completion with a concise summary\n\n"
            f"Be systematic. Each step depends on the previous."
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, task: str = "daily_briefing") -> Dict[str, Any]:
        mode = "mock data" if config.USE_MOCK_DATA else "live Gmail/Calendar"
        print(f"\n[TeamLeadAgent] Starting: {task} ({mode})")
        print("=" * 60)
        try:
            return self._run_with_anthropic(task)
        except Exception as exc:
            if _is_quota_error(exc):
                print(f"[TeamLeadAgent] Anthropic quota hit — switching to Ollama")
                self._reset_state()
                return self._run_with_ollama(task)
            raise

    # ------------------------------------------------------------------
    # Anthropic implementation
    # ------------------------------------------------------------------

    def _run_with_anthropic(self, task: str) -> Dict[str, Any]:
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        messages = [{"role": "user", "content": self._build_prompt(task)}]

        while True:
            response = client.messages.create(
                model=config.MODEL,
                max_tokens=4096,
                thinking={"type": "adaptive"},
                tools=_TOOLS,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                break

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        print(f"\n[TeamLeadAgent] → {block.name}")
                        result = self._dispatch(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        })
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

        print("=" * 60)
        print("[TeamLeadAgent] Pipeline complete (Anthropic)")
        return self._result

    # ------------------------------------------------------------------
    # Gemini implementation
    # ------------------------------------------------------------------

    _GROQ_TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "fetch_data",
                "description": "Fetch emails and calendar events (mock or live).",
                "parameters": {
                    "type": "object",
                    "properties": {"use_mock": {"type": "boolean"}},
                    "required": ["use_mock"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "analyze_data",
                "description": "Run Processing Agent to triage emails and build the briefing.",
                "parameters": {
                    "type": "object",
                    "properties": {"reason": {"type": "string"}},
                    "required": ["reason"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_to_obsidian",
                "description": "Write the processed briefing to the Obsidian vault.",
                "parameters": {
                    "type": "object",
                    "properties": {"reason": {"type": "string"}},
                    "required": ["reason"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "report_completion",
                "description": "Report final pipeline result. Call this last.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["success", "partial", "failed"]},
                        "summary": {"type": "string"},
                    },
                    "required": ["status", "summary"],
                },
            },
        },
    ]

    def _run_with_ollama(self, task: str) -> Dict[str, Any]:
        from openai import OpenAI

        client = OpenAI(base_url=config.OLLAMA_BASE_URL, api_key="ollama")
        messages = [{"role": "user", "content": self._build_prompt(task)}]

        while True:
            response = client.chat.completions.create(
                model=config.OLLAMA_MODEL,
                messages=messages,
                tools=self._GROQ_TOOLS,  # same OpenAI-compatible format
                tool_choice="auto",
            )
            choice = response.choices[0]
            messages.append(choice.message.model_dump(exclude_none=True))

            if choice.finish_reason != "tool_calls" or not choice.message.tool_calls:
                break

            done = False
            for tc in choice.message.tool_calls:
                print(f"\n[TeamLeadAgent] → {tc.function.name}")
                result = self._dispatch(tc.function.name, json.loads(tc.function.arguments))
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                })
                if tc.function.name == "report_completion":
                    done = True
            if done:
                break

        print("=" * 60)
        print("[TeamLeadAgent] Pipeline complete (Ollama)")
        return self._result

    # ------------------------------------------------------------------
    # Tool dispatch (shared)
    # ------------------------------------------------------------------

    def _dispatch(self, name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if name == "fetch_data":
                return self._fetch_data(data)
            if name == "analyze_data":
                return self._analyze_data(data)
            if name == "write_to_obsidian":
                return self._write_to_obsidian(data)
            if name == "report_completion":
                return self._report_completion(data)
            return {"error": f"Unknown tool: {name}"}
        except Exception as e:
            print(f"[TeamLeadAgent] ERROR in {name}: {e}")
            return {"error": str(e), "tool": name}

    def _fetch_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if data.get("use_mock", True):
            from agents.mock_data import MockDataAgent
            self._emails, self._events = MockDataAgent().run()
            source = "mock"
        else:
            from agents.data_ingestion import DataIngestionAgent
            self._emails, self._events = DataIngestionAgent().run()
            source = "live"
        return {
            "emails_fetched": len(self._emails),
            "events_fetched": len(self._events),
            "source": source,
            "preview": [e.subject for e in self._emails[:3]],
        }

    def _analyze_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self._emails and not self._events:
            return {"error": "No data — call fetch_data first"}
        from agents.processing import ProcessingAgent
        self._briefing = ProcessingAgent().run(self._emails, self._events)
        urgent = sum(1 for e in self._briefing.processed_emails if e.urgency.value == "high")
        return {
            "emails_processed": len(self._briefing.processed_emails),
            "action_items": len(self._briefing.action_items),
            "urgent_emails": urgent,
            "has_summary": bool(self._briefing.executive_summary),
        }

    def _write_to_obsidian(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self._briefing:
            return {"error": "No briefing — call analyze_data first"}
        from agents.obsidian import ObsidianAgent
        self._obsidian_path = ObsidianAgent().run(self._briefing)
        return {
            "written": True,
            "vault": str(config.OBSIDIAN_VAULT_PATH),
            "briefing_note": self._obsidian_path,
        }

    def _report_completion(self, data: Dict[str, Any]) -> Dict[str, Any]:
        self._result = {
            "status": data.get("status", "success"),
            "summary": data.get("summary", ""),
            "outputs": data.get("outputs", {}),
            "briefing_date": self._briefing.date if self._briefing else "",
            "obsidian_path": self._obsidian_path,
        }
        if self._briefing:
            self._result["stats"] = {
                "emails": len(self._briefing.processed_emails),
                "action_items": len(self._briefing.action_items),
                "events": len(self._briefing.upcoming_events),
            }
        return {"acknowledged": True}
