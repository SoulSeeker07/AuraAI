import pytest
from pathlib import Path
from scripts.check_duplicate_methods import find_duplicate_class_methods

def test_codebase_has_zero_duplicate_class_methods():
    """
    Automated regression gate ensuring no Python class in the codebase
    defines duplicate method names that silently shadow earlier implementations.
    """
    project_root = Path(__file__).resolve().parent.parent
    src_dir = project_root / "src"

    duplicates = find_duplicate_class_methods(src_dir)

    assert not duplicates, (
        f"Found {len(duplicates)} duplicate class method(s) that cause silent shadowing:\n"
        + "\n".join(
            f"  • {p.relative_to(project_root)} -> Class '{cls_name}': method '{m_name}' (defined {cnt} times)"
            for p, cls_name, m_name, cnt in duplicates
        )
    )
