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
from typing import Any, Dict, List, Optional

from browser.browser_session import BrowserSession
from browser.browser_tools import TOOL_SCHEMAS, TERMINAL_TOOLS, BrowserTools, ToolExecutionError
from browser.safety_gate import SafetyGate
from browser.paused_session import PausedSession, PausedSessionStore

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.getenv("AURA_AGENT_MODEL", "qwen/qwen3.6-27b")
DEFAULT_MAX_STEPS = 15


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
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(fn, *args, **kwargs)
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
6. CHALLENGE HANDLING: If a CAPTCHA or 2FA challenge is detected, call `ask_user` immediately so the user can complete it.
"""


def _should_keep_browser_open(goal: str, headless: bool) -> bool:
    if not headless:
        return True
    keep_keywords = ["cart", "buy", "order", "checkout", "login", "open", "keep open", "book", "reserve"]
    return any(k in goal.lower() for k in keep_keywords)


def _run_loop(
    session: BrowserSession,
    tools: BrowserTools,
    gate: SafetyGate,
    goal: str,
    messages: List[Dict[str, Any]],
    model: str,
    max_steps: int,
    step_log: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    The actual turn loop, shared by run_goal() and resume_goal(). Does NOT
    own the session's lifecycle — the caller decides whether to close it,
    based on the returned status.
    """
    from groq import Groq

    for step in range(max_steps):
        def _call_groq(api_key: str):
            c = Groq(api_key=api_key) if api_key else Groq()
            return c.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
                temperature=0.0,
            )

        try:
            from ai.key_pool import KeyPool
            resp = KeyPool.get_instance().execute_with_failover(_call_groq, service="groq")
        except Exception as ex:
            logger.debug("[AgentLoop] KeyPool failover fallback: %s", ex)
            resp = _call_groq(os.getenv("GROQ_API_KEY", ""))

        msg = resp.choices[0].message
        asst_msg = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            asst_msg["tool_calls"] = msg.tool_calls
        messages.append(asst_msg)

        if not msg.tool_calls:
            messages.append({"role": "user", "content": "Please call a tool to make progress, or `done`/`ask_user` if finished."})
            continue

        for tool_call in msg.tool_calls:
            name = tool_call.function.name
            if name.startswith("functions."):
                name = name[len("functions."):]
            try:
                args = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            logger.info("[AgentLoop] step=%d tool=%s args=%s", step, name, args)

            if name in TERMINAL_TOOLS:
                step_log.append({"step": step, "tool": name, "args": args})
                status = "SUCCESS" if name == "done" else "ASK_USER"
                summary = args.get("summary") if name == "done" else args.get("reason")
                keep_open = _should_keep_browser_open(goal, session.headless)
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
                        )
                    )
                return {"status": status, "summary": summary, "url": tools.page.url, "steps": step_log, "close_session": not keep_open}

            gate_result = gate.check(name, args, goal, authorized=False)
            if not gate_result["allowed"]:
                step_log.append({"step": step, "tool": name, "args": args, "status": "BLOCKED"})
                ticket_id = gate_result["ticket_id"]
                remaining_steps = max(max_steps - step - 1, 5)
                # Keep the browser open on the exact page where the risky
                # action was proposed, so confirm_ticket() can replay THIS
                # exact call — no re-derivation, no risk of the model
                # phrasing it differently on redemption.
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
                    )
                )
                return {
                    "status": "REQUIRE_AUTH_TICKET",
                    "summary": gate_result["message"],
                    "ticket_id": ticket_id,
                    "url": tools.page.url,
                    "steps": step_log,
                    "close_session": False,  # browser must stay open for confirm_ticket() to replay against
                }

            clean_args = {k: v for k, v in args.items() if v is not None}
            try:
                result = getattr(tools, name)(**clean_args)
            except ToolExecutionError as ex:
                result = {"error": str(ex)}
            except Exception as ex:
                result = {"error": f"Tool execution failed: {ex}"}

            gate.record_outcome(name, args, gate_result["risk"], "EXECUTED")
            step_log.append({"step": step, "tool": name, "args": args, "result": result})
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(result)})

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

    return {"status": "MAX_STEPS", "summary": f"Reached {max_steps} steps without finishing.", "url": tools.page.url, "steps": step_log, "close_session": True}


@_safe_thread_runner
def run_goal(goal: str, start_url: Optional[str] = None, max_steps: int = DEFAULT_MAX_STEPS, model: str = DEFAULT_MODEL) -> Dict[str, Any]:
    """Start a brand-new goal. Returns the same result shape as resume_goal()."""
    gate = SafetyGate()
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"GOAL: {goal}"},
    ]
    step_log: List[Dict[str, Any]] = []

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
                )
            )
            return {
                "status": "HAND_BACK_TO_USER",
                "summary": "Challenge detected on start page — browser left open.",
                "url": snapshot.get("url"),
                "steps": step_log,
            }

    result = _run_loop(session, tools, gate, goal, messages, model, max_steps, step_log)
    if result.pop("close_session", True):
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
        # This pause is a safety-gate block, not a CAPTCHA — "resume" is the
        # wrong verb for it. Put it back untouched and point the user at
        # the right command instead of silently re-triggering the same
        # block and minting an orphaned second ticket.
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
        paused.session, tools, gate, paused.goal, paused.messages, paused.model,
        paused.max_steps_remaining, paused.step_log,
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
            )
        )
        return {
            "status": "HAND_BACK_TO_USER",
            "summary": f"Challenge detected right after the confirmed action ({result.get('challenge_detected')}).",
            "url": result.get("url"),
            "steps": paused.step_log,
        }

    final = _run_loop(
        paused.session, tools, gate, paused.goal, paused.messages, paused.model,
        paused.max_steps_remaining, paused.step_log,
    )
    if final.pop("close_session", True):
        paused.session.__exit__(None, None, None)
    return final
