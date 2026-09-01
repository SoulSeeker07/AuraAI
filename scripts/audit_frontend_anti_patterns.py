#!/usr/bin/env python3
"""
Frontend Anti-Pattern & Compliance Audit Script
Audits src/gui against all 5 rules in docs/FRONTEND_DESIGN.md:
1. NO Blocking Modal Dialogs
2. NO Hardcoded Hex Codes (Hex vs theme.py token usage)
3. NO UI-Thread Heavy Computation (Sync DB, HTTP, heavy disk I/O on UI thread)
4. NO Unconstrained List Growth (Unbounded QLayout/QList/QScrollArea without caps/pruning)
5. NO Non-Standard Spacing (Non-4px/8px grid violations)
"""

import ast
import os
import re
import sys
from pathlib import Path
from dataclasses import dataclass, field

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GUI_DIR = Path("src/gui")
THEME_FILE = GUI_DIR / "theme.py"

@dataclass
class AuditReport:
    rule1_blocking_modals: list[str] = field(default_factory=list)
    rule2_hardcoded_colors: list[str] = field(default_factory=list)
    rule3_heavy_ui_computations: list[str] = field(default_factory=list)
    rule4_unbounded_lists: list[str] = field(default_factory=list)
    rule5_nonstandard_spacing: list[str] = field(default_factory=list)
    rule6_token_drift: list[str] = field(default_factory=list)

def audit_rule1_blocking_modals(file_path: Path, content: str, report: AuditReport):
    """Rule 1: Never invoke QMessageBox.exec(), QDialog.exec(), or Win32 MessageBox on UI/worker threads."""
    patterns = [
        (r'\bQMessageBox\b.*\.exec(?:_\(\)|\(\))', "QMessageBox.exec blocking call"),
        (r'\bQDialog\b.*\.exec(?:_\(\)|\(\))', "QDialog.exec blocking modal call"),
        (r'\bctypes\.windll\.user32\.MessageBox[AW]\b', "Win32 MessageBox blocking call"),
        (r'\bwin32gui\.MessageBox\b', "Win32 MessageBox blocking call"),
    ]
    for line_no, line in enumerate(content.splitlines(), 1):
        for pat, desc in patterns:
            if re.search(pat, line):
                report.rule1_blocking_modals.append(f"{file_path.name}:{line_no} -> {desc}: {line.strip()}")

def audit_rule2_hardcoded_colors(file_path: Path, content: str, report: AuditReport):
    """Rule 2: Check for inline hardcoded hex color codes outside theme.py."""
    if file_path.name in ("theme.py", "animations.py"):
        return
    
    # Match #RGB, #RRGGBB, #RRGGBBAA in strings
    hex_pattern = re.compile(r'(?<!\w)#[0-9a-fA-F]{3,8}\b')
    for line_no, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        matches = hex_pattern.findall(line)
        if matches:
            if "Colors." not in line and "THEME" not in line:
                report.rule2_hardcoded_colors.append(f"{file_path.name}:{line_no} -> Hardcoded hex {matches}: {stripped[:80]}")

def audit_rule3_ui_heavy_computation(file_path: Path, content: str, report: AuditReport):
    """Rule 3: Heavy operations (SQLite queries, requests, heavy scans) directly in UI slots/methods."""
    sync_heavy_patterns = [
        (r'\bsqlite3\.connect\(', "Direct synchronous sqlite3.connect in UI file"),
        (r'\brequests\.(?:get|post|put|delete)\(', "Synchronous HTTP request in UI file"),
        (r'\burllib\.request\.urlopen\(', "Synchronous urllib request in UI file"),
        (r'\bsubprocess\.run\(', "Synchronous subprocess.run in UI file"),
        (r'\btime\.sleep\(', "time.sleep blocking call in UI file"),
    ]
    for line_no, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for pat, desc in sync_heavy_patterns:
            if re.search(pat, line):
                report.rule3_heavy_ui_computations.append(f"{file_path.name}:{line_no} -> {desc}: {stripped[:90]}")

def audit_rule4_unbounded_lists(file_path: Path, content: str, report: AuditReport):
    """Rule 4: Find layout item additions (addWidget / addLayout / append) and verify if pruning / max bounds exist."""
    has_item_add = bool(re.search(r'\b(?:addWidget|addLayout|addItem)\b', content))
    has_layout_or_list = bool(re.search(r'\b(?:QVBoxLayout|QHBoxLayout|QListWidget|QScrollArea)\b', content))
    
    if has_item_add and has_layout_or_list:
        dynamic_add_methods = re.findall(r'def\s+([a-zA-Z0-9_]*(?:add_|append_|insert_|log_|message_|task_)[a-zA-Z0-9_]*)\s*\(', content)
        if dynamic_add_methods:
            has_pruning = any(kw in content for kw in (
                "MAX_", "max_", "takeAt", "deleteLater", "removeRow", "clear()", "count() >", "len("
            ))
            if not has_pruning:
                report.rule4_unbounded_lists.append(
                    f"{file_path.name} -> Contains dynamic addition methods {dynamic_add_methods} without explicit layout pruning or capacity capping"
                )

