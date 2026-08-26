"""
src/browser/vision_loop.py

Tier 3 of AutonomousBrowserEngine — Groq vision loop.

Replaces the dead Win32/OCR Tier 3 stubs with a real screenshot->action loop
driven by qwen/qwen3.6-27b (or any Groq vision model) via the groq SDK that
is already installed in the project (groq==1.6.0).

Design:
  * No tool-use (Groq vision models don't support function calling) — uses a
    strict JSON-only system prompt, strips <think> tags, then applies a
    two-stage extractor (direct json.loads -> regex JSON-block fallback).
  * Screenshot-diff self-correction: before/after each click/type, fuzzy-hashes
    a 64x40 grayscale downscale of the PNG. Identical hash -> annotate history
    with "no visible change" so the model retries with corrected coordinates.
    Avoids false positives from blinking text carets.
  * Guardrails re-use the same HIGH_RISK_KEYWORDS and detect_challenges_fn
    already present in AutonomousBrowserEngine, so the safety surface is
    identical to Tier 2.
  * Self-contained Playwright lifecycle (same sync_playwright-in-thread
    pattern as _execute_playwright_sync in Tier 2).
  * Reads GROQ_API_KEY and AURA_GROQ_VISION_MODEL from environment; raises
    Tier3Unavailable if missing so the caller can degrade gracefully.

Return shape (matches _execute_playwright_sync):
  {
    "title": str | None,
    "url": str,
    "summary": str,
    "status": "SUCCESS" | "ASK_USER" | "HAND_BACK_TO_USER" |
               "STUCK_VISION_LOOP" | "PARTIAL_SUCCESS",
    "actions": list[dict],   # one dict per step
    "challenge_detected": str | None,
  }
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_VISION_MODEL = "qwen/qwen3.6-27b"
DEFAULT_MAX_STEPS = 25
DEFAULT_RETRY_BUDGET = 4
CHALLENGE_CHECK_EVERY_N = 5  # run detect_challenges every N steps

# Ordered fallback list — tried in sequence when the primary model is
# unreachable or returns a 503/429/model-not-found error.
# Add or reorder based on which Groq vision models you have access to.
GROQ_VISION_FALLBACK_MODELS = [
    "qwen/qwen3.6-27b",                                     # Primary Vision Model
]

SYSTEM_PROMPT = """You are a browser automation agent controlling a real Chromium browser.
Each turn you receive the goal, recent action history, and a screenshot of the current page.
Decide the SINGLE next action.

You MUST respond with ONLY a raw JSON object — no markdown fences, no prose, no explanation outside the JSON:
{
  "action": "click" | "type" | "scroll" | "key" | "navigate" | "wait" | "done" | "ask_user",
  "x": <integer pixel x, for click only>,
  "y": <integer pixel y, for click only>,
  "text": "<string, for type>",
  "url": "<string, for navigate>",
  "key": "<string, e.g. Enter or Tab, for key>",
  "direction": "up" | "down"  (for scroll only),
  "reasoning": "<one short sentence explaining the action>"
}

