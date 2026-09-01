"""
Duplicate Detector — Phase 2 Semantic & Architectural Duplicate Engine.

Provides multi-tier codebase duplicate detection:
- Tier 1: Active Architectural Clones (Cross-module actionable duplicates)
- Tier 2: Legacy Archive Clones (Historical/frozen backups)
- Tier 3: Facade Delegations (1-statement pass-through wrappers)
- Tier 4: Polymorphic Sibling Implementations (Shared interface/protocol methods)

Compound filtering pipeline:
- all-MiniLM-L6-v2 embeddings with cosine similarity (threshold >= 0.85)
- AST 1-statement facade detection
- Morphological & dictionary antonym inversion check
- Intra-file / same-class exclusion
- Sibling provider/tool interface detection
"""

from __future__ import annotations

import ast
import logging
import re
import textwrap
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .project_index import ProjectIndex, SymbolRecord

logger = logging.getLogger(__name__)


# Common lifecycle/protocol methods across classes
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


@dataclass
class DuplicateCandidatePair:
    """Represents a pair of symbols identified by the duplicate detector."""

    similarity: float
    symbol_a: SymbolRecord
    symbol_b: SymbolRecord
    category: str  # 'ACTIVE_CLONE' | 'LEGACY_ARCHIVE' | 'FACADE' | 'POLYMORPHIC_SIBLING' | 'COMPLEMENTARY'
    classification_reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "similarity": round(self.similarity, 4),
            "symbol_a": self.symbol_a.to_dict(),
            "symbol_b": self.symbol_b.to_dict(),
            "category": self.category,
            "classification_reason": self.classification_reason,
        }


@dataclass
class DuplicateAuditReport:
    """Comprehensive multi-tier duplicate audit report."""

    scan_duration_seconds: float
    total_symbols_evaluated: int
    threshold: float
    tier1_active_clones: list[DuplicateCandidatePair] = field(default_factory=list)
    tier2_legacy_archive: list[DuplicateCandidatePair] = field(default_factory=list)
    tier3_facades: list[DuplicateCandidatePair] = field(default_factory=list)
    tier4_polymorphic_siblings: list[DuplicateCandidatePair] = field(default_factory=list)
    tier5_complementary_companions: list[DuplicateCandidatePair] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "total_symbols_evaluated": self.total_symbols_evaluated,
            "scan_duration_seconds": round(self.scan_duration_seconds, 2),
            "threshold": self.threshold,
            "tier1_active_clones_count": len(self.tier1_active_clones),
            "tier2_legacy_archive_count": len(self.tier2_legacy_archive),
            "tier3_facades_count": len(self.tier3_facades),
            "tier4_polymorphic_siblings_count": len(self.tier4_polymorphic_siblings),
            "tier5_complementary_companions_count": len(self.tier5_complementary_companions),
        }


