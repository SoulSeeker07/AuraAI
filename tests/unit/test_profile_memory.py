import pytest
from pathlib import Path
from src.memory.profile_memory import ProfileMemory
from Memory import Memory


@pytest.fixture
def temp_profile_mem(tmp_path):
    db_file = tmp_path / "test_profile.db"
    ProfileMemory.reset_instance()
    mem = ProfileMemory(db_path=db_file)
    yield mem
    ProfileMemory.reset_instance()


def test_profile_memory_type_serialization_and_crud(temp_profile_mem):
    """Verify that ProfileMemory preserves types and supports full CRUD without decay."""
    # 1. Store various types
    temp_profile_mem.set_fact("identity", "name", "Sreekanta")
    temp_profile_mem.set_fact("preferences", "editor", "vscode")
    temp_profile_mem.set_fact("preferences", "font_size", 14)
    temp_profile_mem.set_fact("preferences", "sound_volume", 0.85)
    temp_profile_mem.set_fact("preferences", "developer_mode", True)
    temp_profile_mem.set_fact("preferences", "enabled_tools", ["python", "terminal", "git"])
    temp_profile_mem.set_fact("preferences", "theme_config", {"mode": "dark", "accent": "cyan"})

    # 2. Retrieve and assert exact types
    assert temp_profile_mem.get_fact("identity", "name") == "Sreekanta"
    assert temp_profile_mem.get_fact("preferences", "editor") == "vscode"
    assert temp_profile_mem.get_fact("preferences", "font_size") == 14
    assert isinstance(temp_profile_mem.get_fact("preferences", "font_size"), int)
    assert temp_profile_mem.get_fact("preferences", "sound_volume") == 0.85
    assert isinstance(temp_profile_mem.get_fact("preferences", "sound_volume"), float)
    assert temp_profile_mem.get_fact("preferences", "developer_mode") is True
    assert isinstance(temp_profile_mem.get_fact("preferences", "developer_mode"), bool)
    assert temp_profile_mem.get_fact("preferences", "enabled_tools") == ["python", "terminal", "git"]
    assert temp_profile_mem.get_fact("preferences", "theme_config") == {"mode": "dark", "accent": "cyan"}

    # 3. List facts by category
    identity_facts = temp_profile_mem.get_identity()
    assert identity_facts == {"name": "Sreekanta"}

    pref_facts = temp_profile_mem.get_preferences()
    assert len(pref_facts) == 6
    assert pref_facts["editor"] == "vscode"

    # 4. Update an existing fact
    temp_profile_mem.set_fact("preferences", "font_size", 16)
    assert temp_profile_mem.get_fact("preferences", "font_size") == 16

    # 5. Delete fact
    deleted = temp_profile_mem.delete_fact("preferences", "sound_volume")
    assert deleted is True
    assert temp_profile_mem.get_fact("preferences", "sound_volume") is None
    assert temp_profile_mem.delete_fact("preferences", "non_existent") is False


def test_profile_memory_persistence_across_connections(tmp_path):
    """Verify that ProfileMemory commits changes ACID-style so a new connection reads them immediately."""
    db_file = tmp_path / "persist_test.db"
    mem1 = ProfileMemory(db_path=db_file)
    mem1.set_fact("identity", "role", "Lead AI Engineer")

    # Open completely separate instance pointing to same file
    mem2 = ProfileMemory(db_path=db_file)
    assert mem2.get_fact("identity", "role") == "Lead AI Engineer"


def test_profile_memory_export_and_import(temp_profile_mem):
    """Verify full export and import of structured profile data."""
    initial_data = {
        "identity": {"name": "Aura", "version": "1.0"},
        "preferences": {"theme": "cyberpunk", "auto_update": False},
    }
    temp_profile_mem.import_profile(initial_data)

    exported = temp_profile_mem.export_profile()
    assert exported["identity"]["name"] == "Aura"
    assert exported["identity"]["version"] == "1.0"
    assert exported["preferences"]["theme"] == "cyberpunk"
    assert exported["preferences"]["auto_update"] is False


def test_memory_py_bridge_syncs_with_profile_memory(tmp_path, monkeypatch):
    """Verify that legacy Memory.py fact_value and upsert_fact read and write to ProfileMemory."""
    db_file = tmp_path / "bridge_profile.db"
    prof_mem = ProfileMemory(db_path=db_file)
    monkeypatch.setattr(ProfileMemory, "get_instance", classmethod(lambda cls, *args, **kwargs: prof_mem))

    legacy_db = tmp_path / "legacy_memory.db"
    legacy_mem = Memory(db_path=str(legacy_db))

    # Writing via legacy upsert_fact syncs to ProfileMemory
    legacy_mem.upsert_fact("profile", "city", "Bengaluru")
    assert prof_mem.get_fact("profile", "city") == "Bengaluru"

    # Reading via legacy fact_value reads directly from ProfileMemory
    prof_mem.set_fact("profile", "preferred_language", "Python")
    val = legacy_mem.fact_value("profile", "preferred_language")
    assert val == "Python"


def test_context_builder_injects_profile_memory_facts(tmp_path, monkeypatch):
    """Verify that ContextBuilder injects ProfileMemory facts into the system messages deterministically."""
    from brain.context_builder import ContextBuilder
    from brain.models import Intent

    db_file = tmp_path / "ctx_profile.db"
    prof_mem = ProfileMemory(db_path=db_file)
    prof_mem.set_fact("identity", "preferred_name", "Alex")
    prof_mem.set_fact("preferences", "preferred_ide", "VSCode")
    monkeypatch.setattr(ProfileMemory, "get_instance", classmethod(lambda cls, *args, **kwargs: prof_mem))

    builder = ContextBuilder(memory=None)
    ctx = builder.build("Hello Aura", intent=Intent("chat"))

    system_contents = [m.content for m in ctx.messages if m.role == "system"]
    assert any("Verified User Profile (Deterministic):" in sc for sc in system_contents)
    assert any("'preferred_name': 'Alex'" in sc for sc in system_contents)
    assert any("'preferred_ide': 'VSCode'" in sc for sc in system_contents)