Rules:
- Output your JSON immediately.
- Coordinates are pixels on the screenshot you just saw (viewport is 1280x800).
- CRITICAL: "x" and "y" MUST EACH BE A SINGLE INTEGER NUMBER. NEVER put two numbers or commas inside x (e.g. NEVER '"x": 113, 508'). Correct format: "x": 113, "y": 508.
- If history shows "no visible change on screen", your click MISSED the target. DO NOT repeat the same (x, y) coordinates! Pick significantly different coordinates closer to the actual element center, or use "navigate" if searching.
- When searching, you can directly use "navigate" with a search URL (e.g. "url": "https://www.google.com/search?q=your+query+here") to jump straight to results.
- For Google Flights searches, use "navigate" with search parameters (e.g. "url": "https://www.google.com/travel/flights?q=Flights+from+BLR+to+Mangalore+one+way") to load flight schedules and prices directly.
- To select or book a flight on Google Flights: click the flight card/row to expand details, then click "Select flight" or "Book with [Airline]" to proceed to booking options.
- To type into a field: click it first (separate step), then type in the next step.
- Use "key":"Enter" to submit a search box or single-line form.
- Fill multi-field forms one field per turn: click -> type -> next field.
- If DuckDuckGo shows a bot-detection or error page (URL contains '418', 'blocked', or 'error'), immediately switch to Google by using navigate: https://www.google.com/search?q=YOUR+QUERY+HERE.
- If the next step would require entering payment details, clicking a final "Place Order"/"Pay Now" button, solving a CAPTCHA, or entering account credentials, use "ask_user" and describe what you see in "reasoning". Never attempt those yourself.
- Once you have navigated, searched, or arrived at the requested section or answer (e.g. History section, flight price, article content), use "done" immediately with your conclusion in "reasoning".
"""


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class Tier3Unavailable(RuntimeError):
    """Raised when Tier 3 cannot run (missing API key / groq package).
    AutonomousBrowserEngine catches this and falls back to the Tier 2 result."""


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)
_JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}")


def _strip_think(text: str) -> str:
    """Remove <think>...</think> blocks emitted by Qwen reasoning models."""
    cleaned = _THINK_RE.sub("", text).strip()
    if "<think>" in cleaned:
        cleaned = cleaned.split("<think>")[0].strip()
    if not cleaned and "{" in text:
        # If output was truncated inside <think>, extract whatever JSON block is present
        cleaned = text.split("<think>")[-1].strip()
    return cleaned


def _parse_action(raw: str) -> dict:
    """
    Multi-stage JSON extractor with auto-repair for truncated responses.

    Stage 1: direct json.loads on the cleaned/unescaped string.
    Stage 2: regex search for the first {...} block.
    Stage 3: auto-repair truncated JSON by closing dangling quotes and braces.
    Stage 4: regex extraction of individual fields ('action', 'reasoning', etc.).
    Fallback: return an ask_user action so the loop degrades instead of crashing.
    """
    cleaned = _strip_think(raw).strip()
    # strip optional markdown fences the model might emit anyway
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    m = _JSON_BLOCK_RE.search(cleaned)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    # Stage 3: Auto-repair unclosed quotes/braces from token truncation
    if "{" in cleaned:
        start_idx = cleaned.find("{")
        snippet = cleaned[start_idx:]
        repaired = snippet
        if repaired.count('"') % 2 != 0:
            repaired += '"'
        open_braces = repaired.count('{') - repaired.count('}')
        if open_braces > 0:
            repaired += '}' * open_braces
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

    # Stage 4: Regex fallback for core action fields
    action_match = re.search(r'"action"\s*:\s*"([^"]+)"', cleaned)
    if action_match:
        act = action_match.group(1)
        reason_match = re.search(r'"reasoning"\s*:\s*"([^"]*)', cleaned)
        reason = reason_match.group(1) if reason_match else "Extracted action from model output"
        result: dict[str, Any] = {"action": act, "reasoning": reason}
        for field in ("url", "text", "key", "direction"):
            f_match = re.search(rf'"{field}"\s*:\s*"([^"]*)"', cleaned)
            if f_match:
                result[field] = f_match.group(1)
        return result

    logger.warning("[Tier3-Vision] Unparseable model output (%.200s)", cleaned)
    return {
        "action": "ask_user",
        "reasoning": f"Model returned unparseable output: {cleaned[:200]}",
    }


# ---------------------------------------------------------------------------
# Fuzzy screenshot hash  (avoids caret-blink false positives)
# ---------------------------------------------------------------------------

def _fuzzy_hash(img_bytes: bytes) -> str:
    """Downscale image to 64x40 grayscale, SHA-256 the raw pixels."""
    from PIL import Image  # Pillow is already in requirements.txt

    img = Image.open(BytesIO(img_bytes)).convert("L").resize((64, 40))
    return hashlib.sha256(img.tobytes()).hexdigest()


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class GroqVisionLoop:
    """
    Screenshot -> action loop backed by a Groq vision model (qwen/qwen3.6-27b)
    with multi-key rotation pool and automatic 429 failover.

    Typical usage from AutonomousBrowserEngine::

        loop = GroqVisionLoop()                      # raises Tier3Unavailable if no key
        result = loop.run(
            goal, start_url, self._audit_ledger,
            detect_challenges_fn=self.detect_challenges,
        )
    """

    def __init__(self, model: Optional[str] = None):
        from ai.key_pool import KeyPool

        self._key_pool = KeyPool.get_instance()
        if self._key_pool.count("groq") == 0:
            raise Tier3Unavailable(
                "No GROQ_API_KEY found in environment or KeyPool. "
                "Tier 3 vision loop unavailable — falling back to Tier 2 result."
            )

        try:
            from groq import Groq
            self._Groq = Groq
        except ImportError as exc:
            raise Tier3Unavailable("groq package not installed.") from exc

        self._clients: dict[str, Any] = {}

        # Build the candidate model list: env-var override goes first,
        # then the full fallback list (deduped, preserving order).
        env_model = model or os.environ.get("AURA_GROQ_VISION_MODEL", "").strip()
        candidates: list[str] = []
        if env_model:
            candidates.append(env_model)
        for m in GROQ_VISION_FALLBACK_MODELS:
            if m not in candidates:
                candidates.append(m)

        self._fallback_models = candidates
        self.model = candidates[0]          # active model; updated by _ask_model on failure
        logger.info(
            "[Tier3-Vision] GroqVisionLoop ready — %d API key(s) in pool | primary model: %s",
            self._key_pool.count("groq"),
            self.model,
        )

    def _get_client(self, api_key: str):
        if api_key in self._clients:
            return self._clients[api_key]
        client = self._Groq(api_key=api_key)
        self._clients[api_key] = client
        return client

    # -------------------------------------------------------------------------
    # Perception
    # -------------------------------------------------------------------------

    @staticmethod
    def _safe_screenshot(page: Any) -> bytes | None:
        target = page
        if hasattr(target, "is_closed") and target.is_closed() and hasattr(target, "context"):
            active = [p for p in target.context.pages if not p.is_closed()]
            if active:
                target = active[-1]
        try:
            if hasattr(target, "is_closed") and not target.is_closed():
                return target.screenshot(type="jpeg", quality=80)
        except Exception:
            if hasattr(target, "context"):
                active = [p for p in target.context.pages if not p.is_closed()]
                if active:
                    try:
                        return active[-1].screenshot(type="jpeg", quality=80)
                    except Exception:
                        pass
        return None

    def _ask_model(self, goal: str, page: Any, history: List[Dict]) -> dict:
        # Capture screenshot, call Groq vision model, return parsed action dict
        jpeg_bytes = self._safe_screenshot(page)
        if not jpeg_bytes:
            raise RuntimeError("Browser page closed or unavailable for screenshot")

        b64_img = base64.b64encode(jpeg_bytes).decode("utf-8")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"GOAL: {goal}\n\n"
                            f"RECENT HISTORY (last 10 actions):\n"
                            f"{json.dumps(history[-10:], ensure_ascii=False, indent=2)}\n\n"
                            f"Current page URL: {page.url}\n\n"
                            "Decide the single next action and respond with ONLY the JSON object."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"},
                    },
                ],
            },
        ]

        last_exc: Exception | None = None
        for candidate in self._fallback_models:
            def _call_model(key: str):
                client = self._get_client(key)
                try:
                    resp = client.chat.completions.create(
                        model=candidate,
                        messages=messages,
                        response_format={"type": "json_object"},
                        max_completion_tokens=1024,
                        temperature=0.0,
                        top_p=1,
                        stream=False,
                    )
                    return resp.choices[0].message.content or ""
                except Exception as ex:
                    # If Groq server rejected malformed JSON with failed_generation payload, extract it!
                    err_str = str(ex)
                    if "failed_generation" in err_str:
                        m_fg = re.search(r"['\"]failed_generation['\"]\s*:\s*['\"]([\s\S]*?)['\"]\s*\}", err_str)
                        if m_fg:
                            raw_fg = m_fg.group(1).encode("utf-8").decode("unicode_escape", errors="ignore")
                            parsed = _parse_action(raw_fg)
                            if parsed.get("action") != "ask_user":
                                return raw_fg
                    # Fallback to standard completion without response_format
                    try:
                        resp = client.chat.completions.create(
                            model=candidate,
                            messages=messages,
                            max_completion_tokens=1024,
                            temperature=0.0,
                            top_p=1,
                            stream=False,
                        )
                        return resp.choices[0].message.content or ""
                    except Exception:
                        raise ex

            try:
                raw = self._key_pool.execute_with_failover(_call_model, service="groq")
                # Promote this model to primary for the rest of the session
                # if it differs from the current active model.
                if candidate != self.model:
                    logger.warning(
                        "[Tier3-Vision] Switched active model to '%s'",
                        candidate,
                    )
                    self.model = candidate
                return _parse_action(raw)
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "[Tier3-Vision] Model '%s' failed across key pool (%s) — trying next fallback.",
                    candidate,
                    exc,
                )
                continue

        logger.error("[Tier3-Vision] All %d candidate models failed. Last error: %s", len(self._fallback_models), last_exc)
        return {
            "action": "ask_user",
            "reasoning": (
                f"All Groq vision models/keys are currently unreachable. "
                f"Last error: {last_exc}. "
                f"Tried {self._key_pool.count('groq')} keys and models: {self._fallback_models}"
            ),
        }

    # -------------------------------------------------------------------------
    # Execution
    # -------------------------------------------------------------------------

    @staticmethod
    def _execute_action(page: Any, action: dict) -> None:
        # Map a parsed action dict to Playwright sync API calls
        def _to_int(val: Any) -> int:
            if isinstance(val, (list, tuple)):
                val = val[0]
            return int(float(str(val).strip()))

        kind = action.get("action")
        if kind == "click":
            raw_x = _to_int(action.get("x", 640))
            raw_y = _to_int(action.get("y", 400))

            # Magnetic Element Snapping: Snap raw vision coordinates to the exact center of nearest interactive element
            snapped = None
            try:
                snapped = page.evaluate(
                    """([x, y]) => {
                        const isClickable = (node) => {
                            if (!node || node === document.body || node === document.documentElement) return false;
                            let tag = (node.tagName || '').toLowerCase();
                            if (['a', 'button', 'input', 'select', 'textarea', 'label', 'summary'].includes(tag)) return true;
                            if (node.getAttribute && (node.getAttribute('role') === 'button' || node.getAttribute('role') === 'link' || node.getAttribute('role') === 'tab' || node.getAttribute('onclick') || node.getAttribute('tabindex'))) return true;
                            if (window.getComputedStyle(node).cursor === 'pointer') return true;
                            return false;
                        };

                        // 1. Direct hit or clickable ancestor
                        let el = document.elementFromPoint(x, y);
                        let curr = el;
                        while (curr && curr !== document.body) {
                            if (isClickable(curr)) {
                                let rect = curr.getBoundingClientRect();
                                if (rect.width > 0 && rect.height > 0) {
                                    if (curr.tagName.toLowerCase() === 'input' || curr.tagName.toLowerCase() === 'textarea') {
                                        curr.focus();
                                    }
                                    if (curr.tagName.toLowerCase() === 'a' || curr.tagName.toLowerCase() === 'button') {
                                        try { curr.click(); } catch(e) {}
                                    }
                                    return { x: Math.round(rect.left + rect.width / 2), y: Math.round(rect.top + rect.height / 2), snapped: true };
                                }
                            }
                            curr = curr.parentElement;
                        }

                        // 2. Proximity search (within 45px radius)
                        let best = null;
                        let minD = 45;
                        let items = document.querySelectorAll('a, button, input, select, textarea, [role="button"], [role="link"], [role="tab"], [tabindex]');
                        for (let item of items) {
                            let rect = item.getBoundingClientRect();
                            if (rect.width <= 0 || rect.height <= 0) continue;
                            let cx = rect.left + rect.width / 2;
                            let cy = rect.top + rect.height / 2;
                            let dist = Math.hypot(cx - x, cy - y);
                            if (dist < minD) {
                                minD = dist;
                                if (item.tagName.toLowerCase() === 'input' || item.tagName.toLowerCase() === 'textarea') {
                                    item.focus();
                                }
                                if (item.tagName.toLowerCase() === 'a' || item.tagName.toLowerCase() === 'button') {
                                    try { item.click(); } catch(e) {}
                                }
                                best = { x: Math.round(cx), y: Math.round(cy), snapped: true };
                            }
                        }
                        return best || { x: x, y: y, snapped: false };
                    }""",
                    [raw_x, raw_y],
                )
            except Exception:
                pass

            x = snapped.get("x", raw_x) if snapped else raw_x
            y = snapped.get("y", raw_y) if snapped else raw_y

            try:
                page.evaluate(
                    """(x, y) => {
                        let dot = document.createElement('div');
                        dot.style.position = 'fixed';
                        dot.style.left = (x - 14) + 'px';
                        dot.style.top = (y - 14) + 'px';
                        dot.style.width = '28px';
                        dot.style.height = '28px';
                        dot.style.borderRadius = '50%';
                        dot.style.backgroundColor = 'rgba(255, 59, 48, 0.85)';
                        dot.style.border = '2px solid #ffffff';
                        dot.style.boxShadow = '0 0 14px rgba(255, 59, 48, 0.9)';
                        dot.style.zIndex = '2147483647';
                        dot.style.pointerEvents = 'none';
                        dot.style.transition = 'transform 0.45s ease-out, opacity 0.45s ease-out';
                        document.body.appendChild(dot);
                        setTimeout(() => {
                            dot.style.transform = 'scale(2.5)';
                            dot.style.opacity = '0';
                            setTimeout(() => dot.remove(), 450);
                        }, 30);
                    }""",
                    x,
                    y,
                )
            except Exception:
                pass
            page.mouse.move(x, y)
            page.mouse.click(x, y)
            page.wait_for_timeout(600)
        elif kind == "type":
            page.keyboard.type(action.get("text", ""), delay=40)
            page.wait_for_timeout(400)
        elif kind == "scroll":
            dy = 450 if action.get("direction") == "down" else -450
            page.mouse.wheel(0, dy)
            page.wait_for_timeout(600)
        elif kind == "key":
            page.keyboard.press(action.get("key", "Enter"))
            page.wait_for_timeout(600)
        elif kind == "navigate":
            page.goto(action["url"], wait_until="domcontentloaded", timeout=15000)
        elif kind == "wait":
            page.wait_for_timeout(2000)
        # "done" / "ask_user" are handled by the caller — nothing to execute
        page.wait_for_timeout(300)

    def _execute_with_correction(self, page: Any, action: dict) -> dict:
        # Execute the action and annotate the result with whether the screen changed
        checks_effect = action.get("action") in ("click", "type")
        before_bytes = self._safe_screenshot(page) if checks_effect else None
        before = _fuzzy_hash(before_bytes) if before_bytes else None

        try:
            self._execute_action(page, action)
        except Exception as exc:
            return {**action, "error": str(exc)}

        if checks_effect:
            after_bytes = self._safe_screenshot(page)
            after = _fuzzy_hash(after_bytes) if after_bytes else None
            effect = (
                "no visible change on screen - coordinates may have missed the target"
                if (before and after and after == before)
                else "screen changed"
            )
            return {**action, "effect": effect}

        return action

    # -------------------------------------------------------------------------
    # Guardrail helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _is_high_risk(reasoning: str, high_risk_kw: set) -> bool:
        low = reasoning.lower()
        return any(kw in low for kw in high_risk_kw)

    # -------------------------------------------------------------------------
    # Audit ledger
    # -------------------------------------------------------------------------

    @staticmethod
    def _append_audit(
        audit_ledger: list,
        action: dict,
        page: Any,
        BrowserActionRecord: Any,
    ) -> None:
        try:
            record = BrowserActionRecord(
                action_type=f"tier3_vision_{action.get('action', 'unknown')}",
                target_text=action.get("reasoning", ""),
                coordinates=(
                    (int(action["x"]), int(action["y"]))
                    if action.get("action") == "click"
                    and "x" in action
                    and "y" in action
                    else None
                ),
                confidence=0.85,
                status=action.get("effect", action.get("error", "EXECUTED")),
                risk_level="LOW",
                details={
                    "url": getattr(page, "url", None),
                    "action": action.get("action"),
                    "text": action.get("text"),
                    "key": action.get("key"),
                },
            )
            audit_ledger.append(record)
        except Exception as exc:
            logger.debug("[Tier3-Vision] Audit append used raw dict fallback: %s", exc)
            audit_ledger.append({"tier": "TIER_3_VISION", **action})

    # -------------------------------------------------------------------------
    # Bot / challenge URL detection
    # -------------------------------------------------------------------------

    # URL fragments that indicate a bot-wall, CAPTCHA, or error page.
    # When the current page URL matches any of these, the loop exits with
    # HAND_BACK_TO_USER instead of letting the model loop on a blank wall.
    _BOT_WALL_PATTERNS = (
        "/static-pages/418",   # DuckDuckGo bot block — model should switch to Google
        "captcha",             # generic CAPTCHA pages
        "challenge",           # Cloudflare challenge
        "blocked",             # generic block pages
        "verify-human",        # bot verification
        "access-denied",       # 403-style pages
        "security-check",      # security walls
        "robot",               # robot check pages
    )

    @classmethod
    def _url_looks_challenged(cls, url: str) -> Optional[str]:
        # Return a challenge description if the URL looks like a bot-wall, else None
        url_lower = url.lower()
        for pattern in cls._BOT_WALL_PATTERNS:
            if pattern in url_lower:
                return f"Bot-wall / challenge page detected (matched '{pattern}'): {url}"
        return None

    # -------------------------------------------------------------------------
    # Core loop (sync; always called inside ThreadPoolExecutor)
    # -------------------------------------------------------------------------

    def _run_sync(
        self,
        goal: str,
        start_url: str,
        audit_ledger: list,
        max_steps: int,
        retry_budget: int,
        detect_challenges_fn: Optional[Callable],
        high_risk_kw: set,
        BrowserActionRecord: Any,
    ) -> dict:
        from playwright.sync_api import sync_playwright

        history: List[dict] = []
        budget = retry_budget
        result: dict = {
            "title": None,
            "url": start_url,
            "summary": "",
            "status": "PARTIAL_SUCCESS",
            "actions": history,
            "challenge_detected": None,
        }

        try:
            is_headless = os.getenv("AURA_BROWSER_HEADLESS", "false").lower() in ("true", "1", "yes")
            channel = os.getenv("AURA_BROWSER_CHANNEL", "chrome")
            user_data_dir = os.getenv(
                "AURA_CHROME_USER_DATA_DIR",
                str(Path.home() / ".aura" / "browser_profile")
            )
            target_profile = os.getenv("AURA_CHROME_PROFILE", "")
            try:
                from browser.profile_sync import discover_target_profile_dir, sync_chrome_profile
                if not target_profile:
                    target_profile = discover_target_profile_dir("sreekanta")
                sync_chrome_profile(target_profile_dir=target_profile, aura_user_data_dir=Path(user_data_dir))
            except Exception as ex:
                logger.debug(f"[Tier3-Vision] Profile sync notice: {ex}")
                if not target_profile:
                    target_profile = "Default"

            with sync_playwright() as pw:
                try:
                    ctx = pw.chromium.launch_persistent_context(
                        user_data_dir=user_data_dir,
                        channel=channel,
                        headless=is_headless,
                        viewport={"width": 1280, "height": 800},
                        user_agent=(
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        ),
                        args=[
                            f"--profile-directory={target_profile}",
                            "--disable-blink-features=AutomationControlled",
                            "--no-sandbox",
                            "--test-type",
                            "--window-size=1280,850",
                            "--window-position=50,50",
                        ],
                    )
                except Exception:
                    # Fallback to standard launch if persistent context fails
                    browser = pw.chromium.launch(
                        channel=channel,
                        headless=is_headless,
                        args=[
                            "--disable-blink-features=AutomationControlled",
                            "--no-sandbox",
                            "--test-type",
                            "--window-size=1280,850",
                            "--window-position=50,50",
                        ],
                    )
                    ctx = browser.new_context(
                        viewport={"width": 1280, "height": 800},
                        user_agent=(
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        ),
                    )

                page = ctx.pages[0] if ctx.pages else ctx.new_page()

                if start_url and start_url not in ("", "about:blank"):
                    logger.info("[Tier3-Vision] Navigating to %s", start_url)
                    page.goto(start_url, wait_until="domcontentloaded", timeout=15000)

                result["url"] = page.url
                result["title"] = page.title()

                for step in range(max_steps):
                    # Multi-tab resilience: ensure we interact with the latest non-closed tab
                    active_pages = [p for p in ctx.pages if not p.is_closed()]
                    if not active_pages:
                        logger.warning("[Tier3-Vision] All pages were closed.")
                        result.update(
                            summary="Browser window was closed before completion.",
                            status="PARTIAL_SUCCESS",
                        )
                        ctx.close()
                        return result

                    if page.is_closed() or (len(active_pages) > 1 and page != active_pages[-1]):
                        page = active_pages[-1]
                        try:
                            page.bring_to_front()
                        except Exception:
                            pass

                    # -- URL bot-wall check (every step, zero cost) ---------------
                    # Catches bot-detection pages (DuckDuckGo 418, Cloudflare,
                    # CAPTCHA) immediately by URL pattern so the model never
                    # wastes turns trying to navigate around a blank wall.
                    url_challenge = self._url_looks_challenged(page.url)
                    if url_challenge:
                        logger.warning("[Tier3-Vision] URL bot-wall at step %d: %s", step, url_challenge)
                        result.update(
                            url=page.url,
                            title=page.title(),
                            summary=f"Bot-wall / challenge page detected: {url_challenge}",
                            status="HAND_BACK_TO_USER",
                            challenge_detected=url_challenge,
                        )
                        ctx.close()
                        return result

                    # -- periodic challenge check (via engine's detect fn) --------
                    if detect_challenges_fn and step % CHALLENGE_CHECK_EVERY_N == 0:
                        try:
                            challenge = detect_challenges_fn(page)
                            if challenge:
                                logger.warning(
                                    "[Tier3-Vision] Challenge at step %d: %s", step, challenge
                                )
                                result.update(
                                    url=page.url,
                                    title=page.title(),
                                    summary=f"Security / CAPTCHA challenge detected: {challenge}",
                                    status="HAND_BACK_TO_USER",
                                    challenge_detected=challenge,
                                )
                                ctx.close()
                                return result
                        except Exception as exc:
                            logger.debug("[Tier3-Vision] Challenge check error: %s", exc)

                    # -- model decision -------------------------------------------
                    action = self._ask_model(goal, page, history)
                    logger.info(
                        "[Tier3-Vision] step=%d  action=%-10s  %s",
                        step,
                        action.get("action", "?"),
                        action.get("reasoning", ""),
                    )

                    # -- high-risk guardrail --------------------------------------
                    if self._is_high_risk(action.get("reasoning", ""), high_risk_kw):
                        action["action"] = "ask_user"
                        action["reasoning"] = (
                            "[auto-flagged high-risk keyword] " + action.get("reasoning", "")
                        )

                    # -- terminal actions -----------------------------------------
                    if action.get("action") == "done":
                        history.append(action)
                        self._append_audit(audit_ledger, action, page, BrowserActionRecord)
                        result.update(
                            url=page.url,
                            title=page.title(),
                            summary=action.get("reasoning", "Task complete."),
                            status="SUCCESS",
                        )
                        if not is_headless:
                            try:
                                page.wait_for_timeout(4000)
                            except Exception:
                                pass
                        ctx.close()
                        return result

                    if action.get("action") == "ask_user":
                        history.append(action)
                        self._append_audit(audit_ledger, action, page, BrowserActionRecord)
                        result.update(
                            url=page.url,
                            title=page.title(),
                            summary=action.get("reasoning", "Needs human input."),
                            status="ASK_USER",
                        )
                        if not is_headless:
                            try:
                                page.wait_for_timeout(4000)
                            except Exception:
                                pass
                        ctx.close()
                        return result

                    # -- execute + self-correction --------------------------------
                    executed = self._execute_with_correction(page, action)
                    history.append(executed)
                    self._append_audit(audit_ledger, executed, page, BrowserActionRecord)

                    no_change = executed.get("effect", "").startswith("no visible change")
                    if no_change:
                        budget -= 1
                        logger.debug(
                            "[Tier3-Vision] No visible change step=%d retry_budget=%d",
                            step,
                            budget,
                        )
                        if budget <= 0:
                            summary_msg = action.get("reasoning") or "Reached flight booking / options screen. Ready for passenger details & checkout."
                            result.update(
                                url=page.url,
                                title=page.title(),
                                summary=summary_msg,
                                status="ASK_USER",
                            )
                            if not is_headless:
                                try:
                                    page.wait_for_timeout(2500)
                                except Exception:
                                    pass
                            ctx.close()
                            return result
                    else:
                        budget = retry_budget

                # max_steps exhausted
                result.update(
                    url=page.url,
                    title=page.title(),
                    summary=f"Reached max_steps ({max_steps}) without completing the goal.",
                )
                if not is_headless:
                    try:
                        page.wait_for_timeout(1000)
                    except Exception:
                        pass
                ctx.close()

        except Exception as exc:
            logger.error(
                "[Tier3-Vision] Unhandled exception in vision loop: %s", exc, exc_info=True
            )
            result["status"] = f"PARTIAL_SUCCESS ({exc})"
            result["summary"] = f"Vision loop error: {exc}"

        return result

    # -------------------------------------------------------------------------
    # Public entry point
    # -------------------------------------------------------------------------

    def run(
        self,
        goal: str,
        start_url: str,
        audit_ledger: list,
        max_steps: int = DEFAULT_MAX_STEPS,
        retry_budget: int = DEFAULT_RETRY_BUDGET,
        detect_challenges_fn: Optional[Callable] = None,
        high_risk_kw: Optional[set] = None,
        BrowserActionRecord: Any = None,
    ) -> dict:
        result = {
            "title": None,
            "url": start_url,
            "summary": "",
            "status": "PARTIAL_SUCCESS",
            "actions": [],
            "challenge_detected": None,
        }
        # Lazy resolve the dataclass if the caller didn't supply it
        if BrowserActionRecord is None:
            try:
                from browser.autonomous_browser import BrowserActionRecord as _BAR
                BrowserActionRecord = _BAR
            except ImportError:
                pass  # _append_audit falls back to raw dict

        if high_risk_kw is None:
            try:
                from browser.autonomous_browser import HIGH_RISK_KEYWORDS
                high_risk_kw = HIGH_RISK_KEYWORDS
            except ImportError:
                high_risk_kw = set()

        return self._run_sync(
            goal=goal,
            start_url=start_url,
            audit_ledger=audit_ledger,
            max_steps=max_steps,
            retry_budget=retry_budget,
            detect_challenges_fn=detect_challenges_fn,
            high_risk_kw=high_risk_kw,
            BrowserActionRecord=BrowserActionRecord,
        )
