"""
Pluggable Code Drafters
Location: src/codeact/drafters.py

Defines the CodeDrafter protocol and implementations for Groq, Antigravity CLI,
and test harnesses.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


def extract_code_block(text: str) -> str:
    """
    Extract executable Python code from markdown formatted response or raw text.
    Handles nested markdown codeblocks, sibling multi-block responses, and conversational envelopes.
    """
    text_clean = text.strip()

    # 1. Whole-response wrapped in code fence
    if text_clean.startswith("```"):
        first_nl = text_clean.find("\n")
        last_fence = text_clean.rfind("```")
        if first_nl != -1 and last_fence > first_nl and last_fence == len(text_clean) - 3:
            first_line = text_clean[:first_nl].strip().lower()
            if first_line == "```" or first_line.startswith("```python") or first_line.startswith("```py"):
                return text_clean[first_nl + 1:last_fence].strip()

    # 2. Find explicit standalone markdown python code blocks (multiline match)
    # Opening fence on its own line: ^\s*```(?:python|py)\s*$
    # Closing fence on its own line: ^\s*```\s*$
    pattern = r"(?m)^\s*```(?:python|py)\s*\n(.*?)(?:\n\s*```\s*$|\Z)"
    matches = re.findall(pattern, text_clean, re.DOTALL | re.IGNORECASE)
    if matches:
        return max(matches, key=len).strip()

    # 3. Fallback: match any standalone code block
    pattern_generic = r"(?m)^\s*```(?:[a-zA-Z0-9_-]+)?\s*\n(.*?)(?:\n\s*```\s*$|\Z)"
    matches_generic = re.findall(pattern_generic, text_clean, re.DOTALL | re.IGNORECASE)
    if matches_generic:
        return max(matches_generic, key=len).strip()

    # 4. Final fallback: standard non-greedy regex
    pattern_any = r"```(?:python)?\s*\n(.*?)```"
    matches_any = re.findall(pattern_any, text_clean, re.DOTALL | re.IGNORECASE)
    if matches_any:
        return max(matches_any, key=len).strip()

    return text_clean


@runtime_checkable
class CodeDrafter(Protocol):
    """Protocol for code synthesis engines."""

    def draft(self, prompt: str) -> str:
        """Generate Python code string from prompt."""
        ...


class GroqDrafter:
    """
    High-speed LLM code drafter using direct Groq API.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "openai/gpt-oss-120b",
        temperature: float = 0.2,
    ):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        self.model = model
        self.temperature = temperature
        self._provider = None

    def _get_provider(self):
        if self._provider is None:
            from ai.groq_provider import GroqProvider

            self._provider = GroqProvider(api_key=self.api_key, default_model=self.model)
        return self._provider

    def draft(self, prompt: str) -> str:
        from ai.models import ChatMessage, ChatRequest

        models_to_try = [self.model, "openai/gpt-oss-20b"]
        last_exc = None

        for model_name in models_to_try:
            try:
                from ai.groq_provider import GroqProvider

                provider = GroqProvider(api_key=self.api_key, default_model=model_name)
                req = ChatRequest(
                    messages=[
                        ChatMessage(
                            role="system",
                            content=(
                                "You are an expert Python code synthesizer for AuraAI. "
                                "You write clean, self-contained, robust Python scripts to create "
                                "documents, spreadsheets, presentations, charts, or perform data transformations. "
                                "CRITICAL RULES:\n"
                                "1. Return ONLY the complete, executable Python code enclosed in a ```python ... ``` block.\n"
                                "2. Do NOT include markdown explanations or chat outside the code block.\n"
                                "3. Do NOT import blocked modules (socket, requests, urllib, subprocess, ctypes, win32api, etc.).\n"
                                "4. Strictly save the final artifact to the specified output filename in the current working directory.\n"
                                "5. When writing scripts that generate markdown, documentation, or text containing quotes, code blocks, or backticks (```):\n"
                                "   - DO NOT embed raw markdown with triple-backticks directly inside Python triple-quoted string literals (''' or \"\"\"), as this causes SyntaxError.\n"
                                "   - INSTEAD, construct text content using JSON decoding (import json; content = json.loads(...)) or join a list of line strings (content = '\\n'.join([...])).\n"
                                "   - Write the file cleanly using pathlib.Path(output_filename).write_text(content, encoding='utf-8')."
                            ),
                        ),
                        ChatMessage(role="user", content=prompt),
                    ],
                    model=model_name,
                    temperature=self.temperature,
                    max_tokens=4096,
                )

                resp = provider.chat(req)
                return extract_code_block(resp.text)
            except Exception as exc:
                last_exc = exc
                if "429" in str(exc) or "rate_limit" in str(exc).lower():
                    logger.warning(f"[GroqDrafter] Model '{model_name}' rate limited (429), trying fallback...")
                    continue
                raise

        raise last_exc


class AgyDrafter:
    """
    Code drafter invoking the Antigravity (agy) CLI in plan mode.
    """

    def __init__(self, agy_client: Any | None = None):
        self._client = agy_client

    def _get_client(self):
        if self._client is None:
            from core.backends.adapters.agy_subprocess_client import (
                AgyConfig,
                AgySubprocessClient,
            )

            self._client = AgySubprocessClient(AgyConfig())
        return self._client

    def draft(self, prompt: str) -> str:
        client = self._get_client()
        full_prompt = (
            f"Generate only self-contained Python code for the following task without executing it:\n\n{prompt}\n\n"
            "Return the Python code in a ```python ... ``` block. "
            "If generating markdown/code blocks, avoid raw triple-quoted string literals; use json.loads() or '\\n'.join([...])."
        )
        res = client.run_plan(goal=full_prompt)
        raw_resp = str(res.raw.get("response", ""))
        return extract_code_block(raw_resp)


class MockDrafter:
    """
    Deterministic mock drafter for tests and simulation.
    """

    def __init__(self, script_responses: list[str] | None = None):
        self.responses = list(script_responses or [])
        self.call_count = 0
        self.prompts_received: list[str] = []

    def draft(self, prompt: str) -> str:
        self.prompts_received.append(prompt)
        if self.call_count < len(self.responses):
            resp = self.responses[self.call_count]
            self.call_count += 1
            return extract_code_block(resp)
        self.call_count += 1
        return "print('default_mock_script')"
