"""
Rigorous Recalibration & Empirical Validation of Phase 2 Duplicate Detection Pipeline.

Implements:
1. Sibling / Polymorphic Interface Filter (detects shared protocol/interface methods across sibling/provider classes).
2. Protocol / Boilerplate Lifecycle Filter (detects __init__, to_dict, close, validate_config, execute on different classes).
3. 0.85+ Strict Similarity Threshold.
4. Full 5,383-symbol pass over the entire repository.
5. Random Sampling of 20 flagged pairs to evaluate real precision honestly.
"""

import ast
import random
import re
import sys
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


# ── Polymorphic Sibling / Interface Detection ─────────────────────────────────

def is_polymorphic_sibling(sym_a: SymbolRecord, sym_b: SymbolRecord) -> tuple[bool, str]:
    """
    Detects if sym_a and sym_b are sibling implementations of the same interface method
    across different classes in the same subsystem / architecture domain.
    """
    # 1. Methods with identical name across different classes
    if sym_a.symbol_type == "method" and sym_b.symbol_type == "method":
        if sym_a.name == sym_b.name:
            # Check if it's a known protocol/interface method
            if sym_a.name in COMMON_INTERFACE_METHODS:
                return True, f"Standard interface/lifecycle method: '{sym_a.name}()'"

            # Check if classes reside in sibling directories (e.g. providers/, experts/, tools/, adapters/)
            path_a = Path(sym_a.file_path).parent
            path_b = Path(sym_b.file_path).parent
            if path_a == path_b or path_a.parent == path_b.parent:
                return True, f"Sibling class method in '{path_a.name}': '{sym_a.name}()'"

    # 2. Both are protocol/lifecycle methods regardless of naming variation if in COMMON_INTERFACE_METHODS
    if sym_a.name in COMMON_INTERFACE_METHODS and sym_b.name in COMMON_INTERFACE_METHODS:
        return True, f"Common protocol methods: '{sym_a.name}' vs '{sym_b.name}'"

    return False, ""


# ── Signature Shape & Inversion Check ─────────────────────────────────────────

@dataclass
class RobustSignatureShape:
    func_name: str
    required_param_types: list[str]
    optional_param_types: list[str]
    return_type: str | None


