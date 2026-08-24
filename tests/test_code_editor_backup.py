import tempfile
from pathlib import Path

from engineering.code_editor import CodeEditor

def test_code_editor_backup_roundtrip():
    with tempfile.TemporaryDirectory() as temp_repo:
        repo_path = Path(temp_repo)
        
        # Initialize editor with mock dependencies
        editor = CodeEditor(
            repository_path=repo_path,
            ast_manager=None,
            symbol_graph=None,
            dependency_graph=None
        )
        
        # 1. Write a file
        test_file = repo_path / "test_file.py"
        original_content = "print('hello world')\n"
        test_file.write_text(original_content, encoding="utf-8")
        
        # 2. create_backup()
        backup_id = editor.create_backup("test_file.py")
        assert backup_id != ""
        assert (repo_path / ".aura_backup" / backup_id).exists()
        
        # 3. Mutate the file
        mutated_content = "print('goodbye world')\n"
        test_file.write_text(mutated_content, encoding="utf-8")
        assert test_file.read_text(encoding="utf-8") == mutated_content
        
        # 4. restore_backup()
        result = editor.restore_backup(backup_id)
        assert result.success is True
        
        # 5. Assert byte-for-byte restoration
        restored_content = test_file.read_text(encoding="utf-8")
        assert restored_content == original_content
        
        # Clean up
        editor.close()
