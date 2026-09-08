"""
agent_loop.py

Replaces autonomous_browser.py::run_autonomous_goal AND vision_loop.py's
_run_sync with one thing: a model that gets a goal, sees tool results in
plain text/JSON (not screenshots it has to pixel-guess against), and picks
its next tool call using real function-calling.

The browser is only closed on genuinely terminal outcomes
(SUCCESS / ASK_USER / MAX_STEPS / REQUIRE_AUTH_TICKET). On
HAND_BACK_TO_USER (CAPTCHA/2FA), the session is handed to
PausedSessionStore and left OPEN so the user can actually solve the
challenge in it, and resume_goal() picks the exact same browser + message
history back up afterward instead of starting over.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import functools
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from browser.browser_session import BrowserSession
from browser.browser_tools import TOOL_SCHEMAS, TERMINAL_TOOLS, BrowserTools, ToolExecutionError
from browser.safety_gate import SafetyGate
from browser.paused_session import PausedSession, PausedSessionStore

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER: str = os.getenv("AURA_BROWSER_PROVIDER", "gemini").lower()
DEFAULT_MODEL: str = os.getenv(
    "AURA_BROWSER_MODEL",
    "gemini-3.5-flash" if DEFAULT_PROVIDER == "gemini" else (os.getenv("AURA_AGENT_MODEL") or "llama-3.3-70b-versatile")
)
DEFAULT_MAX_STEPS = 15


_BROWSER_THREAD_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="AuraBrowserWorker")


def _safe_thread_runner(fn):
    """
    If the caller is inside an active asyncio event loop (e.g. FastAPI / ConversationEngine async loop),
    runs the synchronous Playwright function in a dedicated worker thread to avoid
    'Playwright Sync API inside the asyncio loop' runtime errors.
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            future = _BROWSER_THREAD_POOL.submit(fn, *args, **kwargs)
            return future.result()
        return fn(*args, **kwargs)

    return wrapper

SYSTEM_PROMPT = """You are AuraAI's Autonomous Web Agent. You control a real browser using tools to fulfill user goals end-to-end.

Key Directives:
1. CLEAN SEARCH KEYWORDS: When searching on Amazon, Flipkart, Google, YouTube, or GitHub, extract ONLY the clean product name or subject (e.g. for "add s24 ultra to cart in flipkart", the search keyword is "Samsung Galaxy S24 Ultra" or "S24 Ultra"). NEVER type action commands like "add", "to cart", "buy", "find" into the search box or URL!
2. DIRECT SEARCH FAST-PATH:
   - Flipkart: `https://www.flipkart.com/search?q=Clean+Product+Name`
   - Amazon: `https://www.amazon.in/s?k=Clean+Product+Name`
   - YouTube: `https://www.youtube.com/results?search_query=Clean+Search+Query`
3. END-TO-END AUTONOMOUS EXECUTION:
   - If the user asks to "add to cart", "buy", or "open":
     1. Search for the clean product name.
     2. Click the matching product card/title to navigate to the product page.
     3. Locate and click the "Add to Cart" or "Buy Now" button.
     4. Confirm the action and call `done` with a summary of the item added.
   - NEVER stop on search results and give the user step-by-step instructions on how to do it manually! You are an autonomous agent — execute the clicks yourself.
4. TAB RESILIENCE: E-commerce sites like Flipkart/Amazon often open product pages in a new browser tab. Your tools automatically target the active frontmost tab.
5. DECISIVENESS: As soon as you see the target item, link, or "Add to Cart" button, call `click` immediately.
6. CART VERIFICATION: When adding an item to cart, verify that 'Added to Cart' is displayed or the cart count is at least 1. If you navigate to the cart page and find 'Your Amazon Cart is empty', click the 'Add to cart' button next to the item in your recent history or return to the product page and click 'Add to Cart' again to ensure it is actually in the cart before calling done.
7. CHALLENGE HANDLING: If a CAPTCHA or 2FA challenge is detected, call `ask_user` immediately so the user can complete it.
"""


