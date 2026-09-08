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
        is_ui_request = any(k in prompt_lower for k in ("layout", "screen", "ui design", "wireframe", "mockup", "interface screen", "hardware panel", "control unit"))
        is_diagram_request = any(k in prompt_lower for k in ("flowchart", "architecture diagram", "sequence diagram", "subsystem diagram", "class diagram", "state machine", "er diagram"))

        if (is_art_request or is_ui_request) and not is_diagram_request:
            sys_prompt = system_prompt or (
                "You are a World-Class Master SVG Vector Graphic Designer, CAD Draftsman & UI/UX Architect.\n"
                "CRITICAL MANDATE: When asked to design or convert a UI screen, interface, hardware panel, engineering cross-section, machine schematic, or technical pencil sketch, IMMEDIATELY generate and output the complete, high-fidelity SVG inside a ```svg ... ``` code block.\n"
                "1. Canvas & Background Contrast: ALWAYS define a solid background canvas rect (<rect width='100%' height='100%' fill='...'/>) as the very first element inside <svg>! For pencil sketches & technical drafting, use drafting vellum paper fill='#fcfbf7' with graphite/black strokes (#1a1a1a to #4a5568); for blueprints use fill='#0c2340' with white/cyan strokes; for UI dashboards use dark fill='#090d16'. Never leave the background transparent when using dark strokes.\n"
                "2. Engineering Cross-Sections & Technical Pencil Sketches: Depict the actual mechanical machinery with precision geometry (e.g. for turbofans: include full fan blading, LPC booster stages, HPC stages with stators, annular combustor with injectors, HPT and LPT stages, convergent nozzles, concentric dual-spool shafts, and mechanical bearings). Use realistic CAD/drafting cross-hatch fills (<pattern id='hatch-...' patternTransform='rotate(45)'>), graphite stroke hierarchies (0.8px to 2.5px), airflow streamlines, dimension lines, and clean callout badges. NEVER substitute crude primitive circles or placeholder boxes for real machinery.\n"
                "3. UI Screens & Hardware Panels: Depict the actual visual screen, bezel, typography, colors, status indicators, and button arrangements accurately.\n"
                "4. Always output the complete, working, valid, non-truncated ```svg ... ``` code block directly."
            )
            # Prioritize largest 120B reasoning model for rich artwork and UI mockups
            models_to_try = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]
        else:
            sys_prompt = system_prompt or (
                "You are AuraAI, an ultra-advanced futuristic desktop cognitive intelligence.\n"
                "When the user asks to diagram, explain, or architect any system process, sequence, or workflow, ALWAYS provide complete, fully closed, working Mermaid.js diagrams using ```mermaid (e.g. flowchart LR/TD, sequenceDiagram, stateDiagram-v2, erDiagram, classDiagram) or clean SVG code blocks.\n"
                "Never refuse or ask for format preferences. Never truncate or leave code blocks unclosed. Respond concisely and format beautifully with markdown."
            )
            models_to_try = ["qwen/qwen3.8-27b", "openai/gpt-oss-20b", "openai/gpt-oss-120b"]

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt},
        ]

        # 1. Primary: For diagrams, SVGs, and art/sketch requests, use Gemini by default
        if (is_art_request or is_ui_request or is_diagram_request) and pool.count("gemini") > 0:
            try:
                from ai.gemini_provider import GeminiProvider
                from ai.models import ChatMessage, ChatRequest

                gemini_p = GeminiProvider()
                chat_msgs = [
                    ChatMessage(role="system", content=sys_prompt),
                    ChatMessage(role="user", content=prompt),
                ]
                req = ChatRequest(messages=chat_msgs, max_tokens=8192, temperature=0.3)
                resp = gemini_p.chat(req)
                if resp and resp.text and resp.text.strip():
                    return resp.text.strip()
            except Exception as gemini_err:
                logger.warning(f"[FastLLMClient] Gemini diagram default notice: {gemini_err}, falling back to Groq...")

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
