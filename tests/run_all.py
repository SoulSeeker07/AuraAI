#!/usr/bin/env python3
"""
Master Test Runner for Aura Integration Tests
Runs all 14 stages of integration tests and generates a summary report.
"""

import sys
import os
import time
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import test modules
from tests.integration import (
    test_startup,
    test_memory,
    test_knowledge,
    test_research,
    test_planner,
    test_runtime,
    test_workflow,
    test_plugins,
    test_workspace,
    test_coding,
    test_vision,
    test_desktop,
    test_performance,
    test_regression,
)

def print_header(title):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)

def print_section(title):
    """Print a formatted section header."""
    print("\n" + "-" * 70)
    print(f" {title}")
    print("-" * 70)

def print_success(message):
    """Print a success message."""
    print(f"  ✓ {message}")

def print_warning(message):
    """Print a warning message."""
    print(f"  ⚠ {message}")

def print_error(message):
    """Print an error message."""
    print(f"  ✗ {message}")

def get_stage_number_from_name(stage_name):
    """Map stage name to stage number (1-14)."""
    stage_mapping = {
        "Core Startup": 1,
        "Memory System": 2,
        "Knowledge/RAG": 3,
        "Research Engine": 4,
        "Planner": 5,
        "Agent Runtime": 6,
        "Workflow Engine": 7,
        "Plugins": 8,
        "Workspace": 9,
        "Coding Agent": 10,
        "Vision": 11,
        "Desktop": 12,
        "Performance": 13,
        "Regression": 14,
    }
    return stage_mapping.get(stage_name, 1)

def run_test_stage(stage_module, stage_name):
    """Run a test stage and return results."""
    print_section(f"Stage {stage_name}")
    
    start_time = time.time()
    
    try:
        # Get the stage number and call the appropriate test function
        stage_num = get_stage_number_from_name(stage_name)
        test_function = getattr(stage_module, f"run_stage_{stage_num}_tests")
        
        # Execute the test module
        success = test_function()
        
        end_time = time.time()
        duration = end_time - start_time
        
        if success:
            print_success(f"{stage_name} completed in {duration:.2f} seconds")
            return (stage_name, "PASS", duration, 0)
        else:
            print_error(f"{stage_name} failed")
            return (stage_name, "FAIL", duration, 0)
            
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        print_error(f"{stage_name} crashed: {e}")
        return (stage_name, "CRASH", duration, 0)

def generate_summary_report(all_results, total_duration):
    """Generate a summary report of all test results."""
    print_header("INTEGRATION TEST SUMMARY")
    
    # Calculate totals
    total_tests = sum(status_count for _, status, _, status_count in all_results)
    passed = sum(1 for _, status, _, _ in all_results if status == "PASS")
    failed = sum(1 for _, status, _, _ in all_results if status == "FAIL")
    crashed = sum(1 for _, status, _, _ in all_results if status == "CRASH")
    
    # Group by status
    stage_names = [stage for stage, status, _, _ in all_results]
    stage_statuses = [status for _, status, _, _ in all_results]
    stage_durations = [duration for _, _, duration, _ in all_results]
    stage_failures = [status_count for _, _, _, status_count in all_results]
    
    # Print overall status
    print(f"\nOverall Aura Integration Test Results")
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Crashed: {crashed}")
    print(f"Total Duration: {total_duration:.2f} seconds")
    
    if failed == 0 and crashed == 0:
        print(f"\n{'✓' * 40}")
        print(f"ALL {total_tests} TESTS PASSED!")
        print(f"{'✓' * 40}")
    elif failed > 0:
        print(f"\n{'⚠' * 40}")
        print(f"FAILED: {failed}/{len(all_results)} stages")
        print(f"{'⚠' * 40}")
    else:
        print(f"\n{'⚠' * 40}")
        print(f"CRASHED: {crashed}/{len(all_results)} stages")
        print(f"{'⚠' * 40}")
    
    # Print detailed results
    print_section("Detailed Results")
    
    # Define stage names for display
    stage_display_names = {
        "Core Startup": "Core Startup",
        "Memory System": "Memory System",
        "Knowledge/RAG": "Knowledge/RAG",
        "Research Engine": "Research Engine",
        "Planner": "Planner",
        "Agent Runtime": "Agent Runtime",
        "Workflow Engine": "Workflow Engine",
        "Plugins": "Plugins",
        "Workspace": "Workspace",
        "Coding Agent": "Coding Agent",
        "Vision": "Vision",
        "Desktop": "Desktop",
        "Performance": "Performance",
        "Regression": "Regression",
    }
    
    # Find which stage name corresponds to each stage
    for i, (stage, status, duration, failures) in enumerate(all_results):
        if i < len(stage_names):
            display_name = stage_display_names.get(stage, stage)
            symbol = "✓" if status == "PASS" else "✗"
            print(f"{symbol} {display_name}: {status} ({duration:.2f}s)")
            if failures > 0:
                print(f"  Failed sub-tests: {failures}")
    
    # Print failures
    if failed > 0 or crashed > 0:
        print_section("Failed/Crashed Stages")
        
        for stage, status, _, _ in all_results:
            if status != "PASS":
                display_name = stage_display_names.get(stage, stage)
                print(f"  {display_name}: {status}")
    
    # Print recommendations
    print_section("Recommendations")
    
    if failed > 0:
        print("  • Review and fix failed tests")
        print("  • Check error messages for root causes")
        print("  • Run individual test stages to debug")
    
    if crashed > 0:
        print("  • Fix import errors or dependencies")
        print("  • Check for circular imports")
        print("  • Verify all required modules are present")
    
    if passed > 0:
        print("  • All tests passed! Ready for new features.")
    
    if failed == 0 and crashed == 0:
        print("\n  ✓ You can proceed with Milestone 15 Phase 2")
        print("  ✓ Integration tests serve as regression gate")
    
    print("\n" + "=" * 70)

def run_all_integration_tests():
    """Run all integration tests and generate report."""
    print_header("Aura Integration Test Suite")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Environment: {sys.platform}")
    print(f"Python Version: {sys.version.split()[0]}")
    
    # Define test stages
    test_stages = [
        ("Core Startup", test_startup),
        ("Memory System", test_memory),
        ("Knowledge/RAG", test_knowledge),
        ("Research Engine", test_research),
        ("Planner", test_planner),
        ("Agent Runtime", test_runtime),
        ("Workflow Engine", test_workflow),
        ("Plugins", test_plugins),
        ("Workspace", test_workspace),
        ("Coding Agent", test_coding),
        ("Vision", test_vision),
        ("Desktop", test_desktop),
        ("Performance", test_performance),
        ("Regression", test_regression),
    ]
    
    # Run all tests
    all_results = []
    start_time = time.time()
    
    for stage_name, stage_module in test_stages:
        result = run_test_stage(stage_module, stage_name)
        all_results.append(result)
    
    total_duration = time.time() - start_time
    
    # Generate report
    generate_summary_report(all_results, total_duration)
    
    # Return exit code
    failed = sum(1 for _, status, _, _ in all_results if status != "PASS")
    crashed = sum(1 for _, status, _, _ in all_results if status == "CRASH")
    
    if failed > 0 or crashed > 0:
        return 1
    else:
        return 0

def main():
    """Main entry point."""
    try:
        exit_code = run_all_integration_tests()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nTest suite interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
