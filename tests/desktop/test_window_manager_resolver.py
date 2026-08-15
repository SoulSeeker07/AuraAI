"""
Unit tests for WindowManager Two-Tier App Resolver, UWP Protocols, and Web Fallbacks.
"""

from unittest.mock import MagicMock, patch
import pytest

from src.desktop.native.managers.window_manager import WindowManager
from src.desktop.native.native_result import ResultStatus


def test_tier1_fast_path_aliases():
    """Verify tier 1 fast-path phonetic and colloquial aliases resolve immediately."""
    wm = WindowManager()

    cases = [
        ("out pad", "exe", "notepad"),
        ("load pad", "exe", "notepad"),
        ("goat pad", "exe", "notepad"),
        ("note pad", "exe", "notepad"),
        ("not pad", "exe", "notepad"),
        ("notpad", "exe", "notepad"),
        ("google chrome", "exe", "chrome"),
        ("vs code", "exe", "code"),
        ("visual studio code", "exe", "code"),
        ("calc", "exe", "calc"),
        ("command prompt", "exe", "cmd"),
        ("edge", "exe", "msedge"),
        ("mspaint", "exe", "paint"),
    ]

    for input_name, expected_type, expected_substr in cases:
        res_type, target = wm._resolve_app_executable(input_name)
        assert res_type == expected_type, f"Failed for {input_name}: expected {expected_type}, got {res_type}"
        assert expected_substr in target.lower(), f"Failed for {input_name}: expected '{expected_substr}' in '{target}'"


def test_tier2_fuzzy_matching():
    """Verify tier 2 generalized fuzzy matching via difflib with cutoff."""
    wm = WindowManager()

    # Close matches
    res_type, target = wm._resolve_app_executable("chrom")
    assert res_type == "exe" and "chrome" in target.lower()

    res_type, target = wm._resolve_app_executable("spotfy")
    assert res_type == "exe" and "spotify" in target.lower()

    res_type, target = wm._resolve_app_executable("calclator")
    assert res_type == "exe" and "calc" in target.lower()


def test_ambiguity_gap_check():
    """Verify that close ambiguous matches return an ambiguity clarification message."""
    wm = WindowManager()

    # 'word' vs 'wordpad' or similar close candidates
    res_type, target = wm._resolve_app_executable("word")
    assert res_type in ("exe", "ambiguous")
    if res_type == "ambiguous":
        assert "Did you mean" in target


def test_web_app_fallbacks():
    """Verify that web-first services resolve to their web URLs."""
    wm = WindowManager()

    web_apps = [
        ("instagram", "https://www.instagram.com"),
        ("youtube", "https://www.youtube.com"),
        ("gmail", "https://mail.google.com"),
        ("twitter", "https://twitter.com"),
        ("x", "https://twitter.com"),
        ("reddit", "https://reddit.com"),
        ("github", "https://github.com"),
        ("linkedin", "https://linkedin.com"),
    ]

    for app_name, expected_url in web_apps:
        res_type, target = wm._resolve_app_executable(app_name)
        assert res_type == "url"
        assert target == expected_url


def test_whatsapp_resolution_and_fallback():
    """Verify WhatsApp resolves to exe, UWP protocol, or web fallback."""
    wm = WindowManager()

    res_type, target = wm._resolve_app_executable("whatsapp")
    assert res_type in ("exe", "protocol", "url")
    if res_type == "protocol":
        assert target == "whatsapp:"


@patch("webbrowser.open")
def test_handle_app_open_web_fallback(mock_web_open):
    """Verify _handle_app_open launches web browser for web URLs."""
    wm = WindowManager()
    result = wm._handle_app_open(app_name="instagram")

    assert result.status == ResultStatus.SUCCESS
    assert result.data.get("web_url") == "https://www.instagram.com"
    mock_web_open.assert_called_once_with("https://www.instagram.com")


def test_handle_app_open_ambiguous_fails_with_clarification():
    """Verify _handle_app_open returns FAILURE status with error string when ambiguous."""
    wm = WindowManager()
    with patch.object(wm, "_resolve_app_executable", return_value=("ambiguous", "Ambiguous app name 'word'. Did you mean 'word' or 'wordpad'?")):
        result = wm._handle_app_open(app_name="word")
        assert result.status == ResultStatus.FAILURE
        assert "Ambiguous app name" in result.error
