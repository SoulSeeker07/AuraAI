import pytest
from pathlib import Path
from core.backends.adapters.workspace_policy import WorkspacePolicy, WorkspacePolicyError

def test_workspace_policy_root_generic_file_rejection():
    policy = WorkspacePolicy(Path('/fake/workspace'))
    
    # Should reject generic files in root
    with pytest.raises(WorkspacePolicyError, match='Please place it in a project subdirectory'):
        policy.authorize_write('app.py')
        
    with pytest.raises(WorkspacePolicyError, match='Please place it in a project subdirectory'):
        policy.authorize_write('main.py')
        
    with pytest.raises(WorkspacePolicyError, match='Please place it in a project subdirectory'):
        policy.authorize_write('index.js')
        
    # Should allow generic files in subdirectories
    # Note: we catch the existing file check if we mock it, but here it won't exist so it will just return the path
    result = policy.authorize_write('my_app/app.py')
    assert result == Path('/fake/workspace/my_app/app.py').resolve()
    
    result = policy.authorize_write('my_app/main.py')
    assert result == Path('/fake/workspace/my_app/main.py').resolve()
    
    # Should allow non-generic files in root
    result = policy.authorize_write('my_custom_script.py')
    assert result == Path('/fake/workspace/my_custom_script.py').resolve()
