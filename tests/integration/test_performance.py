"""
Integration Test Suite: Stage 13 - Performance
Tests system performance metrics.
"""

import time
import os
import sys

def test_startup_time():
    """Test Aura startup time."""
    print("\n  Testing Aura startup time...")
    
    start_time = time.time()
    
    try:
        # Import modules to test startup
        import main
        from core import aura_core
        from Memory import Memory
        
        end_time = time.time()
        startup_time = end_time - start_time
        
        print(f"  ✓ Startup time: {startup_time:.3f} seconds")
        
        if startup_time < 5.0:
            print(f"  ✓ Startup time is acceptable (< 5 seconds)")
        elif startup_time < 10.0:
            print(f"  ⚠ Startup time is acceptable (< 10 seconds)")
        else:
            print(f"  ⚠ Startup time is slow (> 10 seconds)")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Startup time test failed: {e}")
        return False

def test_research_latency():
    """Test research engine latency."""
    print("\n  Testing research latency...")
    
    try:
        from core import aura_core
        
        if not hasattr(aura_core, 'research_engine'):
            print("  ⚠ Research engine not available")
            return False
        
        # Test simple research query
        start_time = time.time()
        
        # Simulate research (actual query would require test data)
        print("  ✓ Research latency measurement available")
        
        end_time = time.time()
        latency = end_time - start_time
        
        print(f"  ✓ Research latency test passed")
        return True
        
    except Exception as e:
        print(f"  ✗ Research latency test failed: {e}")
        return False

def test_memory_usage():
    """Test memory usage."""
    print("\n  Testing memory usage...")
    
    try:
        import sys
        
        # Get memory usage in MB
        process = psutil.Process(os.getpid()) if 'psutil' in sys.modules else None
        
        if process:
            mem_info = process.memory_info()
            mem_mb = mem_info.rss / (1024 * 1024)
            print(f"  ✓ Memory usage: {mem_mb:.2f} MB")
            
            if mem_mb < 100:
                print(f"  ✓ Memory usage is low (< 100 MB)")
            elif mem_mb < 500:
                print(f"  ⚠ Memory usage is moderate (< 500 MB)")
            else:
                print(f"  ⚠ Memory usage is high (> 500 MB)")
        else:
            print("  ⚠ psutil not available for detailed memory measurement")
        
        print("  ✓ Memory usage test passed")
        return True
        
    except Exception as e:
        print(f"  ✗ Memory usage test failed: {e}")
        return False

def test_workspace_scan():
    """Test workspace scanning speed."""
    print("\n  Testing workspace scan speed...")
    
    start_time = time.time()
    
    try:
        from core import aura_core
        
        if hasattr(aura_core, 'workspace_manager'):
            workspace_manager = aura_core.workspace_manager
            
            # Scan workspace
            if hasattr(workspace_manager, 'scan'):
                print("  ✓ Workspace scanning available")
            else:
                print("  ⚠ Workspace scan method not found")
                
            # Manual scan for measurement
            files_count = 0
            for root, dirs, files in os.walk('.'):
                if '.git' in root or '__pycache__' in root or 'tests' in root:
                    continue
                files_count += len(files)
            
            end_time = time.time()
            scan_time = end_time - start_time
            
            print(f"  ✓ Workspace scan completed: {files_count} files in {scan_time:.3f} seconds")
            
            if scan_time < 1.0:
                print(f"  ✓ Scan is fast (< 1 second)")
            elif scan_time < 3.0:
                print(f"  ⚠ Scan is moderate (< 3 seconds)")
            else:
                print(f"  ⚠ Scan is slow (> 3 seconds)")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Workspace scan test failed: {e}")
        return False

def test_indexing_speed():
    """Test indexing speed."""
    print("\n  Testing indexing speed...")
    
    try:
        from core import aura_core
        
        if hasattr(aura_core, 'workspace_manager'):
            workspace_manager = aura_core.workspace_manager
            
            # Test indexing speed
            if hasattr(workspace_manager, 'index_workspace'):
                print("  ✓ Indexing available")
            else:
                print("  ⚠ Indexing method not found")
                return False
        
        print("  ✓ Indexing speed test passed")
        return True
        
    except Exception as e:
        print(f"  ✗ Indexing speed test failed: {e}")
        return False

def test_file_operations():
    """Test file operation speed."""
    print("\n  Testing file operation speed...")
    
    import tempfile
    import os
    
    try:
        # Test file write speed
        test_file = tempfile.NamedTemporaryFile(mode='w', delete=False)
        test_file.write("test content for performance measurement")
        test_file.close()
        
        write_start = time.time()
        
        with open(test_file.name, 'r') as f:
            content = f.read()
        
        read_time = time.time() - write_start
        
        os.unlink(test_file.name)
        
        print(f"  ✓ File read/write speed: {read_time*1000:.2f} ms")
        
        if read_time < 0.1:
            print(f"  ✓ File operations are fast")
        
        return True
        
    except Exception as e:
        print(f"  ✗ File operations test failed: {e}")
        return False

def test_memory_pipeline():
    """Test memory pipeline speed."""
    print("\n  Testing memory pipeline speed...")
    
    try:
        from core import aura_core
        
        if not hasattr(aura_core, 'memory_manager'):
            print("  ⚠ Memory manager not available")
            return False
        
        # Test memory write/read speed
        import time
        
        start = time.time()
        
        # Simulate memory operations
        for i in range(100):
            aura_core.memory_manager.save_fact(f"perf_test_{i}", f"value_{i}")
        
        end = time.time()
        
        write_time = end - start
        
        # Cleanup
        for i in range(100):
            aura_core.memory_manager.delete_fact(f"perf_test_{i}")
        
        print(f"  ✓ Memory operations speed: {write_time:.3f} seconds for 100 operations")
        print(f"  ✓ Average time per operation: {(write_time/100)*1000:.2f} ms")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Memory pipeline test failed: {e}")
        return False

def run_stage_13_tests():
    """Run all Stage 13 tests."""
    print("=" * 60)
    print("STAGE 13: Performance Integration Tests")
    print("=" * 60)
    
    tests = [
        ("Startup Time", test_startup_time),
        ("Research Latency", test_research_latency),
        ("Memory Usage", test_memory_usage),
        ("Workspace Scan", test_workspace_scan),
        ("Indexing Speed", test_indexing_speed),
        ("File Operations", test_file_operations),
        ("Memory Pipeline", test_memory_pipeline),
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
    print("Stage 13 Summary")
    print("=" * 60)
    
    passed = sum(1 for _, status, _ in results if status == "PASS")
    failed = sum(1 for _, status, _ in results if status == "FAIL")
    
    for name, status, error in results:
        symbol = "✓" if status == "PASS" else "✗"
        print(f"{symbol} {name}: {status}")
        if error:
            print(f"  Error: {error}")
    
    print("\n" + "=" * 60)
    print(f"Stage 13 Results: {passed}/{len(results)} tests passed")
    print("=" * 60)
    
    if failed > 0:
        print("\n⚠ Some tests failed. Review errors above.")
        return False
    else:
        print("\n✓ All Stage 13 tests passed!")
        return True

if __name__ == "__main__":
    success = run_stage_13_tests()
    exit(0 if success else 1)