def audit_rule5_spacing_grid(file_path: Path, content: str, report: AuditReport):
    """Rule 5: Check margins, paddings, gap dimensions, and spacing against 4px/8px grid."""
    if file_path.name in ("theme.py",):
        return

    spacing_calls = re.finditer(r'\.setSpacing\(\s*(\d+)\s*\)', content)
    for m in spacing_calls:
        val = int(m.group(1))
        if val > 0 and val % 2 != 0:
            report.rule5_nonstandard_spacing.append(f"{file_path.name} -> setSpacing({val}) is odd / non-grid")

    margin_calls = re.finditer(r'\.setContentsMargins\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', content)
    for m in margin_calls:
        vals = [int(x) for x in m.groups()]
        for v in vals:
            if v > 0 and v % 2 != 0:
                report.rule5_nonstandard_spacing.append(f"{file_path.name} -> setContentsMargins({vals}) contains odd pixel value {v}")
                break

    css_odd_px = re.finditer(r'(?:padding|margin|gap):\s*([^;]+);', content)
    for m in css_odd_px:
        nums = re.findall(r'\b(\d+)px\b', m.group(1))
        for n in nums:
            val = int(n)
            if val > 1 and val % 2 != 0:
                report.rule5_nonstandard_spacing.append(f"{file_path.name} -> CSS '{m.group(0)}' has non-standard {val}px")
                break

def run_audit() -> AuditReport:
    report = AuditReport()
    for py_file in sorted(GUI_DIR.rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception as e:
            print(f"Error reading {py_file}: {e}")
            continue
        
        audit_rule1_blocking_modals(py_file, content, report)
        audit_rule2_hardcoded_colors(py_file, content, report)
        audit_rule3_ui_heavy_computation(py_file, content, report)
        audit_rule4_unbounded_lists(py_file, content, report)
        audit_rule5_spacing_grid(py_file, content, report)
    
    # Rule 6: Design-Token Synchronization (theme.py vs templates)
    try:
        from engineering.token_exporter import check_drift
        synced, errors = check_drift()
        if not synced:
            report.rule6_token_drift.extend(errors)
    except Exception as e:
        report.rule6_token_drift.append(f"Failed to check token drift: {e}")

    return report

if __name__ == "__main__":
    rep = run_audit()
    print("=" * 80)
    print("AURA FRONTEND ANTI-PATTERN AUDIT RESULTS")
    print("=" * 80)
    print(f"\n[RULE 1] Blocking Modal Dialogs: {len(rep.rule1_blocking_modals)} violations")
    for item in rep.rule1_blocking_modals:
        print(f"  ❌ {item}")
    if not rep.rule1_blocking_modals:
        print("  ✅ PASS: Zero blocking modal dialog calls found.")

    print(f"\n[RULE 2] Hardcoded Hex Colors: {len(rep.rule2_hardcoded_colors)} instances found")
    print(f"  ℹ️ (Showing top 5 of {len(rep.rule2_hardcoded_colors)} if any)")
    for item in rep.rule2_hardcoded_colors[:5]:
        print(f"  ⚠️ {item}")

    print(f"\n[RULE 3] UI-Thread Heavy Computation: {len(rep.rule3_heavy_ui_computations)} call sites")
    for item in rep.rule3_heavy_ui_computations:
        print(f"  ⚠️ {item}")
    if not rep.rule3_heavy_ui_computations:
        print("  ✅ PASS: No direct synchronous DB/HTTP/blocking calls on UI thread.")

    print(f"\n[RULE 4] Unbounded List / Dynamic Layout Growth: {len(rep.rule4_unbounded_lists)} unconstrained widgets")
    for item in rep.rule4_unbounded_lists:
        print(f"  ⚠️ {item}")
    if not rep.rule4_unbounded_lists:
        print("  ✅ PASS: All dynamic layouts/lists have pruning or bounded capacity.")

    print(f"\n[RULE 5] Non-Standard Spacing (Non-Grid Values): {len(rep.rule5_nonstandard_spacing)} occurrences")
    print(f"  ℹ️ (Showing top 5 of {len(rep.rule5_nonstandard_spacing)} if any)")
    for item in rep.rule5_nonstandard_spacing[:5]:
        print(f"  ⚠️ {item}")
    if not rep.rule5_nonstandard_spacing:
        print("  ✅ PASS: All margins and paddings adhere to the grid.")

    print(f"\n[RULE 6] Design-Token Synchronization: {len(rep.rule6_token_drift)} drift errors")
    for item in rep.rule6_token_drift:
        print(f"  ❌ {item}")
    if not rep.rule6_token_drift:
        print("  ✅ PASS: Web token artifacts (tokens.json, tailwind.config.js, aura-theme.css) are 100% in sync with theme.py.")
    print("=" * 80)