def parse_robust_signature(sig_text: str) -> RobustSignatureShape:
    if not sig_text:
        return RobustSignatureShape("", [], [], None)
    try:
        tree = ast.parse(f"{sig_text}\n    pass")
        func_def = tree.body[0]
        if not isinstance(func_def, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return RobustSignatureShape("", [], [], None)

        args = func_def.args
        num_defaults = len(args.defaults)
        num_args = len(args.args)
        num_required = num_args - num_defaults

        req_types = []
        opt_types = []

        for i, a in enumerate(args.args):
            if a.arg in ("self", "cls"):
                continue
            ann = ast.unparse(a.annotation).strip() if a.annotation else "Any"
            if a.arg in ("logger", "timeout", "verbose", "context", "config"):
                opt_types.append(ann)
            elif i < num_required:
                req_types.append(ann)
            else:
                opt_types.append(ann)

        ret = ast.unparse(func_def.returns).strip() if func_def.returns else None
        return RobustSignatureShape(func_def.name, req_types, opt_types, ret)
    except Exception:
        name_match = re.match(r"(?:async\s+)?def\s+([a-zA-Z0-9_]+)", sig_text)
        name = name_match.group(1) if name_match else ""
        return RobustSignatureShape(name, [], [], None)


def evaluate_signature_relationship(sig_a: RobustSignatureShape, sig_b: RobustSignatureShape) -> str:
    all_a = set(sig_a.required_param_types + sig_a.optional_param_types)
    all_b = set(sig_b.required_param_types + sig_b.optional_param_types)
    ret_a = sig_a.return_type
    ret_b = sig_b.return_type

    if ret_a and ret_b and ret_a != ret_b and ret_a not in ("None", "bool") and ret_b not in ("None", "bool"):
        if (ret_a in all_b or any(ret_a in p for p in all_b)) and (
            ret_b in all_a or any(ret_b in p for p in all_a)
        ):
            return "INVERTED_IO"

    if ret_a == ret_b and len(sig_a.required_param_types) == len(sig_b.required_param_types):
        return "MATCHING_IO_SHAPE"

    return "ASYMMETRIC_SHAPE"


# ── Run Full Recalibrated Evaluation ──────────────────────────────────────────

def run_recalibrated_evaluation():
    print("=" * 80)
    print("Recalibrated Pipeline Pass on All Real Symbols (Threshold >= 0.85 + Sibling Filter)")
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

    print(f"\n[1] Extracted {len(symbols)} unique candidate symbols.")

    texts = [f"{s.signature or s.name}\n{s.docstring.strip()}" for s in symbols]

    print("\n[2] Computing embeddings...")
    t0 = time.perf_counter()
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
    emb_time = time.perf_counter() - t0
    print(f"    Embedded in {emb_time:.2f}s.")

    print("\n[3] Computing pairwise similarities with STRICT threshold (>= 0.85)...")
    sim_matrix = cosine_similarity(embeddings, embeddings)

    THRESHOLD = 0.85
    candidates = []
    n = len(symbols)
    for i in range(n):
        for j in range(i + 1, n):
            score = float(sim_matrix[i, j])
            if score >= THRESHOLD:
                sym_a = symbols[i]
                sym_b = symbols[j]
                if sym_a.file_path == sym_b.file_path and sym_a.name == sym_b.name:
                    continue
                candidates.append((score, sym_a, sym_b))

    candidates.sort(key=lambda x: x[0], reverse=True)
    print(f"    Raw pairs >= {THRESHOLD}: {len(candidates)}")

    classified = {
        "HIGH_CONFIDENCE_DUPLICATE": [],
        "POLYMORPHIC_SIBLING": [],
        "COMPLEMENTARY_COMPANION": [],
        "ASYMMETRIC_RELATED": [],
    }

    for score, sym_a, sym_b in candidates:
        sig_a = parse_robust_signature(sym_a.signature or sym_a.name)
        sig_b = parse_robust_signature(sym_b.signature or sym_b.name)

        is_antonym, antonym_desc = is_antonym_or_inverted_pair(sig_a.func_name, sig_b.func_name)
        is_sibling, sibling_desc = is_polymorphic_sibling(sym_a, sym_b)
        io_rel = evaluate_signature_relationship(sig_a, sig_b)

        if is_sibling:
            classified["POLYMORPHIC_SIBLING"].append((score, sym_a, sym_b, sibling_desc))
        elif is_antonym or io_rel == "INVERTED_IO":
            classified["COMPLEMENTARY_COMPANION"].append((score, sym_a, sym_b, antonym_desc if is_antonym else "Inverted I/O payload"))
        elif io_rel == "MATCHING_IO_SHAPE":
            classified["HIGH_CONFIDENCE_DUPLICATE"].append((score, sym_a, sym_b, f"Matching I/O shape (ret={sig_a.return_type})"))
        else:
            classified["ASYMMETRIC_RELATED"].append((score, sym_a, sym_b, "Asymmetric parameters"))

    print("\n" + "=" * 80)
    print(f"Recalibrated Pipeline Breakdown (Threshold >= {THRESHOLD}):")
    print(f"  • Raw Candidate Pairs:        {len(candidates)}")
    print(f"  • Filtered: POLYMORPHIC_SIBLING:     {len(classified['POLYMORPHIC_SIBLING'])} pairs")
    print(f"  • Filtered: COMPLEMENTARY_COMPANION: {len(classified['COMPLEMENTARY_COMPANION'])} pairs")
    print(f"  • Filtered: ASYMMETRIC_RELATED:      {len(classified['ASYMMETRIC_RELATED'])} pairs")
    print(f"  ==================================================================")
    print(f"  • REMAINING HIGH_CONFIDENCE_DUPLICATE: {len(classified['HIGH_CONFIDENCE_DUPLICATE'])} pairs")
    print("=" * 80)

    # 5. Draw Random 20 Sample from HIGH_CONFIDENCE_DUPLICATE
    flagged = classified["HIGH_CONFIDENCE_DUPLICATE"]
    random.seed(42)  # Deterministic seed for reproducible evaluation
    sample_size = min(20, len(flagged))
    random_sample = random.sample(flagged, sample_size) if flagged else []

    print(f"\n[4] Random Sample of {sample_size} Flagged HIGH_CONFIDENCE_DUPLICATE Pairs:")
    print("=" * 80)

    real_duplicates_count = 0
    false_positives_count = 0

    for i, (score, sym_a, sym_b, detail) in enumerate(random_sample, 1):
        rel_a = sym_a.file_path.split("AuraAI")[-1]
        rel_b = sym_b.file_path.split("AuraAI")[-1]
        doc_a = (sym_a.docstring or "").replace("\n", " ")[:90]
        doc_b = (sym_b.docstring or "").replace("\n", " ")[:90]

        print(f"\nSample {i:2d} [Cosine: {score:.4f}] ({detail})")
        print(f"  A: {sym_a.qualified_name} in ...{rel_a}")
        print(f"     Sig: {sym_a.signature}")
        print(f"     Doc: {doc_a}...")
        print(f"  B: {sym_b.qualified_name} in ...{rel_b}")
        print(f"     Sig: {sym_b.signature}")
        print(f"     Doc: {doc_b}...")


if __name__ == "__main__":
    run_recalibrated_evaluation()
