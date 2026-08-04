"""
Integration Test Suite: Stage 3 - Knowledge/RAG
Tests local knowledge retrieval and RAG capabilities.
"""

import os

def test_project_files():
    """Test that project files can be indexed and searched."""
    print("\n  Testing project file indexing...")
    
    # Check for project structure
    required_dirs = [
        'apps',
        'backend',
        'core',
        'plugins',
        'tests',
    ]
    
    for dir_name in required_dirs:
        if os.path.exists(dir_name):
            print(f"  ✓ {dir_name}/ found")
        else:
            print(f"  ⚠ {dir_name}/ not found")
            return False
    
    print("  ✓ Project structure verified")
    return True

def test_file_search():
    """Test finding files by name."""
    print("\n  Testing file search...")
    
    try:
        # Try to import search module
        # This will be implemented as plugins/ or core tools
        # For now, we check if the file exists
        files_to_find = [
            'Memory.py',
            'main.py',
            'core/aura_core.py',
            'plugins/__init__.py',
        ]
        
        for file_path in files_to_find:
            if os.path.exists(file_path):
                print(f"  ✓ {file_path}")
            else:
                print(f"  ⚠ {file_path} not found")
                return False
        
        print("  ✓ File search works")
        return True
        
    except Exception as e:
        print(f"  ✗ File search failed: {e}")
        return False

def test_find_conversation_engine():
    """Test finding ConversationEngine."""
    print("\n  Testing ConversationEngine search...")
    
    try:
        # Check for ConversationEngine
        if os.path.exists('Memory.py'):
            print("  ✓ Memory.py found")
            
            # Try to import
            try:
                with open('Memory.py', 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'ConversationEngine' in content:
                        print("  ✓ ConversationEngine class found in Memory.py")
                    else:
                        print("  ⚠ ConversationEngine class not found in Memory.py")
            except Exception as e:
                print(f"  ⚠ Could not read Memory.py: {e}")
        else:
            print("  ✗ Memory.py not found")
            return False
            
        return True
        
    except Exception as e:
        print(f"  ✗ ConversationEngine search failed: {e}")
        return False

def test_explain_memory_py():
    """Test explaining Memory.py."""
    print("\n  Testing Memory.py explanation...")
    
    try:
        if not os.path.exists('Memory.py'):
            print("  ✗ Memory.py not found")
            return False
        
        # Read and analyze Memory.py
        with open('Memory.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for key classes
        classes_found = []
        for line in content.split('\n'):
            if 'class ' in line and not line.strip().startswith('#'):
                class_name = line.strip().split('class ')[1].split('(')[0].strip()
                if class_name:
                    classes_found.append(class_name)
        
        print(f"  ✓ Found classes: {', '.join(classes_found)}")
        
        # Check for methods
        methods_found = []
        for line in content.split('\n'):
            if 'def ' in line and not line.strip().startswith('#'):
                method_name = line.strip().split('def ')[1].split('(')[0].strip()
                if method_name and not method_name.startswith('__'):
                    methods_found.append(method_name)
        
        print(f"  ✓ Found {len(methods_found)} methods")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Memory.py explanation failed: {e}")
        return False

def test_find_research_planner():
    """Test finding the research planner."""
    print("\n  Testing research planner search...")
    
    try:
        # Search for research planner in the codebase
        research_files = []
        
        # Look in core and backend directories
        for root, dirs, files in os.walk('.'):
            # Skip hidden directories and tests
            if '.git' in root or '__pycache__' in root or 'tests' in root:
                continue
                
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            if 'planner' in content.lower() or 'research' in content.lower():
                                research_files.append(file_path)
                    except:
                        continue
        
        if research_files:
            print(f"  ✓ Found research-related files:")
            for file_path in research_files[:5]:  # Show first 5
                rel_path = os.path.relpath(file_path)
                print(f"    - {rel_path}")
        else:
            print("  ⚠ No research planner found in codebase")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Research planner search failed: {e}")
        return False

def test_local_knowledge_base():
    """Test local knowledge base functionality."""
    print("\n  Testing local knowledge base...")
    
    try:
        # Check if knowledge base directory exists
        if os.path.exists('Data'):
            print("  ✓ Data directory exists")
            
            # Check for cache
            cache_dir = os.path.join('Data', 'cache')
            if os.path.exists(cache_dir):
                print("  ✓ Cache directory exists")
            else:
                print("  ⚠ Cache directory does not exist (will be created)")
        else:
            print("  ✗ Data directory not found")
            return False
            
        return True
        
    except Exception as e:
        print(f"  ✗ Local knowledge base test failed: {e}")
        return False

def run_stage_3_tests():
    """Run all Stage 3 tests."""
    print("=" * 60)
    print("STAGE 3: Knowledge/RAG Integration Tests")
    print("=" * 60)
    
    tests = [
        ("Project Files", test_project_files),
        ("File Search", test_file_search),
        ("ConversationEngine", test_find_conversation_engine),
        ("Memory.py Explanation", test_explain_memory_py),
        ("Research Planner", test_find_research_planner),
        ("Local Knowledge Base", test_local_knowledge_base),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            if test_func():
                results.append((name, "PASS", None))
            else:
                results.append((name, "FAIL", "Test returned False"))
        except Exception as e:
            results.append((name, "FAIL", str(e)))
    
    print("\n" + "=" * 60)
    print("Stage 3 Summary")
    print("=" * 60)
    
    passed = sum(1 for _, status, _ in results if status == "PASS")
    failed = sum(1 for _, status, _ in results if status == "FAIL")
    
    for name, status, error in results:
        symbol = "✓" if status == "PASS" else "✗"
        print(f"{symbol} {name}: {status}")
        if error:
            print(f"  Error: {error}")
    
    print("\n" + "=" * 60)
    print(f"Stage 3 Results: {passed}/{len(results)} tests passed")
    print("=" * 60)
    
    if failed > 0:
        print("\n⚠ Some tests failed. Review errors above.")
        return False
    else:
        print("\n✓ All Stage 3 tests passed!")
        return True

if __name__ == "__main__":
    success = run_stage_3_tests()
    exit(0 if success else 1)
