"""
Real-World Codebase Evaluation of Phase 2 Semantic Duplicate Detection Pipeline.

Runs the complete pipeline across all real symbols stored in ProjectIndex:
1. Extracts all real functions/methods with docstrings/signatures from AuraAI.
2. Embeds all symbols with all-MiniLM-L6-v2.
3. Finds top candidate pairs scoring >= 0.75 cosine similarity.
4. Applies enhanced morphological + dictionary verb disambiguation and robust signature I/O shape comparison.
5. Classifies every real candidate pair into:
   - HIGH_CONFIDENCE_DUPLICATE
   - COMPLEMENTARY_COMPANION
   - RELATED_UTILITY
6. Reports the exact findings, real duplicate clusters, and noisy edge cases.
"""

import ast
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


# ── 1. Comprehensive Programming Antonym & Prefix Rules ──────────────────────

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
    """Extract action tokens from snake_case function name."""
    clean = re.sub(r"[^a-zA-Z0-9_]", "", func_name)
    parts = [p.lower() for p in clean.split("_") if p]
    return parts[:2] if parts else [func_name.lower()]


def is_antonym_or_inverted_pair(name_a: str, name_b: str) -> tuple[bool, str]:
    """
    Checks dictionary antonyms and morphological prefixes ('un-', 'de-', 'dis-').
    """
    verbs_a = extract_primary_verbs(name_a)
    verbs_b = extract_primary_verbs(name_b)

    for va in verbs_a:
        for vb in verbs_b:
            if va == vb:
                continue

            # 1. Exact Dictionary Match
            if ANTONYM_MAP.get(va) == vb:
                return True, f"Antonym pair '{va}' <-> '{vb}'"

            # 2. Morphological Prefix Inversion (e.g. serialize / deserialize, pack / unpack)
            for prefix in ("un", "de", "dis", "in", "non"):
                if vb == prefix + va or va == prefix + vb:
                    return True, f"Prefix antonym '{va}' <-> '{vb}'"

    return False, ""


# ── 2. Robust Signature Shape & Type Inversion (Handling noisy args) ───────────

@dataclass
class RobustSignatureShape:
    func_name: str
    required_param_types: list[str]
    optional_param_types: list[str]
    return_type: str | None


def parse_robust_signature(sig_text: str) -> RobustSignatureShape:
    """Parses signatures into required payload types and optional/default types."""
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
            # Ignore standard auxiliary options from core payload comparison
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
    """Robust signature comparison across real code."""
    all_a = set(sig_a.required_param_types + sig_a.optional_param_types)
    all_b = set(sig_b.required_param_types + sig_b.optional_param_types)
    ret_a = sig_a.return_type
    ret_b = sig_b.return_type

    # 1. Type Inversion: different return types where payload types cross over
    if ret_a and ret_b and ret_a != ret_b and ret_a not in ("None", "bool") and ret_b not in ("None", "bool"):
        if (ret_a in all_b or any(ret_a in p for p in all_b)) and (
            ret_b in all_a or any(ret_b in p for p in all_a)
        ):
            return "INVERTED_IO"

    # 2. Matching I/O shape: same return type category, matching required parameter count
    if ret_a == ret_b and len(sig_a.required_param_types) == len(sig_b.required_param_types):
        return "MATCHING_IO_SHAPE"

    return "ASYMMETRIC_SHAPE"


# ── 3. Run Pipeline on Real Repository Index ─────────────────────────────────

