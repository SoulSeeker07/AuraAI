"""
Spot-Check Audit of Tier 2 (Legacy Archive Candidates, n=10 random sample).
"""

import random
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from scripts.full_scale_50sample_audit import (
    COMMON_INTERFACE_METHODS,
    ProjectIndex,
    is_archived_path,
    is_facade_delegation,
    is_polymorphic_sibling,
)
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


def audit_tier2_legacy_archive():
    print("=" * 80)
    print("Tier 2 (Legacy Archive Candidates) 10-Sample Verification Audit")
    print("=" * 80)

    index = ProjectIndex(repo_root=repo_root)
    index.scan()

    with index._get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, file_path, symbol_type, name, qualified_name, signature, docstring, line_start, line_end
            FROM symbols
            WHERE docstring IS NOT NULL 
              AND length(docstring) > 20
              AND symbol_type IN ('function', 'method', 'async_function')
              AND file_path NOT LIKE '%test%'
              AND file_path NOT LIKE '%scratch%'
              AND file_path NOT LIKE '%__pycache__%'
            ORDER BY id ASC
            """
        ).fetchall()

    from src.engineering.project_index import SymbolRecord
    symbols = []
    seen = set()
    for r in rows:
        k = f"{r['file_path']}:{r['qualified_name']}"
        if k not in seen:
            seen.add(k)
            symbols.append(
                SymbolRecord(
                    id=r["id"],
                    file_path=r["file_path"],
                    symbol_type=r["symbol_type"],
                    name=r["name"],
                    qualified_name=r["qualified_name"],
                    signature=r["signature"],
                    docstring=r["docstring"],
                    line_start=r["line_start"],
                    line_end=r["line_end"],
                )
            )

    texts = [f"{s.signature or s.name}\n{s.docstring.strip()}" for s in symbols]
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False)

    sim_matrix = cosine_similarity(embeddings, embeddings)
    THRESHOLD = 0.85
    n = len(symbols)

    legacy_candidates = []
    for i in range(n):
        for j in range(i + 1, n):
            score = float(sim_matrix[i, j])
            if score >= THRESHOLD:
                sym_a = symbols[i]
                sym_b = symbols[j]
                if sym_a.file_path == sym_b.file_path:
                    continue

                is_arch_a = is_archived_path(sym_a.file_path)
                is_arch_b = is_archived_path(sym_b.file_path)

                # Pair between legacy_archive and active code
                if (is_arch_a and not is_arch_b) or (is_arch_b and not is_arch_a):
                    legacy_candidates.append((score, sym_a, sym_b))

    print(f"\nTotal Tier 2 Legacy Archive vs Active Code Pairs (>= 0.85): {len(legacy_candidates)}")

    random.seed(42)
    sample_size = min(10, len(legacy_candidates))
    sample = random.sample(legacy_candidates, sample_size)

    for i, (score, sym_a, sym_b) in enumerate(sample, 1):
        rel_a = sym_a.file_path.split("AuraAI")[-1]
        rel_b = sym_b.file_path.split("AuraAI")[-1]
        print(f"\n[Sample {i:02d}] Cosine: {score:.4f}")
        print(f"  Archive: {sym_a.qualified_name} in ...{rel_a}")
        print(f"  Active:  {sym_b.qualified_name} in ...{rel_b}")
        print(f"  Doc A:   {(sym_a.docstring or '')[:80].strip()}...")
        print(f"  Doc B:   {(sym_b.docstring or '')[:80].strip()}...")


if __name__ == "__main__":
    audit_tier2_legacy_archive()