def _should_keep_browser_open(goal: str, headless: bool) -> bool:
    # Always keep the browser open when visible so the user can use and view the webpage
    if not headless:
        return True
    keep_keywords = ["cart", "buy", "order", "checkout", "login", "open", "keep open", "book", "reserve", "instagram", "youtube", "flipkart", "amazon"]
    return any(k in goal.lower() for k in keep_keywords)


class GeminiTurnRunner:
    """
    Stateful Gemini Chat turn runner using Google GenAI SDK and KeyPool.
    Maintains chat history (including thought_signature and FunctionCall parts)
    and enables multi-turn function calling with failover across the key pool.
    """
    def __init__(self, model: str, system_prompt: str, history: Optional[List[Any]] = None):
        from ai.key_pool import KeyPool
        from google.genai import types

        self.model = model
        self.system_prompt = system_prompt
        self.history: List[Any] = list(history or [])
        self._kp = KeyPool.get_instance()

        all_decls = []
        for t in TOOL_SCHEMAS:
            fn_dict = t.get("function", t)
            fn_decl = types.FunctionDeclaration(
                name=fn_dict.get("name"),
                description=fn_dict.get("description", ""),
                parameters=fn_dict.get("parameters", {}),
            )
            all_decls.append(fn_decl)

        self._tools = [types.Tool(function_declarations=all_decls)]
        self._config = types.GenerateContentConfig(
            system_instruction=self.system_prompt,
            temperature=0.0,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            tools=self._tools,
        )

    def send(self, message_or_parts: Any) -> tuple[str, list[tuple[str, dict]], float]:
        from google import genai

        t0 = time.perf_counter()

        def _op(key: str):
            client = genai.Client(api_key=key)
            chat = client.chats.create(
                model=self.model,
                history=self.history,
                config=self._config,
            )
            resp = chat.send_message(message_or_parts)
            return resp, chat.get_history()

        resp, new_history = self._kp.execute_with_failover(_op, service="gemini")
        self.history = new_history
        latency_s = round(time.perf_counter() - t0, 2)

        text = ""
        tool_calls: list[tuple[str, dict]] = []
        if resp.candidates and resp.candidates[0].content and resp.candidates[0].content.parts:
            for part in resp.candidates[0].content.parts:
                if getattr(part, "text", None):
                    text += part.text
                if getattr(part, "function_call", None):
                    fc = part.function_call
                    name = fc.name
                    if name.startswith("functions."):
                        name = name[len("functions."):]
                    args = dict(fc.args) if hasattr(fc.args, "items") else (fc.args or {})
                    tool_calls.append((name, args))

        return text, tool_calls, latency_s


