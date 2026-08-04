# Aura Integration Test Suite

Comprehensive integration testing suite for AuraAI covering all 14 milestones.

## Overview

This test suite provides a safety net to ensure Aura remains stable as new features are added. Before implementing Milestone 15 Phase 2 and beyond, all previous milestones must pass their integration tests.

## Test Stages

1. **Core Startup** - Verify Aura boots cleanly with no errors
2. **Memory System** - Test memory write/read cycles and user facts
3. **Knowledge/RAG** - Test local knowledge retrieval
4. **Research Engine** - Test static, current, and deep research modes
5. **Planner** - Test step-by-step planning capabilities
6. **Agent Runtime** - Test task execution and error recovery
7. **Workflow Engine** - Test workflow automation and state transitions
8. **Plugins** - Test all plugin systems
9. **Workspace** - Test workspace awareness and file management
10. **Coding Agent** - Test coding assistance features
11. **Vision** - Test vision capabilities
12. **Desktop** - Test desktop automation
13. **Performance** - Test system performance metrics
14. **Regression** - Ensure all previous tests still pass

## Running Tests

### Run All Tests

```bash
cd tests
python run_all.py
```

This will execute all 14 test stages and generate a comprehensive report.

### Run Individual Test Stages

```bash
cd tests/integration
python test_startup.py
python test_memory.py
python test_research.py
# ... etc
```

### Run from Root Directory

```bash
python tests/run_all.py
```

## Test Output

The master test runner generates a detailed report including:

- Overall pass/fail summary
- Duration for each stage
- Detailed results per stage
- Failed tests and error messages
- Recommendations for fixes

### Example Output

```
======================================================================
 Aura Integration Test Suite
======================================================================

======================================================================
  Stage 1: Core Startup Integration Tests
======================================================================

  Testing core module imports...
    ✓ main
    ✓ aura_core
    ✓ Memory

...

======================================================================
 INTEGRATION TEST SUMMARY
======================================================================

Overall Aura Integration Test Results
Total Tests: 112
Passed: 98
Failed: 14
Total Duration: 12.34 seconds

✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓
ALL 112 TESTS PASSED!
✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓

======================================================================
Detailed Results
======================================================================

  ✓ Core Startup: PASS (2.34s)
  ✓ Memory System: PASS (1.56s)
  ✓ Knowledge/RAG: PASS (0.89s)
  ...
```

## Test Requirements

All test files require:

- AuraAI core modules loaded
- Proper workspace structure
- No circular imports
- All managers initialized

## Continuous Integration

To integrate this into CI/CD:

```yaml
# Example GitHub Actions workflow
name: Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: python tests/run_all.py
```

## Troubleshooting

### All Tests Failed

1. Check error messages for specific failures
2. Run individual test files to debug
3. Check for circular imports
4. Verify all dependencies are installed

### Import Errors

- Ensure AuraAI is properly installed
- Check PYTHONPATH includes the workspace root
- Verify all required modules exist

### Memory Write Issues

- Check Memory.py permissions
- Verify data directory is writable
- Check for file locking issues

## Test Coverage

Each test file includes multiple test cases covering:

- **Positive cases**: Ensure features work correctly
- **Negative cases**: Ensure errors are handled properly
- **Edge cases**: Test boundary conditions
- **Integration cases**: Test component interactions

## Contributing

When adding new features:

1. Add corresponding integration tests
2. Ensure all existing tests still pass
3. Update this README with new test information
4. Document any new test requirements

## Best Practices

- Run tests frequently during development
- Never commit if tests fail
- Use test failures as regression detection
- Update tests when API changes

## Test Metrics

Target metrics:

- **Startup Time**: < 5 seconds
- **Research Latency**: < 3 seconds for simple queries
- **Memory Usage**: < 100 MB idle
- **Workspace Scan**: < 3 seconds
- **All Tests**: 100% pass rate

## Contact

For questions or issues with the test suite, refer to:
- [AuraAI Documentation](../docs/)
- [Issues](https://github.com/your-org/AuraAI/issues)

## License

Part of AuraAI project. See [LICENSE](../LICENSE) file.
