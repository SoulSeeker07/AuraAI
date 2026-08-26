"""
challenge_detection.py

The ONE place that knows what a CAPTCHA / bot-wall / login-wall looks like,
and the ONE place that knows whether a navigation landed somewhere it
shouldn't have. Previously this logic was half-duplicated between
autonomous_browser.py and vision_loop.py — now everything imports from here.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any, Optional

CHALLENGE_SELECTORS = [
    (".cf-turnstile", "CLOUDFLARE_TURNSTILE"),
    ("#challenge-running", "CLOUDFLARE_CHALLENGE"),
    ("iframe[src*='challenges.cloudflare.com']", "CLOUDFLARE_TURNSTILE_IFRAME"),
    ("iframe[src*='recaptcha']", "GOOGLE_RECAPTCHA"),
    ("iframe[src*='hcaptcha']", "HCAPTCHA"),
    ("#captchacharacters", "AMAZON_BOT_CHECK"),
    ("form[action*='validateCaptcha']", "AMAZON_CAPTCHA_FORM"),
    ("input[type='password']", "LOGIN_AUTH_WALL"),
    ("input[name*='2fa']", "2FA_VERIFICATION_WALL"),
    ("input[name*='otp']", "OTP_VERIFICATION_WALL"),
]

CHALLENGE_TEXT_PATTERNS = [
    (r"verify you are human", "HUMAN_VERIFICATION"),
    (r"checking if the site connection is secure", "CLOUDFLARE_SECURITY_CHECK"),
    (r"enter the characters you see below", "IMAGE_CAPTCHA"),
    (r"prove you(?:'re| are) not a robot", "BOT_DETECTION"),
    (r"enter your 2-step verification code", "2FA_AUTHENTICATION"),
    (r"our systems have detected unusual traffic", "GOOGLE_UNUSUAL_TRAFFIC_BOT_CHECK"),
    (r"google\.com/sorry", "GOOGLE_SORRY_CAPTCHA_INTERSTITIAL"),
]

# URL fragments that mean "you already lost" — no point letting the model
# grind against these visually.
BOT_WALL_URL_PATTERNS = (
    "/static-pages/418", "captcha", "challenge", "blocked",
    "verify-human", "access-denied", "security-check", "/sorry/",
)


def detect_challenges(page: Any) -> Optional[str]:
    """Return a challenge name if the current page is a CAPTCHA/bot-wall, else None."""
    try:
        for selector, name in CHALLENGE_SELECTORS:
            try:
                if page.locator(selector).first.is_visible(timeout=400):
                    return name
            except Exception:
                continue
        text = page.content().lower()
        for pattern, name in CHALLENGE_TEXT_PATTERNS:
            if re.search(pattern, text):
                return name
    except Exception:
        pass
    return None


def url_looks_challenged(url: str) -> Optional[str]:
    """Cheap URL-only check, no DOM query needed — run this every step."""
    low = url.lower()
    for pattern in BOT_WALL_URL_PATTERNS:
        if pattern in low:
            return f"Bot-wall pattern matched ('{pattern}') at {url}"
    return None


def extract_base_domain(url: str) -> str:
    try:
        host = (urllib.parse.urlparse(url).netloc or "").lower().split(":")[0]
        for prefix in ("www.", "m.", "mobile.", "en.", "login.", "accounts."):
            if host.startswith(prefix):
                host = host[len(prefix):]
        return host
    except Exception:
        return ""


def is_valid_domain_transition(target_url: str, landed_url: str) -> bool:
    """
    Did navigation land somewhere sane, or did it get silently redirected
    to a bot-check / phishing / unrelated domain?
    """
    target = extract_base_domain(target_url)
    landed = extract_base_domain(landed_url)
    if not target or not landed:
        return True
    if "/sorry/" in landed_url:
        return False
    if target == landed or landed.endswith("." + target) or target.endswith("." + landed):
        return True
    oauth_allowlist = ("accounts.google.com", "login.microsoftonline.com", "appleid.apple.com")
    if any(h in landed_url.lower() for h in oauth_allowlist):
        return True
    return False