def _run_loop(
    session: BrowserSession,
    tools: BrowserTools,
    gate: SafetyGate,
    goal: str,
    messages: List[Dict[str, Any]],
    model: str,
    max_steps: int,
    step_log: List[Dict[str, Any]],
    candidate_trace_id: Optional[str] = None,
    provider: str = DEFAULT_PROVIDER,
    gemini_history: Optional[List[Any]] = None,
    pending_fn_responses: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """
    The actual turn loop, shared by run_goal() and resume_goal(). Does NOT
    own the session's lifecycle — the caller decides whether to close it,
    based on the returned status.
    """
    from browser.experience_store import BrowserExperienceStore

    is_gemini = (provider == "gemini") or ("gemini" in (model or "").lower())

    gemini_runner: Optional[GeminiTurnRunner] = None
    next_gemini_input: Any = None
    groq_provider = None

    if is_gemini:
        gemini_runner = GeminiTurnRunner(model=model, system_prompt=SYSTEM_PROMPT, history=gemini_history)
        if pending_fn_responses:
            next_gemini_input = pending_fn_responses if len(pending_fn_responses) > 1 else pending_fn_responses[0]
        elif not gemini_runner.history:
            user_texts = [m["content"] for m in messages if m.get("role") == "user" and isinstance(m.get("content"), str)]
            next_gemini_input = "\n\n".join(user_texts) if user_texts else f"GOAL: {goal}"
        else:
            next_gemini_input = messages[-1]["content"] if messages else "Resume execution."
    else:
        from ai.groq_provider import GroqProvider
        groq_provider = GroqProvider()

    consecutive_no_tool_calls = 0

    for step in range(max_steps):
        # 5k+ Token Auto-Escalation Guardrail:
        # If running on Groq and accumulated DOM/message context reaches or exceeds 5,000 tokens (~20,000 chars),
        # auto-escalate directly to Gemini 3.5 Flash to prevent Groq TPM throttling and latency degradation.
        if not is_gemini:
            total_chars = sum(len(str(m.get("content", "") or "")) for m in messages if isinstance(m, dict))
            est_tokens = total_chars // 4
            if est_tokens >= 5000:
                logger.info(
                    "[AgentLoop] Context size (%d tokens >= 5000) reached Groq limit. Auto-escalating to Gemini 3.5 Flash.",
                    est_tokens
                )
                is_gemini = True
                model = os.getenv("AURA_BROWSER_MODEL", "gemini-3.5-flash")
                gemini_runner = GeminiTurnRunner(model=model, system_prompt=SYSTEM_PROMPT)
                user_texts = [m["content"] for m in messages if m.get("role") == "user" and isinstance(m.get("content"), str)]
                next_gemini_input = "\n\n".join(user_texts) if user_texts else f"GOAL: {goal}"

        t_llm_start = time.perf_counter()

        if is_gemini:
            try:
                text_content, tool_calls_list, llm_latency_s = gemini_runner.send(next_gemini_input)
            except Exception as ex:
                logger.error("[AgentLoop] Gemini turn error: %s", ex)
                raise
            used_model = model
            asst_msg = {"role": "assistant", "content": text_content or ""}
            if tool_calls_list:
                asst_msg["tool_calls"] = [
                    {"id": f"call_gemini_{step}_{i}", "function": {"name": name, "arguments": json.dumps(args)}}
                    for i, (name, args) in enumerate(tool_calls_list)
                ]
            messages.append(asst_msg)
            raw_tool_calls = [(name, args, None) for name, args in tool_calls_list]
            content_reply = text_content
        else:
            try:
                resp = groq_provider.chat_with_tools(
                    messages=messages,
                    tools=TOOL_SCHEMAS,
                    model=model,
                    temperature=0.0,
                )
            except Exception as ex:
                logger.debug("[AgentLoop] Groq chat_with_tools error: %s", ex)
                raise
            llm_latency_s = round(time.perf_counter() - t_llm_start, 2)
            msg = resp.choices[0].message
            used_model = getattr(resp, "model", None) or model or "unknown"
            asst_msg = {"role": "assistant", "content": msg.content or ""}
            if msg.tool_calls:
                asst_msg["tool_calls"] = msg.tool_calls
            messages.append(asst_msg)
            content_reply = msg.content or ""
            raw_tool_calls = []
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    tc_name = tc.function.name
                    if tc_name.startswith("functions."):
                        tc_name = tc_name[len("functions."):]
                    try:
                        tc_args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        tc_args = {}
                    raw_tool_calls.append((tc_name, tc_args, getattr(tc, "id", None)))

        logger.info("[AgentLoop] step=%d model_used=%s (llm_latency=%.2fs)", step, used_model, llm_latency_s)

        if not raw_tool_calls:
            consecutive_no_tool_calls += 1
            if consecutive_no_tool_calls >= 2:
                logger.warning(
                    "[AgentLoop] NO_TOOL_CALL_ABORT goal='%s' step=%d model='%s' consecutive=%d reason='Model returned plain text without tool calls'",
                    goal, step, used_model, consecutive_no_tool_calls
                )
                return {
                    "status": "ASK_USER",
                    "summary": content_reply or "Model returned text reasoning without executing browser tools.",
                    "url": tools.page.url if tools.page else "",
                    "steps": step_log,
                    "close_session": not _should_keep_browser_open(goal, session.headless),
                }
            reprompt = "Please call a tool to make progress, or `done`/`ask_user` if finished."
            messages.append({"role": "user", "content": reprompt})
            if is_gemini:
                next_gemini_input = reprompt
            continue

        consecutive_no_tool_calls = 0
        gemini_turn_responses = []

        for name, args, tool_call_id in raw_tool_calls:
            logger.info("[AgentLoop] step=%d tool=%s args=%s", step, name, args)

            if name in TERMINAL_TOOLS:
                step_log.append({
                    "step": step,
                    "tool": name,
                    "args": args,
                    "llm_latency_s": llm_latency_s,
                    "tool_latency_s": 0.0,
                    "total_step_s": llm_latency_s,
                })
                status = "SUCCESS" if name == "done" else "ASK_USER"
                summary = args.get("summary") if name == "done" else args.get("reason")
                keep_open = _should_keep_browser_open(goal, session.headless)

                # Persist verified trace to episodic memory on verified SUCCESS
                if status == "SUCCESS":
                    try:
                        selectors = []
                        for s in step_log:
                            s_args = s.get("args", {})
                            for k in ("selector", "query", "text", "url"):
                                if s_args.get(k):
                                    selectors.append(str(s_args[k]))
                        dom = BrowserExperienceStore.get_instance()._extract_domain(tools.page.url if tools.page else goal)
                        BrowserExperienceStore.get_instance().record_trace(
                            domain=dom,
                            goal=goal,
                            action_sequence=[{"tool": s["tool"], "args": s["args"]} for s in step_log if "tool" in s],
                            selectors_used=selectors,
                            success=True,
                            confidence=1.0,
                            summary=summary or "",
                        )
                    except Exception as ex:
                        logger.debug("[AgentLoop] Experience recording notice: %s", ex)

                screenshot_path = None
                try:
                    if tools.page:
                        import uuid
                        from vision.screenshot_manager import ScreenshotManager
                        sm = ScreenshotManager()
                        ss_file = f"browser_verification_{int(time.time())}_{uuid.uuid4().hex[:6]}.png"
                        save_path = sm._get_save_path(ss_file)
                        tools.page.screenshot(path=save_path)
                        screenshot_path = save_path
                except Exception as ss_ex:
                    logger.debug("[AgentLoop] Completion screenshot capture failed: %s", ss_ex)

                if keep_open:
                    PausedSessionStore.get_instance().save(
                        PausedSession(
                            session=session,
                            messages=messages,
                            goal=goal,
                            model=model,
                            max_steps_remaining=max(max_steps - step - 1, 5),
                            challenge_type=None,
                            step_log=step_log,
                            provider="gemini" if is_gemini else "groq",
                            gemini_history=gemini_runner.history if is_gemini else None,
                        )
                    )
                return {
                    "status": status,
                    "summary": summary,
                    "url": tools.page.url if tools.page else "",
                    "screenshot_path": screenshot_path,
                    "steps": step_log,
                    "close_session": not keep_open,
                }

            gate_result = gate.check(name, args, goal, authorized=False)
            if not gate_result["allowed"]:
                step_log.append({"step": step, "tool": name, "args": args, "status": "BLOCKED"})
                ticket_id = gate_result["ticket_id"]
                remaining_steps = max(max_steps - step - 1, 5)
                PausedSessionStore.get_instance().save(
                    PausedSession(
                        session=session,
                        messages=messages,
                        goal=goal,
                        model=model,
                        max_steps_remaining=remaining_steps,
                        challenge_type=None,
                        step_log=step_log,
                        pending_ticket_id=ticket_id,
                        pending_tool={"tool": name, "args": args},
                        provider="gemini" if is_gemini else "groq",
                        gemini_history=gemini_runner.history if is_gemini else None,
                    )
                )
                return {
                    "status": "REQUIRE_AUTH_TICKET",
                    "summary": gate_result["message"],
                    "ticket_id": ticket_id,
                    "url": tools.page.url,
                    "steps": step_log,
                    "close_session": False,
                }

            clean_args = {k: v for k, v in args.items() if v is not None}
            failure_type = None
            t_tool_start = time.perf_counter()
            try:
                result = getattr(tools, name)(**clean_args)
            except ToolExecutionError as ex:
                result = {"error": str(ex)}
                failure_type = "hard"
            except Exception as ex:
                result = {"error": f"Tool execution failed: {ex}"}
                failure_type = "soft"
            tool_latency_s = round(time.perf_counter() - t_tool_start, 2)

            if isinstance(result, dict) and "error" in result and candidate_trace_id and failure_type:
                BrowserExperienceStore.get_instance().discount_trace(
                    candidate_trace_id, failure_type=failure_type, reason=f"Tool '{name}' error: {result['error']}"
                )

            gate.record_outcome(name, args, gate_result["risk"], "EXECUTED")
            step_log.append({
                "step": step,
                "tool": name,
                "args": args,
                "llm_latency_s": llm_latency_s,
                "tool_latency_s": tool_latency_s,
                "total_step_s": round(llm_latency_s + tool_latency_s, 2),
                "result": {k: v for k, v in result.items() if k != "screenshot_url"} if isinstance(result, dict) else result,
            })

            clean_res = {k: v for k, v in result.items() if k != "screenshot_url"} if isinstance(result, dict) else result

            if is_gemini:
                from google.genai import types
                fn_part = types.Part.from_function_response(name=name, response={"result": clean_res})
                gemini_turn_responses.append(fn_part)
                if isinstance(result, dict) and result.get("screenshot_url"):
                    try:
                        import base64
                        raw_b64 = result["screenshot_url"].split(",", 1)[1] if "," in result["screenshot_url"] else result["screenshot_url"]
                        img_bytes = base64.b64decode(raw_b64)
                        img_part = types.Part.from_bytes(data=img_bytes, mime_type="image/png")
                        gemini_turn_responses.append(img_part)
                    except Exception as img_ex:
                        logger.debug("[AgentLoop] Screenshot part parsing error: %s", img_ex)
                messages.append({"role": "tool", "tool_call_id": f"call_gemini_{step}", "content": json.dumps(clean_res)})
            else:
                if isinstance(result, dict) and result.get("screenshot_url"):
                    img_url = result["screenshot_url"]
                    messages.append({"role": "tool", "tool_call_id": tool_call_id or f"call_{step}", "content": json.dumps(clean_res)})
                    messages.append({
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Screenshot of {tools.page.url}: {result.get('note', '')}"},
                            {"type": "image_url", "image_url": {"url": img_url}},
                        ],
                    })
                else:
                    messages.append({"role": "tool", "tool_call_id": tool_call_id or f"call_{step}", "content": json.dumps(result)})

            if isinstance(result, dict) and result.get("challenge_detected"):
                remaining_steps = max_steps - step - 1
                PausedSessionStore.get_instance().save(
                    PausedSession(
                        session=session,
                        messages=messages,
                        goal=goal,
                        model=model,
                        max_steps_remaining=max(remaining_steps, 5),
                        challenge_type=result.get("challenge_detected"),
                        step_log=step_log,
                        provider="gemini" if is_gemini else "groq",
                        gemini_history=gemini_runner.history if is_gemini else None,
                        pending_fn_responses=gemini_turn_responses if is_gemini else None,
                    )
                )
                logger.warning("[AgentLoop] Hand-back: %s at %s — browser left OPEN for user.", result.get("challenge_detected"), result.get("url"))
                return {
                    "status": "HAND_BACK_TO_USER",
                    "summary": (
                        f"Security/CAPTCHA challenge detected ({result.get('challenge_detected')}). "
                        f"The browser window is open — please resolve it there, then say 'resume'."
                    ),
                    "url": result.get("url"),
                    "steps": step_log,
                    "close_session": False,
                }

        if is_gemini:
            next_gemini_input = gemini_turn_responses if len(gemini_turn_responses) > 1 else (gemini_turn_responses[0] if gemini_turn_responses else "Continue.")

    return {"status": "MAX_STEPS", "summary": f"Reached {max_steps} steps without finishing.", "url": tools.page.url, "steps": step_log, "close_session": True}


