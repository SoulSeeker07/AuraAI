import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from core.backends.adapters.antigravity_backend import CodingBackendAdapter
import subprocess

def test_code_execute_timeout_handling():
    adapter = CodingBackendAdapter()
    repo_path = Path('/fake/workspace')
    args = {'script': 'gui_app.py'}
    
    with patch('pathlib.Path.exists', return_value=True):
        with patch('subprocess.run') as mock_run:
            # Simulate a TimeoutExpired
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=['python', 'gui_app.py'],
                timeout=10,
                output=b'GUI starting...'
            )
            
            result = adapter._execute_run('run gui app', args, repo_path)
            
            # Should gracefully catch the timeout and return success
            assert result.success is True
            assert 'Process timed out after 10 seconds' in result.observations[0]
            assert 'GUI starting...' in result.observations[1]

def test_code_execute_stdout_capture():
    adapter = CodingBackendAdapter()
    repo_path = Path('/fake/workspace')
    args = {'script': 'cli_tool.py'}
    
    with patch('pathlib.Path.exists', return_value=True):
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = 'Test Output'
            mock_result.stderr = ''
            mock_run.return_value = mock_result
            
            result = adapter._execute_run('run cli app', args, repo_path)
            
            assert result.success is True
            assert 'STDOUT:\nTest Output' in result.observations[1]
