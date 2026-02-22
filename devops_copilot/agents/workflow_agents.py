"""
workflow_agents.py — Multi-Provider Planner & Executor
Supports: Gemini (google-genai) | Groq (llama-3.3-70b-versatile)
Set LLM_PROVIDER=gemini|groq in your .env
"""
import json
import os
import re
from abc import ABC, abstractmethod
from pydantic import BaseModel
from devops_copilot.agents.base import BaseAgent, AgentState
from devops_copilot.tools.registry import registry
from devops_copilot.utils.logger import logger


# ── Data models ────────────────────────────────────────────────────────────────

class PlanStep(BaseModel):
    tool_name: str
    arguments: dict
    thought: str


class Plan(BaseModel):
    steps: list[PlanStep]


# ── Shared ReAct prompt ────────────────────────────────────────────────────────

_PLANNER_SYSTEM = """You are the Planner Agent in a ReAct (Reason + Act) loop acting as an AI DevOps Copilot.
Your job is to resolve an incident step by step using only the available tools.

Rules:
1. Output EXACTLY one step per response.
2. After seeing tool results, decide whether to take another step or finish.
3. If the goal is fully achieved, output an empty steps list: {{"steps": []}}
4. If restarting or doing a destructive action, include REQUIRES_APPROVAL in the thought.

Output format (strict JSON, no markdown fences):
{{
  "steps": [
    {{
      "tool_name": "<tool name from available tools>",
      "arguments": {{"<arg>": "<value>"}},
      "thought": "<your reasoning>"
    }}
  ]
}}

Available tools:
{tools}
"""


# ── LLM Provider backends ──────────────────────────────────────────────────────

class _LLMBackend(ABC):
    """Abstract LLM backend. Implement `complete(prompt) -> str`."""
    @abstractmethod
    def complete(self, prompt: str) -> str: ...


class _GeminiBackend(_LLMBackend):
    def __init__(self, model: str):
        from google import genai  # lazy import
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise EnvironmentError("GOOGLE_API_KEY not set.")
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def complete(self, prompt: str) -> str:
        response = self._client.models.generate_content(
            model=self._model, contents=prompt
        )
        return response.text.strip()


class _GroqBackend(_LLMBackend):
    def __init__(self, model: str):
        from groq import Groq  # lazy import
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY not set.")
        self._client = Groq(api_key=api_key)
        self._model = model

    def complete(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()


def _build_backend(provider: str) -> _LLMBackend:
    """Factory: builds the correct LLM backend based on provider name."""
    provider = provider.lower()
    if provider == "gemini":
        model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        logger.info(f"Using Gemini backend: {model}")
        return _GeminiBackend(model)
    elif provider == "groq":
        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        logger.info(f"Using Groq backend: {model}")
        return _GroqBackend(model)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: '{provider}'. Use gemini or groq.")


def _mock_plan() -> Plan:
    """Fallback demo plan when no API key is configured."""
    return Plan(steps=[PlanStep(
        tool_name="get_metrics",
        arguments={"service": "payment-gateway"},
        thought="Check health metrics to detect anomalies."
    )])


# ── Agents ─────────────────────────────────────────────────────────────────────

class PlannerAgent(BaseAgent):
    """
    Provider-agnostic Planner Agent.
    Set LLM_PROVIDER=gemini|groq in your .env to choose backend.
    """
    def __init__(self):
        super().__init__(name="Planner", role="Strategic Planning")

    async def chat(self, message: str, state: AgentState) -> Plan:
        provider = os.getenv("LLM_PROVIDER", "gemini")
        try:
            backend = _build_backend(provider)
        except EnvironmentError as e:
            logger.warning(f"No API key for '{provider}' — using mock plan. ({e})")
            return _mock_plan()
        except ValueError as e:
            logger.error(str(e))
            return _mock_plan()

        tools_info = registry.list_tools()
        system_prompt = _PLANNER_SYSTEM.format(tools=json.dumps(tools_info, indent=2))

        conversation = "\n".join(
            f"{m['role'].upper()}: {m['content']}"
            for m in state.history[-6:]
        )
        full_prompt = f"{system_prompt}\n\n{conversation}\nUSER: {message}"

        try:
            raw = backend.complete(full_prompt)
            # Strip markdown fences if model wraps with ```json...```
            raw = re.sub(r"^```(?:json)?\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)

            parsed = json.loads(raw)
            steps = [PlanStep(**s) for s in parsed.get("steps", [])]
            self._log_interaction(state, "assistant", raw)
            logger.info(f"[{provider.upper()}] Planner proposed {len(steps)} step(s).")
            return Plan(steps=steps)

        except json.JSONDecodeError as e:
            logger.error(f"LLM returned non-JSON: {raw[:200]} — {e}")
            return Plan(steps=[])
        except Exception as e:
            logger.error(f"LLM backend error: {e}")
            return Plan(steps=[])


class ExecutorAgent(BaseAgent):
    """Executes a single plan step using the Tool Registry."""
    def __init__(self):
        super().__init__(name="Executor", role="Task Execution")

    async def chat(self, step: PlanStep, state: AgentState) -> str:
        tool = registry.get_tool(step.tool_name)
        if not tool:
            msg = f"ERROR: Tool '{step.tool_name}' not found in registry."
            logger.error(msg)
            self._log_interaction(state, "tool_error", msg)
            return msg
        try:
            result = tool.execute(**step.arguments)
            result_str = json.dumps(result) if isinstance(result, dict) else str(result)
            self._log_interaction(state, "tool_result", result_str)
            return result_str
        except Exception as e:
            err = f"Execution error in '{step.tool_name}': {e}"
            logger.error(err)
            self._log_interaction(state, "tool_error", err)
            return err