class DuplicateDetector:
    """
    On-Demand / Batch Duplicate & Architecture Audit Engine.
    Uses all-MiniLM-L6-v2 embeddings + AST compound filters.
    """

    def __init__(self, project_index: ProjectIndex, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.project_index = project_index
        self.model_name = model_name
        self._model: SentenceTransformer | None = None

    def _get_model(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model '{self.model_name}'...")
            self._model = SentenceTransformer(self.model_name)
        return self._model


    @staticmethod
    def _is_archived_path(path_str: str) -> bool:
        p_lower = path_str.lower()
        return "legacy_archive" in p_lower or "legacy" in p_lower or "archive" in p_lower

    @staticmethod
    def _extract_primary_verbs(func_name: str) -> list[str]:
        clean = re.sub(r"[^a-zA-Z0-9_]", "", func_name)
        parts = [p.lower() for p in clean.split("_") if p]
        return parts[:2] if parts else [func_name.lower()]

    def _is_antonym_or_inverted_pair(self, name_a: str, name_b: str) -> tuple[bool, str]:
        verbs_a = self._extract_primary_verbs(name_a)
        verbs_b = self._extract_primary_verbs(name_b)

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

    def _is_polymorphic_sibling(self, sym_a: SymbolRecord, sym_b: SymbolRecord) -> tuple[bool, str]:
        if sym_a.symbol_type == "method" and sym_b.symbol_type == "method":
            if sym_a.name == sym_b.name:
                if sym_a.name in COMMON_INTERFACE_METHODS:
                    return True, f"Standard interface method: '{sym_a.name}()'"
                path_a = Path(sym_a.file_path).parent
                path_b = Path(sym_b.file_path).parent
                if path_a == path_b or path_a.parent == path_b.parent:
                    return True, f"Sibling class method in '{path_a.name}': '{sym_a.name}()'"

        if sym_a.name in COMMON_INTERFACE_METHODS and sym_b.name in COMMON_INTERFACE_METHODS:
            return True, f"Common protocol methods: '{sym_a.name}' vs '{sym_b.name}'"

        return False, ""

    def _is_facade_delegation(self, file_path: str, line_start: int | None, line_end: int | None) -> tuple[bool, str]:
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

    def audit_repository(self, threshold: float = 0.85) -> DuplicateAuditReport:
        """
        Executes a full multi-tier deduplication audit across all symbols in the ProjectIndex.
        """
        t0 = time.perf_counter()
        logger.info(f"Starting DuplicateDetector audit (threshold: {threshold})...")

        with self.project_index._get_connection() as conn:
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

        symbols: list[SymbolRecord] = []
        seen: set[str] = set()
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

        if not symbols:
            return DuplicateAuditReport(
                scan_duration_seconds=time.perf_counter() - t0,
                total_symbols_evaluated=0,
                threshold=threshold,
            )

        texts = [f"{s.signature or s.name}\n{s.docstring.strip()}" for s in symbols]
        model = self._get_model()
        embeddings = model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False)

        from sklearn.metrics.pairwise import cosine_similarity
        sim_matrix = cosine_similarity(embeddings, embeddings)

        n = len(symbols)

        report = DuplicateAuditReport(
            scan_duration_seconds=0.0,
            total_symbols_evaluated=n,
            threshold=threshold,
        )

        for i in range(n):
            for j in range(i + 1, n):
                score = float(sim_matrix[i, j])
                if score >= threshold:
                    sym_a = symbols[i]
                    sym_b = symbols[j]

                    # 1. Intra-File exclusion
                    if sym_a.file_path == sym_b.file_path:
                        continue

                    # 2. Legacy archive segregation
                    if self._is_archived_path(sym_a.file_path) or self._is_archived_path(sym_b.file_path):
                        if score >= 0.99:
                            reason = "Exact legacy clone (candidate to safely delete archive copy)"
                        else:
                            reason = "Refactored lineage (functionality evolved into active package; archive copy is historical reference)"
                        pair = DuplicateCandidatePair(
                            similarity=score,
                            symbol_a=sym_a,
                            symbol_b=sym_b,
                            category="LEGACY_ARCHIVE",
                            classification_reason=reason,
                        )
                        report.tier2_legacy_archive.append(pair)
                        continue

                    # 3. Polymorphic sibling filter
                    is_sibling, sibling_desc = self._is_polymorphic_sibling(sym_a, sym_b)
                    if is_sibling:
                        pair = DuplicateCandidatePair(
                            similarity=score,
                            symbol_a=sym_a,
                            symbol_b=sym_b,
                            category="POLYMORPHIC_SIBLING",
                            classification_reason=sibling_desc,
                        )
                        report.tier4_polymorphic_siblings.append(pair)
                        continue

                    # 4. Antonym companion filter
                    is_antonym, antonym_desc = self._is_antonym_or_inverted_pair(sym_a.name, sym_b.name)
                    if is_antonym:
                        pair = DuplicateCandidatePair(
                            similarity=score,
                            symbol_a=sym_a,
                            symbol_b=sym_b,
                            category="COMPLEMENTARY",
                            classification_reason=antonym_desc,
                        )
                        report.tier5_complementary_companions.append(pair)
                        continue

                    # 5. AST Facade delegation filter
                    is_facade_a, _ = self._is_facade_delegation(sym_a.file_path, sym_a.line_start, sym_a.line_end)
                    is_facade_b, _ = self._is_facade_delegation(sym_b.file_path, sym_b.line_start, sym_b.line_end)
                    if is_facade_a or is_facade_b:
                        facade_name = sym_a.name if is_facade_a else sym_b.name
                        pair = DuplicateCandidatePair(
                            similarity=score,
                            symbol_a=sym_a,
                            symbol_b=sym_b,
                            category="FACADE",
                            classification_reason=f"'{facade_name}' is a 1-line pass-through facade delegation",
                        )
                        report.tier3_facades.append(pair)
                        continue

                    # 6. Active Architectural Clone
                    pair = DuplicateCandidatePair(
                        similarity=score,
                        symbol_a=sym_a,
                        symbol_b=sym_b,
                        category="ACTIVE_CLONE",
                        classification_reason="Cross-module active candidate duplication",
                    )
                    report.tier1_active_clones.append(pair)

        # Sort each tier by similarity descending
        report.tier1_active_clones.sort(key=lambda x: x.similarity, reverse=True)
        report.tier2_legacy_archive.sort(key=lambda x: x.similarity, reverse=True)
        report.tier3_facades.sort(key=lambda x: x.similarity, reverse=True)

        report.scan_duration_seconds = time.perf_counter() - t0
        logger.info(
            f"Duplicate audit complete in {report.scan_duration_seconds:.2f}s: "
            f"{len(report.tier1_active_clones)} active clones, {len(report.tier2_legacy_archive)} archive clones."
        )
        return report
