import tempfile
import sys
from pathlib import Path
from src.engineering.test_engine import TestEngine

def test_test_engine_parsing():
    with tempfile.TemporaryDirectory() as temp_repo:
        repo_path = Path(temp_repo)
        engine = TestEngine(repository_path=repo_path)
        
        # 1. Passing test
        passing_file = repo_path / "test_pass.py"
        passing_file.write_text("def test_ok():\n    assert True\n")
        
        res1 = engine.run_tests(str(passing_file))
        assert res1["status"] == "passed"
        assert res1["passed"] == 1
        
        # 2. Failing test
        failing_file = repo_path / "test_fail.py"
        failing_file.write_text("def test_bad():\n    assert False\n")
        
        res2 = engine.run_tests(str(failing_file))
        assert res2["status"] == "failed"
        assert res2["failed"] == 1
        assert "assert False" in res2["results"][0].traceback
        
        # 3. Syntax error (collection error)
        syntax_file = repo_path / "test_syntax.py"
        syntax_file.write_text("def test_syntax()   bad syntax\n")
        
        res3 = engine.run_tests(str(syntax_file))
        assert res3["status"] == "collection_error"
        assert "SyntaxError" in res3["error"] or "SyntaxError" in str(res3.get("results", []))
