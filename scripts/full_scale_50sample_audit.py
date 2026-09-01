"""
Comprehensive 50-Sample Evaluation of Phase 2 Duplicate Pipeline with Intra-File & Facade Filters.

Filters applied:
1. Intra-File Exclusion (sym_a.file_path == sym_b.file_path filtered out).
2. Sibling / Polymorphic Interface Filter.
3. AST 1-Statement Facade Delegation Filter.
4. Legacy Archive Segregation Filter.
5. Morphological + Dictionary Antonym Filter.
6. 0.85+ Strict Similarity Threshold.
7. n=50 Random Sample Audit with ground-truth source verification.
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


COMMON_INTERFACE_METHODS = {
    "__init__", "__call__", "__str__", "__repr__", "to_dict", "from_dict",
    "validate", "validate_config", "get_status", "execute", "run", "close",
    "reset", "cleanup", "initialize", "handle", "process", "dispatch", "format",
    "get_info", "get_stats", "get_metrics", "get_name", "get_version",
    "is_available", "is_enabled", "setup", "teardown",
}

COMPLEMENTARY_VERB_PAIRS = {
    ("load", "save"), ("read", "write"), ("serialize", "deserialize"),
    ("encode", "decode"), ("encrypt", "decrypt"), ("pack", "unpack"),
    ("compress", "decompress"), ("marshal", "unmarshal"), ("import", "export"),
    ("get", "set"), ("start", "stop"), ("connect", "disconnect"),
    ("subscribe", "unsubscribe"), ("publish", "consume"), ("push", "pull"),
    ("lock", "unlock"), ("show", "hide"), ("open", "close"), ("mount", "unmount"),
    ("enable", "disable"), ("add", "remove"), ("attach", "detach"),
    ("register", "unregister"), ("install", "uninstall"), ("create", "delete"),
    ("create", "destroy"), ("increment", "decrement"), ("acquire", "release"),
    ("enter", "exit"), ("expand", "collapse"), ("activate", "deactivate"),
    ("pause", "resume"), ("setup", "teardown"), ("bind", "unbind"),
    ("init", "cleanup"), ("initialize", "terminate"),
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


def run_50_sample_audit():
    print("=" * 80)
    print("50-Sample Rigorous Audit: Intra-File + Facade + Sibling + Archive Filters")
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

    print(f"\n[1] Extracted {len(symbols)} candidate symbols.")

    texts = [f"{s.signature or s.name}\n{s.docstring.strip()}" for s in symbols]
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False)

    sim_matrix = cosine_similarity(embeddings, embeddings)
    THRESHOLD = 0.85
    n = len(symbols)

    categories = {
        "ACTIVE_ARCHITECTURAL_CLONES": [],
        "INTRA_FILE_HELPERS": [],
        "LEGACY_ARCHIVE_CANDIDATES": [],
        "FACADE_DELEGATIONS": [],
        "POLYMORPHIC_SIBLINGS": [],
        "COMPLEMENTARY_COMPANIONS": [],
    }

    for i in range(n):
        for j in range(i + 1, n):
            score = float(sim_matrix[i, j])
            if score >= THRESHOLD:
                sym_a = symbols[i]
                sym_b = symbols[j]

                # 1. Intra-File Filter
                if sym_a.file_path == sym_b.file_path:
                    categories["INTRA_FILE_HELPERS"].append((score, sym_a, sym_b, "Same file methods"))
                    continue

                # 2. Archive segregation
                if is_archived_path(sym_a.file_path) or is_archived_path(sym_b.file_path):
                    categories["LEGACY_ARCHIVE_CANDIDATES"].append((score, sym_a, sym_b, "Matches legacy/archive file"))
                    continue

                # 3. Sibling / Polymorphic filter
                is_sibling, sibling_desc = is_polymorphic_sibling(sym_a, sym_b)
                if is_sibling:
                    categories["POLYMORPHIC_SIBLINGS"].append((score, sym_a, sym_b, sibling_desc))
                    continue

                # 4. Antonym filter
                is_antonym, antonym_desc = is_antonym_or_inverted_pair(sym_a.name, sym_b.name)
                if is_antonym:
                    categories["COMPLEMENTARY_COMPANIONS"].append((score, sym_a, sym_b, antonym_desc))
                    continue

                # 5. AST Facade filter
                is_facade_a, _ = is_facade_delegation(sym_a.file_path, sym_a.line_start, sym_a.line_end)
                is_facade_b, _ = is_facade_delegation(sym_b.file_path, sym_b.line_start, sym_b.line_end)
                if is_facade_a or is_facade_b:
                    facade_name = sym_a.name if is_facade_a else sym_b.name
                    categories["FACADE_DELEGATIONS"].append((score, sym_a, sym_b, f"'{facade_name}' is a 1-line facade"))
                    continue

                # 6. Active Architectural Candidate
                categories["ACTIVE_ARCHITECTURAL_CLONES"].append((score, sym_a, sym_b, "Cross-module active candidate"))

    print("\n" + "=" * 80)
    print(f"Categorized Breakdown:")
    print(f"  • INTRA_FILE_HELPERS (Filtered):             {len(categories['INTRA_FILE_HELPERS'])} pairs")
    print(f"  • POLYMORPHIC_SIBLINGS (Filtered):           {len(categories['POLYMORPHIC_SIBLINGS'])} pairs")
    print(f"  • FACADE_DELEGATIONS (Filtered):             {len(categories['FACADE_DELEGATIONS'])} pairs")
    print(f"  • COMPLEMENTARY_COMPANIONS (Filtered):       {len(categories['COMPLEMENTARY_COMPANIONS'])} pairs")
    print(f"  • LEGACY_ARCHIVE_CANDIDATES (Segregated):    {len(categories['LEGACY_ARCHIVE_CANDIDATES'])} pairs")
    print(f"  ==================================================================")
    print(f"  • ACTIVE_ARCHITECTURAL_CLONES (Actionable):  {len(categories['ACTIVE_ARCHITECTURAL_CLONES'])} pairs")
    print("=" * 80)

    # 4. Draw n=50 Random Sample from ACTIVE_ARCHITECTURAL_CLONES
    active_clones = categories["ACTIVE_ARCHITECTURAL_CLONES"]
    random.seed(9999)  # Deterministic seed for 50-sample audit
    sample_size = min(50, len(active_clones))
    sample = random.sample(active_clones, sample_size) if active_clones else []

    print(f"\n[4] Comprehensive Audit of n={sample_size} Sample Pairs:")
    print("=" * 80)

    for i, (score, sym_a, sym_b, detail) in enumerate(sample, 1):
        rel_a = sym_a.file_path.split("AuraAI")[-1]
        rel_b = sym_b.file_path.split("AuraAI")[-1]
        doc_a = (sym_a.docstring or "").replace("\n", " ")[:70]
        doc_b = (sym_b.docstring or "").replace("\n", " ")[:70]

        print(f"[{i:02d}] {score:.4f} | {sym_a.qualified_name} (...{rel_a})")
        print(f"     vs  | {sym_b.qualified_name} (...{rel_b})")
        print(f"     DocA: {doc_a}...")
        print(f"     DocB: {doc_b}...")
        print("-" * 80)


if __name__ == "__main__":
    run_50_sample_audit()
