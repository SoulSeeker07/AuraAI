import sys
from pathlib import Path
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from Memory import Memory
from memory.manager.memory_manager import MemoryManager

with tempfile.TemporaryDirectory() as tmp_dir:
    tmp_path = Path(tmp_dir)
    mem = Memory(db_path=tmp_path / "Memory.db", chat_log_path=tmp_path / "ChatLog.json")
    mem.upsert_fact("profile", "editor_theme", "Monokai Pro with customized glyph icons")
    mem.upsert_fact("hobby", "gardening", "Growing organic heirloom tomatoes and basil")

    class MockProviderManager:
        def chat(self, req):
            class Resp:
                text = "[]"
            return Resp()

    mgr = MemoryManager(provider_manager=MockProviderManager(), memory=mem)
    print("get_relevant_facts:", mem.get_relevant_facts("What syntax theme do I like?"))
    print("search_semantic:", mem.search_semantic("What syntax theme do I like?"))
    msgs = mgr.get_context_messages("What syntax theme do I like?")
    print("msgs:", msgs)