def run_real_codebase_evaluation():
    print("=" * 80)
    print("Evaluating Phase 2 Pipeline on Real AuraAI Codebase Symbols")
    print("=" * 80)

    index = ProjectIndex(repo_root=repo_root)
    index.scan()

    # Query all real functions/methods with docstrings (excluding test/scratch files)
    with index._get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, file_path, symbol_type, name, qualified_name, signature, docstring, line_start, line_end
            FROM symbols
            WHERE docstring IS NOT NULL 
              AND length(docstring) > 15
              AND symbol_type IN ('function', 'method', 'async_function')
              AND file_path NOT LIKE '%test%'
              AND file_path NOT LIKE '%scratch%'
              AND file_path NOT LIKE '%__pycache__%'
            ORDER BY id ASC
            """
        ).fetchall()

    symbols = [
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
        for r in rows
    ]

    print(f"\n[1] Extracted {len(symbols)} real functions with docstrings from ProjectIndex.")

    # Deduplicate exact same qualified names across duplicate paths if any
    unique_symbols = []
    seen = set()
    for s in symbols:
        k = f"{s.file_path}:{s.qualified_name}"
        if k not in seen:
            seen.add(k)
            unique_symbols.append(s)

    symbols = unique_symbols
    print(f"    Unique candidate symbols: {len(symbols)}")

    # Formulate embeddings text
    texts = [f"{s.signature or s.name}\n{s.docstring.strip()}" for s in symbols]

    # Load model and compute embeddings
    print("\n[2] Embedding all real symbols with all-MiniLM-L6-v2...")
    t0 = time.perf_counter()
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
    emb_time = time.perf_counter() - t0
    print(f"    Generated matrix {embeddings.shape} in {emb_time:.2f}s ({len(symbols) / emb_time:.1f} symbols/sec)")

    # Compute pairwise similarity matrix
    print("\n[3] Computing all pairwise similarities and applying 2-stage filter...")
    sim_matrix = cosine_similarity(embeddings, embeddings)

    # Filter upper triangle for pairs >= 0.75 (excluding self and methods within the same class)
    candidates = []
    n = len(symbols)
    for i in range(n):
        for j in range(i + 1, n):
            score = float(sim_matrix[i, j])
            if score >= 0.75:
                sym_a = symbols[i]
                sym_b = symbols[j]

                # Skip if exact same file and same scope
                if sym_a.file_path == sym_b.file_path and sym_a.name == sym_b.name:
                    continue

                candidates.append((score, sym_a, sym_b))

    candidates.sort(key=lambda x: x[0], reverse=True)
    print(f"    Total candidate pairs scoring >= 0.75: {len(candidates)}")

    # Classify each candidate pair
    classified_results = {
        "HIGH_CONFIDENCE_DUPLICATE": [],
        "COMPLEMENTARY_COMPANION": [],
        "RELATED_UTILITY": [],
    }

    for score, sym_a, sym_b in candidates:
        sig_a = parse_robust_signature(sym_a.signature or sym_a.name)
        sig_b = parse_robust_signature(sym_b.signature or sym_b.name)

        is_antonym, antonym_desc = is_antonym_or_inverted_pair(sig_a.func_name, sig_b.func_name)
        io_rel = evaluate_signature_relationship(sig_a, sig_b)

        if is_antonym or io_rel == "INVERTED_IO":
            cat = "COMPLEMENTARY_COMPANION"
            detail = antonym_desc if is_antonym else "Inverted input/output type payload"
        elif io_rel == "MATCHING_IO_SHAPE" and not is_antonym:
            cat = "HIGH_CONFIDENCE_DUPLICATE"
            detail = f"Matching I/O shape (ret={sig_a.return_type}, params={len(sig_a.required_param_types)})"
        else:
            cat = "RELATED_UTILITY"
            detail = "Similar domain text but asymmetric signature shape"

        classified_results[cat].append((score, sym_a, sym_b, detail))

    print("\n" + "=" * 80)
    print(f"Pipeline Classification Summary:")
    print(f"  • HIGH_CONFIDENCE_DUPLICATE: {len(classified_results['HIGH_CONFIDENCE_DUPLICATE'])} pairs")
    print(f"  • COMPLEMENTARY_COMPANION:   {len(classified_results['COMPLEMENTARY_COMPANION'])} pairs")
    print(f"  • RELATED_UTILITY:           {len(classified_results['RELATED_UTILITY'])} pairs")
    print("=" * 80)

    # 4. Display representative samples from each category
    print("\n[A] Top HIGH_CONFIDENCE_DUPLICATE Discoveries in Real Codebase:")
    for idx, (score, sym_a, sym_b, detail) in enumerate(classified_results["HIGH_CONFIDENCE_DUPLICATE"][:5], 1):
        rel_a = sym_a.file_path.split("AuraAI")[-1]
        rel_b = sym_b.file_path.split("AuraAI")[-1]
        print(f"\n  Duplicate Pair {idx} [Cosine: {score:.4f}] ({detail})")
        print(f"    Func A: {sym_a.qualified_name} in ...{rel_a}")
        print(f"            Sig: {sym_a.signature}")
        print(f"            Doc: {(sym_a.docstring or '')[:80].strip()}...")
        print(f"    Func B: {sym_b.qualified_name} in ...{rel_b}")
        print(f"            Sig: {sym_b.signature}")
        print(f"            Doc: {(sym_b.docstring or '')[:80].strip()}...")

    print("\n[B] Top COMPLEMENTARY_COMPANION (Demoted Counterparts) in Real Codebase:")
    for idx, (score, sym_a, sym_b, detail) in enumerate(classified_results["COMPLEMENTARY_COMPANION"][:5], 1):
        rel_a = sym_a.file_path.split("AuraAI")[-1]
        rel_b = sym_b.file_path.split("AuraAI")[-1]
        print(f"\n  Companion Pair {idx} [Cosine: {score:.4f}] (Demoted Reason: {detail})")
        print(f"    Func A: {sym_a.qualified_name} in ...{rel_a}")
        print(f"            Sig: {sym_a.signature}")
        print(f"    Func B: {sym_b.qualified_name} in ...{rel_b}")
        print(f"            Sig: {sym_b.signature}")

    print("\n[C] Top RELATED_UTILITY (Asymmetric / Non-Duplicate Context):")
    for idx, (score, sym_a, sym_b, detail) in enumerate(classified_results["RELATED_UTILITY"][:3], 1):
        rel_a = sym_a.file_path.split("AuraAI")[-1]
        rel_b = sym_b.file_path.split("AuraAI")[-1]
        print(f"\n  Related Utility {idx} [Cosine: {score:.4f}] ({detail})")
        print(f"    Func A: {sym_a.qualified_name} in ...{rel_a} | {sym_a.signature}")
        print(f"    Func B: {sym_b.qualified_name} in ...{rel_b} | {sym_b.signature}")

    print("\n" + "=" * 80)
    print("Real Codebase Evaluation Completed.")
    print("=" * 80)


if __name__ == "__main__":
    run_real_codebase_evaluation()