@_safe_thread_runner
def run_goal(
    goal: str,
    start_url: Optional[str] = None,
    max_steps: int = DEFAULT_MAX_STEPS,
    model: Optional[str] = None,
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    """Start a brand-new goal. Returns the same result shape as resume_goal()."""
    gate = SafetyGate()
    resolved_provider = (provider or DEFAULT_PROVIDER).lower()
    if model:
        if "gemini" in model.lower():
            resolved_provider = "gemini"
        elif any(k in model.lower() for k in ["llama", "groq", "mixtral", "deepseek"]):
            resolved_provider = "groq"
    else:
        model = os.getenv("AURA_BROWSER_MODEL", "gemini-3.5-flash" if resolved_provider == "gemini" else "llama-3.3-70b-versatile")

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"GOAL: {goal}"},
    ]
    step_log: List[Dict[str, Any]] = []

    # Episodic Memory Recall (Candidate Hypothesis)
    candidate_trace_id = None
    try:
        from browser.experience_store import BrowserExperienceStore
        exp_store = BrowserExperienceStore.get_instance()
        candidate = exp_store.retrieve_trace(domain="", goal=goal)
        if candidate:
            candidate_trace_id = candidate.get("trace_id")
            steps_preview = "\n".join(
                [f"   - Step {i+1}: `{a.get('tool')}` {json.dumps(a.get('args', {}))}" for i, a in enumerate(candidate.get("action_sequence", [])[:4])]
            )
            messages.append({
                "role": "user",
                "content": (
                    f"💡 [Episodic Memory Candidate Trace — Domain: {candidate.get('domain')}, Confidence: {candidate.get('confidence'):.2f}]\n"
                    f"Prior verified trace hypothesis:\n{steps_preview}\n\n"
                    "⚠️ CLOSED-LOOP VERIFICATION MANDATE: Treat this strictly as a candidate hypothesis. You MUST observe the live DOM and verify before every click/type action. Never assume cached selectors still exist without live confirmation."
                ),
            })
    except Exception as ex:
        logger.debug("[AgentLoop] Experience recall notice: %s", ex)

    session = BrowserSession()
    session.__enter__()
    tools = BrowserTools(session)

    if start_url:
        snapshot = tools.navigate(start_url)
        messages.append({"role": "user", "content": f"Starting page: {json.dumps(snapshot)}"})
        if snapshot.get("challenge_detected"):
            PausedSessionStore.get_instance().save(
                PausedSession(
                    session=session,
                    messages=messages,
                    goal=goal,
                    model=model,
                    max_steps_remaining=max_steps,
                    challenge_type=snapshot.get("challenge_detected"),
                    step_log=step_log,
                    provider=resolved_provider,
                )
            )
            return {
                "status": "HAND_BACK_TO_USER",
                "summary": "Challenge detected on start page — browser left open.",
                "url": snapshot.get("url"),
                "steps": step_log,
            }

    result = _run_loop(
        session=session,
        tools=tools,
        gate=gate,
        goal=goal,
        messages=messages,
        model=model,
        max_steps=max_steps,
        step_log=step_log,
        candidate_trace_id=candidate_trace_id,
        provider=resolved_provider,
    )
    if not session.headless:
        result["close_session"] = False

    if result.pop("close_session", False):
        session.__exit__(None, None, None)
    return result


