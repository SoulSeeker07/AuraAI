"""
Unit tests for WorkspaceJail multi-root support, FileManager file.organize & file.move,
TaskDecomposer organize intent branch, and capability registry consistency.
"""

from pathlib import Path
import pytest

from core.capabilities.capability_registry import CapabilityRegistry
from core.orchestration.task_decomposer import TaskDecomposer
from desktop.native.managers.file_manager import FileManager
from desktop.native.sandbox.workspace_jail import WorkspaceJail


# ==============================================================================
# 1. WorkspaceJail Multi-Root and Blocked Segment Tests
# ==============================================================================

def test_add_allowed_root_rejects_nonexistent(tmp_path):
    jail = WorkspaceJail(workspace_root=str(tmp_path))
    with pytest.raises(ValueError, match="Cannot allow-list nonexistent root"):
        jail.add_allowed_root(str(tmp_path / "does_not_exist"))


def test_blocked_segment_inside_allowed_root(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    docs = tmp_path / "external_docs"
    docs.mkdir()
    (docs / "notes.txt").write_text("hello")

    jail = WorkspaceJail(workspace_root=str(ws))
    jail.add_allowed_root(str(docs))

    # Regular files inside allowed root should pass
    assert jail.is_path_inside_workspace(docs / "notes.txt") is True

    # All 10 blocked segments inside an additional allowed root must be blocked
    for blocked_seg in [".ssh", ".aws", ".gnupg", ".azure", ".kube", ".docker", ".git", ".npmrc", ".netrc", "appdata"]:
        blocked_path = docs / blocked_seg / "secret.txt"
        assert jail.is_path_inside_workspace(blocked_path) is False, f"Expected {blocked_seg} to be blocked in allowed root"


def test_primary_workspace_allows_git_but_blocks_credentials(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / ".git").mkdir()
    (ws / ".git" / "config").write_text("[core]")
    (ws / ".ssh").mkdir()
    (ws / ".ssh" / "id_rsa").write_text("key")

    jail = WorkspaceJail(workspace_root=str(ws))
    # Primary workspace allows .git for project VCS / HMAC gating
    assert jail.is_path_inside_workspace(ws / ".git" / "config") is True
    # Primary workspace still blocks .ssh / .aws credentials
    assert jail.is_path_inside_workspace(ws / ".ssh" / "id_rsa") is False


def test_allowed_roots_contains_multiple(tmp_path):
    root1 = tmp_path / "root1"
    root2 = tmp_path / "root2"
    root1.mkdir()
    root2.mkdir()

    jail = WorkspaceJail(workspace_root=str(root1), allowed_roots=[root2])
    assert jail.is_path_inside_workspace(root1 / "file1.txt") is True
    assert jail.is_path_inside_workspace(root2 / "file2.txt") is True
    assert jail.is_path_inside_workspace(tmp_path / "outside.txt") is False


# ==============================================================================
# 2. FileManager file.organize & file.move Tests
# ==============================================================================

def test_file_organize_sorts_by_category(tmp_path):
    test_dir = tmp_path / "test_folder"
    test_dir.mkdir()
    (test_dir / "report.pdf").write_text("pdf content")
    (test_dir / "photo.png").write_text("png content")
    (test_dir / "notes.txt").write_text("txt content")
    (test_dir / "data.csv").write_text("csv content")
    (test_dir / "song.mp3").write_text("mp3 content")

    fm = FileManager(workspace_root=str(tmp_path))
    result = fm.execute("file.organize", arguments={"path": str(test_dir), "strategy": "category"})

    assert result.success is True
    assert (test_dir / "Documents" / "report.pdf").exists()
    assert (test_dir / "Documents" / "notes.txt").exists()
    assert (test_dir / "Images" / "photo.png").exists()
    assert (test_dir / "Spreadsheets" / "data.csv").exists()
    assert (test_dir / "Audio" / "song.mp3").exists()
    assert result.data["moved_count"] == 5
    assert result.data["failed_count"] == 0


def test_file_organize_unmapped_and_extensionless_files(tmp_path):
    test_dir = tmp_path / "misc_folder"
    test_dir.mkdir()
    (test_dir / "unknown.xyz").write_text("custom data")
    (test_dir / "data.customext").write_text("custom")
    (test_dir / "LICENSE").write_text("MIT License")

    fm = FileManager(workspace_root=str(tmp_path))
    result = fm.execute("file.organize", arguments={"path": str(test_dir), "strategy": "category"})

    assert result.success is True
    assert (test_dir / "Other" / "unknown.xyz").exists()
    assert (test_dir / "Other" / "data.customext").exists()
    assert (test_dir / "Other" / "LICENSE").exists()
    assert result.data["moved_count"] == 3
    assert result.data["failed_count"] == 0


def test_file_organize_sorts_by_extension(tmp_path):
    test_dir = tmp_path / "ext_folder"
    test_dir.mkdir()
    (test_dir / "doc.pdf").write_text("pdf")
    (test_dir / "readme.txt").write_text("txt")
    (test_dir / "LICENSE").write_text("MIT")

    fm = FileManager(workspace_root=str(tmp_path))
    result = fm.execute("file.organize", arguments={"path": str(test_dir), "strategy": "by_extension"})

    assert result.success is True
    assert (test_dir / "pdf" / "doc.pdf").exists()
    assert (test_dir / "txt" / "readme.txt").exists()
    assert (test_dir / "no_extension" / "LICENSE").exists()
    assert result.data["moved_count"] == 3


def test_file_move_verifies_on_disk(tmp_path):
    src = tmp_path / "source.txt"
    dst = tmp_path / "sub" / "dest.txt"
    src.write_text("move me")

    fm = FileManager(workspace_root=str(tmp_path))
    result = fm.execute("file.move", arguments={"source": str(src), "destination": str(dst)})

    assert result.success is True
    assert dst.exists()
    assert not src.exists()
    assert dst.read_text() == "move me"


def test_file_organize_rejects_outside_jail(tmp_path):
    jail_root = tmp_path / "jail"
    outside_dir = tmp_path / "outside"
    jail_root.mkdir()
    outside_dir.mkdir()
    (outside_dir / "doc.pdf").write_text("pdf")

    fm = FileManager(workspace_root=str(jail_root))
    result = fm.execute("file.organize", arguments={"path": str(outside_dir)})

    assert result.success is False
    assert "outside allowed workspace" in result.error.lower() or "workspace_jail" in str(result.data).lower()


# ==============================================================================
# 3. TaskDecomposer Pattern & Intent Tests
# ==============================================================================

@pytest.mark.parametrize("goal,expected_folder_key", [
    ("organize documents folder", "documents"),
    ("organize downloads", "downloads"),
    ("sort desktop folder", "desktop"),
    ("clean up my pictures", "pictures"),
])
def test_task_decomposer_organize_patterns(goal, expected_folder_key):
    decomposer = TaskDecomposer()
    task_graph = decomposer.decompose(goal)

    assert len(task_graph.subtasks) == 1
    st = list(task_graph.subtasks.values())[0]
    assert st.capability == "file.organize"
    folder_param = st.parameters.get("folder", "").lower()
    target_dir_param = st.parameters.get("target_dir", "").lower()
    assert expected_folder_key in folder_param or expected_folder_key in target_dir_param


# ==============================================================================
# 4. Registry & Dispatch Consistency Tests
# ==============================================================================

def test_registry_dispatch_consistency():
    """Verify file.organize and file.move exist in both FileManager and Universal Registry."""
    fm = FileManager(workspace_root=".")
    assert "file.organize" in fm.capabilities
    assert "file.move" in fm.capabilities

    reg = CapabilityRegistry.get_instance()
    cap_organize = reg.get("file.organize")
    cap_move = reg.get("file.move")

    assert cap_organize is not None, "file.organize must be discoverable in Universal CapabilityRegistry"
    assert cap_move is not None, "file.move must be discoverable in Universal CapabilityRegistry"
    assert cap_organize.is_live is True
    assert cap_move.is_live is True
