"""
Phase 2 Feasibility Spike: Semantic Existing-Feature / Duplicate Detection

Tests all-MiniLM-L6-v2 on 20 real functions sampled across AuraAI subsystems.
Computes cosine similarity and displays top-3 nearest neighbors for 5 distinct probe functions.
"""

import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from src.engineering.project_index import ProjectIndex


def run_spike():
    print("=" * 80)
    print("Phase 2 Feasibility Spike - Semantic Embedding & Nearest Neighbor Evaluation")
    print("=" * 80)

    # 1. Open persistent index from Phase 1
    index = ProjectIndex(repo_root=repo_root)
    index.scan()

    # 2. Select 20 real diverse functions with non-empty docstrings across subsystems
    cur_symbols = []
    with index._get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, file_path, symbol_type, name, qualified_name, signature, docstring, line_start, line_end
            FROM symbols
            WHERE docstring IS NOT NULL 
              AND docstring != '' 
              AND symbol_type IN ('function', 'method', 'async_function')
              AND file_path NOT LIKE '%test%'
              AND file_path NOT LIKE '%scratch%'
            ORDER BY id ASC
            """
        ).fetchall()

    # Pick 20 diverse functions from distinct files
    seen_files = set()
    selected_symbols = []
    for r in rows:
        fp = r["file_path"]
        if fp not in seen_files:
            seen_files.add(fp)
            from src.engineering.project_index import SymbolRecord
            selected_symbols.append(
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
            if len(selected_symbols) >= 20:
                break

    print(f"\n[1] Sampled {len(selected_symbols)} real functions across AuraAI subsystems:")
    for i, sym in enumerate(selected_symbols, 1):
        rel = sym.file_path.split("AuraAI")[-1]
        print(f"  {i:2d}. {sym.qualified_name} ({rel})")

    # 3. Formulate text representations: f"{signature}\n{docstring or ''}"
    texts = []
    for sym in selected_symbols:
        doc = sym.docstring.strip() if sym.docstring else "No docstring provided."
        text = f"{sym.signature or sym.name}\n{doc}"
        texts.append(text)

    # 4. Load all-MiniLM-L6-v2 model and compute embeddings
    print("\n[2] Loading 'all-MiniLM-L6-v2' (~80MB embedding model)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(texts, normalize_embeddings=True)
    print(f"  Generated normalized embeddings matrix: {embeddings.shape}")

    # 5. Evaluate 5 distinct probe functions across different index positions
    probe_indices = [0, 4, 8, 12, 16]
    if len(selected_symbols) < 20:
        probe_indices = list(range(min(5, len(selected_symbols))))

    print("\n" + "=" * 80)
    print("[3] Top-3 Nearest Neighbor Evaluations for 5 Distinct Probes")
    print("=" * 80)

    for probe_idx in probe_indices:
        query_sym = selected_symbols[probe_idx]
        query_vec = embeddings[probe_idx].reshape(1, -1)

        # Compute cosine similarity with all candidate vectors
        sims = cosine_similarity(query_vec, embeddings)[0]

        # Sort indices excluding self
        ranked_indices = [i for i in np.argsort(sims)[::-1] if i != probe_idx]
        top3 = ranked_indices[:3]

        print(f"\n------------------------------------------------------------------------")
        print(f"PROBE: {query_sym.qualified_name}")
        print(f"  Signature: {query_sym.signature}")
        print(f"  Docstring: {query_sym.docstring.strip()[:120]}...")
        print(f"  Top 3 Nearest Neighbors (Cosine Similarity):")

        for rank, cand_idx in enumerate(top3, 1):
            cand_sym = selected_symbols[cand_idx]
            cand_score = sims[cand_idx]
            doc_snippet = (cand_sym.docstring or "").strip()[:100].replace("\n", " ")
            print(f"    {rank}. [Score: {cand_score:.4f}] {cand_sym.qualified_name}")
            print(f"       Sig: {cand_sym.signature}")
            print(f"       Doc: {doc_snippet}...")

    print("\n" + "=" * 80)
    print("Spike Completed.")
    print("=" * 80)


if __name__ == "__main__":
    run_spike()
