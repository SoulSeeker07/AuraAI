"""
Run a real audit of the AuraAI codebase using EngineeringManager.audit_duplicates().
"""

import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.engineering.engineering_manager import EngineeringManager


def main():
    print("=" * 80)
    print("AuraAI Repository Architecture & Deduplication Audit")
    print("=" * 80)

    t0 = time.perf_counter()
    em = EngineeringManager(repository_path=repo_root)
    em.project_index.scan()
    report = em.audit_duplicates(threshold=0.85)
    total_time = time.perf_counter() - t0

    print(f"\n[Audit Summary - {total_time:.2f}s total]:")
    summary = report.summary()
    for k, v in summary.items():
        print(f"  • {k}: {v}")

    print("\n" + "=" * 80)
    print(f"Tier 1 Highlights: Top 5 Active Architectural Clones:")
    print("=" * 80)
    for i, pair in enumerate(report.tier1_active_clones[:5], 1):
        rel_a = pair.symbol_a.file_path.split("AuraAI")[-1]
        rel_b = pair.symbol_b.file_path.split("AuraAI")[-1]
        print(f"\n[{i}] Cosine: {pair.similarity:.4f}")
        print(f"    Symbol A: {pair.symbol_a.qualified_name} in ...{rel_a}")
        print(f"    Symbol B: {pair.symbol_b.qualified_name} in ...{rel_b}")
        print(f"    Reason:   {pair.classification_reason}")

    print("\n" + "=" * 80)
    print(f"Tier 2 Highlights: Top 3 Legacy Archive Clones:")
    print("=" * 80)
    for i, pair in enumerate(report.tier2_legacy_archive[:3], 1):
        rel_a = pair.symbol_a.file_path.split("AuraAI")[-1]
        rel_b = pair.symbol_b.file_path.split("AuraAI")[-1]
        print(f"\n[{i}] Cosine: {pair.similarity:.4f}")
        print(f"    Archive: {pair.symbol_a.qualified_name} in ...{rel_a}")
        print(f"    Active:  {pair.symbol_b.qualified_name} in ...{rel_b}")

    em.close()


if __name__ == "__main__":
    main()
