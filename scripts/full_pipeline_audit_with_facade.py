"""
Full-Scale Re-Audit of Duplicate Pipeline with Integrated AST Facade & Archive Filters.

Pipeline:
1. Sibling / Polymorphic Interface Filter
2. Morphological + Dictionary Antonym Inversion Filter
3. AST 1-Statement Facade Delegation Filter (reads actual function body slice & dedents)
4. Archive Path Filter (segregates dev/legacy_archive/ into Dedicated Archive Category)
5. 0.85+ Strict Similarity Threshold
6. Fresh Random Sample of 20 pairs from Active Clones bucket to measure ground-truth precision.
"""

import ast
import random
import re
import sys
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from src.engineering.project_index import ProjectIndex, SymbolRecord


# ── Common Protocol / Interface Method Names ──────────────────────────────────
COMMON_INTERFACE_METHODS = {
    "__init__",
    "__call__",
    "__str__",
    "__repr__",
    "to_dict",
    "from_dict",
    "validate",
    "validate_config",
    "get_status",
    "execute",
    "run",
    "close",
    "reset",
    "cleanup",
    "initialize",
    "handle",
    "process",
    "dispatch",
    "format",
    "get_info",
    "get_stats",
    "get_metrics",
    "get_name",
    "get_version",
    "is_available",
    "is_enabled",
    "setup",
    "teardown",
}


# ── Antonym & Inversion Rules ────────────────────────────────────────────────
COMPLEMENTARY_VERB_PAIRS = {
    ("load", "save"),
    ("read", "write"),
    ("serialize", "deserialize"),
    ("encode", "decode"),
    ("encrypt", "decrypt"),
    ("pack", "unpack"),
    ("compress", "decompress"),
    ("marshal", "unmarshal"),
    ("import", "export"),
    ("get", "set"),
    ("start", "stop"),
    ("connect", "disconnect"),
    ("subscribe", "unsubscribe"),
    ("publish", "consume"),
    ("push", "pull"),
    ("lock", "unlock"),
    ("show", "hide"),
    ("open", "close"),
    ("mount", "unmount"),
    ("enable", "disable"),
    ("add", "remove"),
    ("attach", "detach"),
    ("register", "unregister"),
    ("install", "uninstall"),
    ("create", "delete"),
    ("create", "destroy"),
    ("increment", "decrement"),
    ("acquire", "release"),
    ("enter", "exit"),
    ("expand", "collapse"),
    ("activate", "deactivate"),
    ("pause", "resume"),
    ("setup", "teardown"),
    ("bind", "unbind"),
    ("init", "cleanup"),
    ("initialize", "terminate"),
}

ANTONYM_MAP: dict[str, str] = {}
for v1, v2 in COMPLEMENTARY_VERB_PAIRS:
    ANTONYM_MAP[v1] = v2
    ANTONYM_MAP[v2] = v1


def extract_primary_verbs(func_name: str) -> list[str]:
    clean = re.sub(r"[^a-zA-Z0-9_]", "", func_name)
    parts = [p.lower() for p in clean.split("_") if p]
    return parts[:2] if parts else [func_name.lower()]


def is_antonym_or_inverted_pair(name_a: str, name_b: str) -> tuple[bool, str]:
    verbs_a = extract_primary_verbs(name_a)
    verbs_b = extract_primary_verbs(name_b)

    for va in verbs_a:
        for vb in verbs_b:
            if va == vb:
                continue
            if ANTONYM_MAP.get(va) == vb:
                return True, f"Antonym pair '{va}' <-> '{vb}'"
            for prefix in ("un", "de", "dis", "in", "non"):
                if vb == prefix + va or va == prefix + vb:
                    return True, f"Prefix antonym '{va}' <-> '{vb}'"
    return False, ""


def is_polymorphic_sibling(sym_a: SymbolRecord, sym_b: SymbolRecord) -> tuple[bool, str]:
    if sym_a.symbol_type == "method" and sym_b.symbol_type == "method":
        if sym_a.name == sym_b.name:
            if sym_a.name in COMMON_INTERFACE_METHODS:
                return True, f"Standard interface method: '{sym_a.name}()'"
            path_a = Path(sym_a.file_path).parent
            path_b = Path(sym_b.file_path).parent
            if path_a == path_b or path_a.parent == path_b.parent:
                return True, f"Sibling class method: '{sym_a.name}()'"

    if sym_a.name in COMMON_INTERFACE_METHODS and sym_b.name in COMMON_INTERFACE_METHODS:
        return True, f"Common protocol method: '{sym_a.name}' vs '{sym_b.name}'"

    return False, ""


