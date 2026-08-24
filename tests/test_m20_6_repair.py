import tempfile
import sys
from pathlib import Path
from engineering.test_engine import TestEngine
from engineering.code_editor import CodeEditor
from engineering.bug_repair import BugRepairLoop

class MockBridge:
    def execute_capability(self, capability, arguments):
        self.capability = capability
        self.arguments = arguments
        
class MockWM:
    def query_sync(self, entity, domain):
        if "function:bad_func" in entity:
            return "symbol context"
        return None

def test_repair_loop_exhaustion(monkeypatch):
    import engineering.bug_repair
    from brain.world_model import WorldModel
    
    # Mock WorldModel
    monkeypatch.setattr(WorldModel, "get_instance", lambda: MockWM())
    
    # Mock Antigravity Bridge module
    bridge_mock = MockBridge()
    class MockBridgeModule:
        AntigravityCodingBridge = lambda: bridge_mock
    monkeypatch.setitem(sys.modules, "engineering.antigravity_bridge", MockBridgeModule)
    
    with tempfile.TemporaryDirectory() as temp_repo:
        repo_path = Path(temp_repo)
        engine = TestEngine(repository_path=repo_path)
        editor = CodeEditor(
            repository_path=repo_path,
            ast_manager=None,
            symbol_graph=None,
            dependency_graph=None
        )
        
        loop = BugRepairLoop(
            repository_path=repo_path,
            test_engine=engine,
            ast_manager=None,
            code_editor=editor
        )
        
        # 1. Failing test
        target_file = repo_path / "bad.py"
        target_file.write_text("def bad_func():\n    assert False\n")
        
        test_file = repo_path / "test_bad.py"
        test_file.write_text("from bad import bad_func\ndef test_bad():\n    bad_func()\n")
        
        res = loop.repair_bug(
            test_file=str(test_file),
            test_name=None,
            max_attempts=2,
            target_file="bad.py"
        )
        
        assert res.success is False
        assert res.final_status == "failed"
        assert res.total_attempts == 2
        
        # Verify bridge was called
        assert bridge_mock.capability == "code.debug"
        assert "Symbol Context from World Model:\nsymbol context" in bridge_mock.arguments["description"]
        
        # Verify rollback occurred (bad.py should still exist exactly as before)
        assert (repo_path / "bad.py").read_text() == "def bad_func():\n    assert False\n"
        
        editor.close()
