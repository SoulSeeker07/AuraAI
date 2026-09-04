"""
Fast-Path Neural LLM Client for AuraAI
=====================================
Location: src/ai/fast_client.py

Provides sub-second direct LLM inference (Groq / Qwen / GPT-OSS) for instant chat
responses without waiting for heavy multi-agent desktop tool initialization.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class FastLLMClient:
    """Instant sub-second neural inference client."""

    DEFAULT_MODELS = [
        "qwen/qwen3.8-27b",
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
    ]

    @classmethod
    def query(cls, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Execute fast direct completion via Groq KeyPool with automatic failover."""
        from ai.key_pool import KeyPool

        pool = KeyPool.get_instance()
        prompt_lower = prompt.lower().strip()
        is_art_request = any(k in prompt_lower for k in ("draw", "illustration", "vector art", "sketch", "paint", "portrait", "character", "deity", "icon", "logo", "render", "artwork"))
        is_diagram_request = any(k in prompt_lower for k in ("diagram", "flowchart", "architecture", "sequence", "subsystem", "class diagram", "state machine"))

        if is_art_request and not is_diagram_request:
            sys_prompt = system_prompt or (
                "You are a World-Class Master SVG Vector Graphic Illustrator & Digital Artist.\n"
                "CRITICAL MANDATE: Never refuse a drawing request, never say 'I cannot draw pencil sketches', and never ask 'which format do you prefer?'. When asked to draw ANYTHING, IMMEDIATELY generate and output the complete, breathtaking, professional-grade SVG vector artwork inside a ```svg ... ``` block.\n"
                "1. Use rich <defs> with sophisticated multi-stop linear and radial gradients (e.g. glowing gold, metallic crimson, glowing neon, deep shading, metallic highlights).\n"
                "2. Use drop shadows and glow filters (<filter id=\"glow\">).\n"
                "3. Use intricate, realistic Bezier paths (<path d=\"M... C... Q... Z\">) for smooth curves, armor plating, contours, jewelry, glowing eyes/arc reactors, and expressive anatomy.\n"
                "4. Create a complete, stunning, layered composition with a beautiful dark-mode or thematic background (viewBox=\"0 0 800 800\").\n"
                "5. Output the complete, working, valid ```svg ... ``` code block. Never output simplistic basic primitive doodles or toy shapes."
            )
            # Prioritize largest 120B reasoning model for rich artwork
            models_to_try = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]
        else:
            sys_prompt = system_prompt or (
                "You are AuraAI, an ultra-advanced futuristic desktop cognitive intelligence.\n"
                "When the user asks to draw, diagram, explain, or architect any system, process, suit, or concept, ALWAYS provide complete, fully closed, working Mermaid.js diagrams using ```mermaid (e.g. flowchart LR, graph TD, sequenceDiagram) or clean SVG code blocks.\n"
                "Never refuse or ask for format preferences. Never truncate or leave code blocks unclosed. Respond concisely and format beautifully with markdown."
            )
            models_to_try = ["qwen/qwen3.8-27b", "openai/gpt-oss-20b", "openai/gpt-oss-120b"]

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt},
        ]

        def _call_groq(api_key: str) -> str:
            from groq import Groq
            client = Groq(api_key=api_key)

            last_err = None
            for model_name in models_to_try:
                try:
                    resp = client.chat.completions.create(
                        model=model_name,
                        messages=messages,
                        max_tokens=4096,
                        temperature=0.6,
                    )
                    content = resp.choices[0].message.content
                    if content and content.strip():
                        return content.strip()
                except Exception as model_err:
                    logger.debug(f"[FastLLMClient] Model {model_name} notice: {model_err}")
                    last_err = model_err
                    continue

            if last_err is not None:
                raise last_err
            raise RuntimeError("All Groq fast models exhausted or unavailable.")

        try:
            result = pool.execute_with_failover(_call_groq, service="groq")
            if result:
                return result
        except Exception as exc:
            logger.warning(f"[FastLLMClient] Groq KeyPool fast-path notice: {exc}")

        return f"✦ Aura Neural Engine received: '{prompt}'. Ready for multi-agent reasoning."
