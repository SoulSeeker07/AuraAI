import importlib.util
from pathlib import Path
from collections import defaultdict

ROOT = Path.cwd()
checker_path = ROOT / "scripts" / "check_import_convention.py"
spec = importlib.util.spec_from_file_location("check_import_convention", checker_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

report_lines = []
total_violations = 0
files_with_violations = []

for scan_dir in module.SCAN_DIRS:
    scan_path = ROOT / scan_dir
    if not scan_path.exists():
        continue
    for filepath in sorted(scan_path.rglob("*.py")):
        rel_str = str(filepath.relative_to(ROOT)).replace("\\", "/")
        if rel_str in module.EXCLUDE_FILES or rel_str in module.HISTORICAL_EXEMPT_ARTIFACTS:
            continue
        v_list = module.scan_file(filepath)
        if v_list:
            files_with_violations.append((rel_str, v_list))
            total_violations += len(v_list)

report_lines.append(f"# Import Convention Violations: {total_violations} across {len(files_with_violations)} files\n")

for rel_str, v_list in files_with_violations:
    report_lines.append(f"### `{rel_str}` ({len(v_list)} violation{'s' if len(v_list) > 1 else ''})\n")
    report_lines.append("| Line | Offending Import Statement |")
    report_lines.append("|---|---|")
    for ln, content in v_list:
        report_lines.append(f"| {ln} | `{content}` |")
    report_lines.append("")

output_file = ROOT / "scratch" / "import_violations_report.md"
output_file.write_text("\n".join(report_lines), encoding="utf-8")
print(f"Report written to {output_file}")