@_safe_thread_runner
def resume_goal() -> Dict[str, Any]:
    """
    Continue a previously paused goal in the SAME browser window with the
    SAME conversation history — call this from the `resume_browser` intent
    once the user says they've solved the challenge.
    """
    paused = PausedSessionStore.get_instance().take()
    if paused is None:
        return {"status": "NO_PAUSED_SESSION", "summary": "No paused browser session found (or it expired)."}

    if paused.pending_ticket_id is not None:
        PausedSessionStore.get_instance().save(paused)
        return {
            "status": "REQUIRE_AUTH_TICKET",
            "summary": f"This session is waiting on a confirmation, not a CAPTCHA — run `aura confirm {paused.pending_ticket_id}` instead of resume.",
            "ticket_id": paused.pending_ticket_id,
        }

    gate = SafetyGate()
    tools = BrowserTools(paused.session)
    paused.messages.append({"role": "user", "content": "The challenge has been resolved. Continue the goal."})

    result = _run_loop(
        session=paused.session,
        tools=tools,
        gate=gate,
        goal=paused.goal,
        messages=paused.messages,
        model=paused.model,
        max_steps=paused.max_steps_remaining,
        step_log=paused.step_log,
        provider=paused.provider,
        gemini_history=paused.gemini_history,
        pending_fn_responses=paused.pending_fn_responses,
    )
    if result.pop("close_session", True):
        paused.session.__exit__(None, None, None)
    return result


