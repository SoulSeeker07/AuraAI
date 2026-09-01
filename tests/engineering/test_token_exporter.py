"""
Tests for Design Token Exporter & Drift Engine
==============================================
Location: tests/engineering/test_token_exporter.py
"""

import json
from pathlib import Path
import pytest

from engineering.token_exporter import (
    check_drift,
    export_tokens,
    extract_canonical_tokens,
    generate_aura_theme_css,
    generate_tailwind_config,
    generate_tokens_json,
)
from gui.theme import Colors, Radius, Spacing, Typography


def test_extract_canonical_tokens():
    tokens = extract_canonical_tokens()
    assert "colors" in tokens
    assert "typography" in tokens
    assert "spacing" in tokens
    assert "radius" in tokens
    assert "token_hash" in tokens
    assert len(tokens["token_hash"]) == 16

    # Verify colors match theme.py
    colors = tokens["colors"]
    assert colors["cyan"] == Colors.CYAN
    assert colors["bg-deep"] == Colors.BG_DEEP
    assert colors["emerald"] == Colors.EMERALD

    # Verify spacing matches theme.py
    assert tokens["spacing"]["xs"] == f"{Spacing.XS}px"
    assert tokens["spacing"]["sm"] == f"{Spacing.SM}px"


def test_token_exporter_lifecycle_and_drift_detection(tmp_path):
    target_dir = tmp_path / "templates"
    
    # 1. Initially missing files -> check_drift reports errors
    synced, errors = check_drift(target_dir)
    assert not synced
    assert any("Missing token artifact" in err for err in errors)

    # 2. Export tokens -> check_drift returns True
    exported = export_tokens(target_dir)
    assert exported["tokens_json"].exists()
    assert exported["tailwind_config"].exists()
    assert exported["aura_css"].exists()

    synced, errors = check_drift(target_dir)
    assert synced
    assert len(errors) == 0

    # 3. Simulate drift by tampering with tokens.json
    tampered_json = json.loads(exported["tokens_json"].read_text(encoding="utf-8"))
    tampered_json["token_hash"] = "tampered_hash_123"
    exported["tokens_json"].write_text(json.dumps(tampered_json), encoding="utf-8")

    synced, errors = check_drift(target_dir)
    assert not synced
    assert any("tokens.json hash mismatch" in err for err in errors)

    # 4. Re-exporting fixes drift
    export_tokens(target_dir)
    synced, errors = check_drift(target_dir)
    assert synced
    assert len(errors) == 0


def test_starter_app_html_template_exists():
    project_root = Path(__file__).resolve().parents[2]
    starter_html = project_root / "src" / "engineering" / "templates" / "starter_app.html"
    assert starter_html.exists()
    content = starter_html.read_text(encoding="utf-8")
    assert "tailwind.config" in content
    assert "AURA CYBER-HUD" in content
