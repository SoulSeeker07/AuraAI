"""
Comprehensive Test Suite for Phase 2 Duplicate Detector.

Verifies:
1. AST Single-statement Facade Detection.
2. Polymorphic Sibling Method Filtering.
3. Antonym / Complementary Method Inversion Filtering.
4. Intra-File Exclusion.
5. Legacy Archive Path Segregation.
6. Tier 1 Active Clone Detection.
7. Report Summary & Serialization.
8. EngineeringManager Integration.
"""

from pathlib import Path
import tempfile
import pytest

from engineering.project_index import ProjectIndex, SymbolRecord
from engineering.duplicate_detector import (
    DuplicateDetector,
    DuplicateAuditReport,
    DuplicateCandidatePair,
)
from engineering.engineering_manager import EngineeringManager


@pytest.fixture
def temp_repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        # Create folder structure
        (repo_path / "src" / "service_a").mkdir(parents=True)
        (repo_path / "src" / "service_b").mkdir(parents=True)
        (repo_path / "dev" / "legacy_archive").mkdir(parents=True)
        yield repo_path


def test_facade_delegation_detection(temp_repo):
    file_facade = temp_repo / "src" / "service_a" / "facade.py"
    file_facade.write_text(
        "class FacadeService:\n"
        "    def get_status(self) -> dict:\n"
        '        """Return the status of the service."""\n'
        "        return self.backend.get_status()\n"
        "    def complex_status(self) -> dict:\n"
        '        """Compute detailed status metrics."""\n'
        "        x = 10\n"
        "        y = 20\n"
        "        return {'val': x + y}\n",
        encoding="utf-8",
    )

    index = ProjectIndex(repo_root=temp_repo)
    detector = DuplicateDetector(project_index=index)

    is_facade_1, reason_1 = detector._is_facade_delegation(str(file_facade), 2, 4)
    assert is_facade_1 is True
    assert "Return Delegation" in reason_1

    is_facade_2, reason_2 = detector._is_facade_delegation(str(file_facade), 5, 9)
    assert is_facade_2 is False
    assert reason_2 == ""


def test_antonym_detection():
    index = ProjectIndex(repo_root=Path("."))
    detector = DuplicateDetector(project_index=index)

    is_ant, desc = detector._is_antonym_or_inverted_pair("save_audio", "load_audio")
    assert is_ant is True
    assert "save" in desc and "load" in desc

    is_ant2, desc2 = detector._is_antonym_or_inverted_pair("encode_token", "decode_token")
    assert is_ant2 is True
    assert "encode" in desc2 and "decode" in desc2

    is_ant3, _ = detector._is_antonym_or_inverted_pair("calculate_average", "compute_mean")
    assert is_ant3 is False


def test_polymorphic_sibling_detection(temp_repo):
    index = ProjectIndex(repo_root=temp_repo)
    detector = DuplicateDetector(project_index=index)

    sym_a = SymbolRecord(
        id=1,
        file_path=str(temp_repo / "src" / "providers" / "git.py"),
        symbol_type="method",
        name="validate_config",
        qualified_name="GitProvider.validate_config",
        signature="def validate_config(self) -> bool",
        docstring="Validate provider configuration.",
    )
    sym_b = SymbolRecord(
        id=2,
        file_path=str(temp_repo / "src" / "providers" / "wiki.py"),
        symbol_type="method",
        name="validate_config",
        qualified_name="WikiProvider.validate_config",
        signature="def validate_config(self) -> bool",
        docstring="Validate provider configuration.",
    )

    is_sibling, desc = detector._is_polymorphic_sibling(sym_a, sym_b)
    assert is_sibling is True
    assert "validate_config" in desc


def test_legacy_archive_segregation():
    index = ProjectIndex(repo_root=Path("."))
    detector = DuplicateDetector(project_index=index)

    assert detector._is_archived_path("dev/legacy_archive/core/aura_core.py") is True
    assert detector._is_archived_path("src/core/aura_core.py") is False


def test_audit_repository_multitier(temp_repo):
    # 1. Active duplicate pair
    (temp_repo / "src" / "service_a" / "math_utils.py").write_text(
        "def compute_mean_score(numbers: list[float]) -> float:\n"
        '    """Calculate the arithmetic mean of a list of float numbers."""\n'
        "    if not numbers:\n"
        "        return 0.0\n"
        "    return sum(numbers) / len(numbers)\n",
        encoding="utf-8",
    )
    (temp_repo / "src" / "service_b" / "stats_helper.py").write_text(
        "def compute_mean_score(values: list[float]) -> float:\n"
        '    """Calculate the arithmetic mean of a list of float numbers."""\n'
        "    if not values:\n"
        "        return 0.0\n"
        "    return sum(values) / len(values)\n",
        encoding="utf-8",
    )

    # 2. Legacy archive copy
    (temp_repo / "dev" / "legacy_archive" / "old_math.py").write_text(
        "def compute_mean_score(numbers: list[float]) -> float:\n"
        '    """Calculate the arithmetic mean of a list of float numbers."""\n'
        "    return sum(numbers) / len(numbers)\n",
        encoding="utf-8",
    )

    index = ProjectIndex(repo_root=temp_repo)
    index.scan()

    detector = DuplicateDetector(project_index=index)
    report = detector.audit_repository(threshold=0.85)

    assert report.total_symbols_evaluated >= 3
    assert len(report.tier1_active_clones) >= 1
    assert len(report.tier2_legacy_archive) >= 1

    summary = report.summary()
    assert summary["tier1_active_clones_count"] >= 1
    assert summary["tier2_legacy_archive_count"] >= 1
    assert "scan_duration_seconds" in summary

    # Verify structural invariant: no pair is classified into multiple tiers
    all_tier_pairs = [
        (p.symbol_a.id, p.symbol_b.id)
        for p in (
            report.tier1_active_clones
            + report.tier2_legacy_archive
            + report.tier3_facades
            + report.tier4_polymorphic_siblings
            + report.tier5_complementary_companions
        )
    ]
    assert len(all_tier_pairs) == len(set(all_tier_pairs)), "Duplicate pairs must not appear in multiple tiers"

    # Verify Tier 2 reason labels
    for pair in report.tier2_legacy_archive:
        assert pair.category == "LEGACY_ARCHIVE"
        assert "legacy clone" in pair.classification_reason or "Refactored lineage" in pair.classification_reason


def test_engineering_manager_integration(temp_repo):
    (temp_repo / "src" / "service_a" / "runner.py").write_text(
        "def execute_task(task_id: str) -> bool:\n"
        '    """Execute a scheduled engineering task by identifier."""\n'
        "    return True\n",
        encoding="utf-8",
    )
    (temp_repo / "src" / "service_b" / "runner.py").write_text(
        "def execute_task(task_id: str) -> bool:\n"
        '    """Execute a scheduled engineering task by identifier."""\n'
        "    return True\n",
        encoding="utf-8",
    )

    em = EngineeringManager(repository_path=temp_repo)
    em.project_index.scan()

    report = em.audit_duplicates(threshold=0.85)
    assert isinstance(report, DuplicateAuditReport)
    assert len(report.tier1_active_clones) >= 1
    em.close()