@_safe_thread_runner
def confirm_ticket(ticket_id: str) -> Dict[str, Any]:
    """
    Redeem a ticket issued by a previous run() call. Replays the exact blocked
    tool call on the already-open browser session, then lets the agent loop continue.
    """
    ticket_id = ticket_id.strip().upper()
    gate = SafetyGate()
    disk_ticket = gate.redeem_ticket(ticket_id)
    if not disk_ticket:
        return {"status": "INVALID_TICKET", "summary": f"Ticket {ticket_id} not found or expired."}

    paused = PausedSessionStore.get_instance().take_for_ticket(ticket_id)
    if paused is None:
        return {
            "status": "INVALID_TICKET",
            "summary": (
                f"Ticket {ticket_id} was valid, but its paused browser session is no longer "
                f"available (it may have been replaced by a newer goal or expired). Please retry the goal."
            ),
        }

    tools = BrowserTools(paused.session)
    tool_name = paused.pending_tool["tool"]
    tool_args = paused.pending_tool["args"]
    logger.info("[AgentLoop] Ticket %s confirmed — replaying %s(%s)", ticket_id, tool_name, tool_args)

    try:
        result = getattr(tools, tool_name)(**tool_args)
    except ToolExecutionError as ex:
        result = {"error": str(ex)}
    except Exception as ex:
        result = {"error": f"Tool execution failed: {ex}"}

    gate.record_outcome(tool_name, tool_args, "HIGH", "EXECUTED_VIA_TICKET")
    paused.step_log.append({"tool": tool_name, "args": tool_args, "result": result, "status": "EXECUTED_VIA_TICKET"})
    paused.messages.append({"role": "user", "content": f"[Authorized] Executed {tool_name}({tool_args}): {json.dumps(result)}"})

    pending_fn_resp = None
    if paused.provider == "gemini":
        from google.genai import types
        clean_res = {k: v for k, v in result.items() if k != "screenshot_url"} if isinstance(result, dict) else result
        pending_fn_resp = [types.Part.from_function_response(name=tool_name, response={"result": clean_res})]

    if isinstance(result, dict) and result.get("challenge_detected"):
        PausedSessionStore.get_instance().save(
            PausedSession(
                session=paused.session,
                messages=paused.messages,
                goal=paused.goal,
                model=paused.model,
                max_steps_remaining=paused.max_steps_remaining,
                challenge_type=result.get("challenge_detected"),
                step_log=paused.step_log,
                provider=paused.provider,
                gemini_history=paused.gemini_history,
                pending_fn_responses=pending_fn_resp,
            )
        )
        return {
            "status": "HAND_BACK_TO_USER",
            "summary": f"Challenge detected right after the confirmed action ({result.get('challenge_detected')}).",
            "url": result.get("url"),
            "steps": paused.step_log,
        }

    final = _run_loop(
        session=paused.session,
        tools=tools,
        gate=gate,
        goal=paused.goal,
        messages=paused.messages,
        model=paused.model,
        max_steps=paused.max_steps_remaining,
        step_log=paused.step_log,
        provider=paused.provider,
        gemini_history=paused.gemini_history,
        pending_fn_responses=pending_fn_resp,
    )
    if final.pop("close_session", True):
        paused.session.__exit__(None, None, None)
    return final