def is_facade_delegation(file_path: str, line_start: int | None, line_end: int | None) -> tuple[bool, str]:
    if not line_start or not line_end:
        return False, ""

    try:
        p = Path(file_path)
        if not p.exists():
            return False, ""

        lines = p.read_text(encoding="utf-8").splitlines()
        func_slice = textwrap.dedent("\n".join(lines[line_start - 1 : line_end]))
        tree = ast.parse(func_slice)

        func_def = tree.body[0]
        if not isinstance(func_def, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return False, ""

        body_stmts = []
        for stmt in func_def.body:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                continue
            body_stmts.append(stmt)

        if len(body_stmts) == 1:
            stmt = body_stmts[0]
            if isinstance(stmt, ast.Return):
                if isinstance(stmt.value, (ast.Call, ast.Attribute)):
                    return True, "1-line Return Delegation"
            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                return True, "1-line Void Call Delegation"

        return False, ""
    except Exception:
        return False, ""


def is_archived_path(path_str: str) -> bool:
    p_lower = path_str.lower()
    return "legacy_archive" in p_lower or "legacy" in p_lower or "archive" in p_lower


# ── Run Full Re-Audit Pass ───────────────────────────────────────────────────

def run_full_reaudit():
    print("=" * 80)
    print("Full Pipeline Pass: Sibling + Antonym + AST Facade + Archive Filters")
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

    print(f"\n[1] Indexed {len(symbols)} candidate symbols.")

    texts = [f"{s.signature or s.name}\n{s.docstring.strip()}" for s in symbols]

    print("\n[2] Computing embeddings with all-MiniLM-L6-v2...")
    t0 = time.perf_counter()
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
    emb_time = time.perf_counter() - t0
    print(f"    Embeddings generated in {emb_time:.2f}s.")

    print("\n[3] Computing pairwise similarities and applying full filter pipeline...")
    sim_matrix = cosine_similarity(embeddings, embeddings)

    THRESHOLD = 0.85
    n = len(symbols)

    categories = {
        "ACTIVE_ARCHITECTURAL_CLONES": [],
        "LEGACY_ARCHIVE_CANDIDATES": [],
        "FACADE_DELEGATIONS": [],
        "POLYMORPHIC_SIBLINGS": [],
        "COMPLEMENTARY_COMPANIONS": [],
    }

    raw_candidates_count = 0

    for i in range(n):
        for j in range(i + 1, n):
            score = float(sim_matrix[i, j])
            if score >= THRESHOLD:
                sym_a = symbols[i]
                sym_b = symbols[j]

                if sym_a.file_path == sym_b.file_path and sym_a.name == sym_b.name:
                    continue

                raw_candidates_count += 1

                # 1. Archive segregation
                is_arch_a = is_archived_path(sym_a.file_path)
                is_arch_b = is_archived_path(sym_b.file_path)
                if is_arch_a or is_arch_b:
                    categories["LEGACY_ARCHIVE_CANDIDATES"].append((score, sym_a, sym_b, "Matches frozen legacy/archive file"))
                    continue

                # 2. Sibling / Polymorphic filter
                is_sibling, sibling_desc = is_polymorphic_sibling(sym_a, sym_b)
                if is_sibling:
                    categories["POLYMORPHIC_SIBLINGS"].append((score, sym_a, sym_b, sibling_desc))
                    continue

                # 3. Antonym filter
                is_antonym, antonym_desc = is_antonym_or_inverted_pair(sym_a.name, sym_b.name)
                if is_antonym:
                    categories["COMPLEMENTARY_COMPANIONS"].append((score, sym_a, sym_b, antonym_desc))
                    continue

                # 4. AST Facade Delegation filter
                is_facade_a, reason_a = is_facade_delegation(sym_a.file_path, sym_a.line_start, sym_a.line_end)
                is_facade_b, reason_b = is_facade_delegation(sym_b.file_path, sym_b.line_start, sym_b.line_end)
                if is_facade_a or is_facade_b:
                    facade_name = sym_a.name if is_facade_a else sym_b.name
                    categories["FACADE_DELEGATIONS"].append((score, sym_a, sym_b, f"'{facade_name}' is a 1-line pass-through facade"))
                    continue

                # 5. Remaining Active Candidate
                categories["ACTIVE_ARCHITECTURAL_CLONES"].append((score, sym_a, sym_b, "Active cross-module candidate"))

    print("\n" + "=" * 80)
    print(f"Categorized Pipeline Output (Threshold >= {THRESHOLD}):")
    print(f"  • Total Raw Candidate Pairs (>= 0.85):       {raw_candidates_count}")
    print(f"  ------------------------------------------------------------------")
    print(f"  1. POLYMORPHIC_SIBLINGS (Filtered):          {len(categories['POLYMORPHIC_SIBLINGS'])} pairs")
    print(f"  2. FACADE_DELEGATIONS (Filtered):            {len(categories['FACADE_DELEGATIONS'])} pairs")
    print(f"  3. COMPLEMENTARY_COMPANIONS (Filtered):      {len(categories['COMPLEMENTARY_COMPANIONS'])} pairs")
    print(f"  4. LEGACY_ARCHIVE_CANDIDATES (Segregated):   {len(categories['LEGACY_ARCHIVE_CANDIDATES'])} pairs")
    print(f"  ==================================================================")
    print(f"  5. ACTIVE_ARCHITECTURAL_CLONES (Actionable): {len(categories['ACTIVE_ARCHITECTURAL_CLONES'])} pairs")
    print("=" * 80)

    # 4. Deterministic Random Sample of 20 from ACTIVE_ARCHITECTURAL_CLONES
    active_clones = categories["ACTIVE_ARCHITECTURAL_CLONES"]
    random.seed(12345)  # Fresh random seed
    sample_size = min(20, len(active_clones))
    sample = random.sample(active_clones, sample_size) if active_clones else []

    print(f"\n[4] Fresh Random Sample of {sample_size} ACTIVE_ARCHITECTURAL_CLONES:")
    print("=" * 80)

    for i, (score, sym_a, sym_b, detail) in enumerate(sample, 1):
        rel_a = sym_a.file_path.split("AuraAI")[-1]
        rel_b = sym_b.file_path.split("AuraAI")[-1]
        doc_a = (sym_a.docstring or "").replace("\n", " ")[:85]
        doc_b = (sym_b.docstring or "").replace("\n", " ")[:85]

        print(f"\nSample {i:2d} [Cosine: {score:.4f}] ({detail})")
        print(f"  A: {sym_a.qualified_name} in ...{rel_a}")
        print(f"     Sig: {sym_a.signature}")
        print(f"     Doc: {doc_a}...")
        print(f"  B: {sym_b.qualified_name} in ...{rel_b}")
        print(f"     Sig: {sym_b.signature}")
        print(f"     Doc: {doc_b}...")


if __name__ == "__main__":
    run_full_reaudit()
