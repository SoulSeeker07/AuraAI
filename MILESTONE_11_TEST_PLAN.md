# MILESTONE 11 - KNOWLEDGE INTELLIGENCE (RAG 2.0) - TEST PLAN

## Overview

This document provides the comprehensive test plan for Milestone 11 - Knowledge Intelligence (RAG 2.0). The system includes:
- Document parsing (10 formats)
- Knowledge indexing and storage
- Multi-strategy retrieval (semantic, keyword, hybrid, graph)
- Knowledge graph management
- Embedding management
- Citation generation
- Background indexing
- File watching

## Test Scenarios

### Test 1: Parser Registry & File Detection

**Objective**: Verify all parsers are registered and can detect their supported file types

**Steps**:
1. Import parser registry: `from src.knowledge.parsers import get_parser_registry`
2. List all registered parsers
3. Test each parser's `supports()` method with valid and invalid file paths

**Expected Results**:
- All 10 parsers should be registered: pdf, markdown, python, docx, pptx, html, json, yaml, csv, log
- Each parser should correctly detect its supported extensions
- Invalid files should return `False`

**Pass Criteria**: ✅ All 10 parsers work correctly

---

### Test 2: Markdown Document Parsing

**Objective**: Verify Markdown files are parsed with heading-based chunking

**Steps**:
1. Create a test Markdown file with multiple headings
2. Parse using the Markdown parser
3. Verify chunk structure and content

**File Structure**:
```markdown
# Main Heading
This is main content.

## Section 1
Content about section 1.

## Section 2
Content about section 2.
```

**Expected Results**:
- 3 chunks should be created (1 main heading + 2 sections)
- Each chunk should have appropriate chunk type (SECTION or PARAGRAPH)
- Content should preserve heading structure

**Pass Criteria**: ✅ Chunk count = 3, types = SECTION/PARAGRAPH

---

### Test 3: Python Code Parsing

**Objective**: Verify Python files are parsed with function-level chunking

**Steps**:
1. Create a Python file with multiple functions and classes
2. Parse using the Python parser
3. Verify function and class chunks are extracted

**File Structure**:
```python
def greet(name):
    """Return a greeting."""
    return f"Hello, {name}!"

def calculate(a, b):
    """Calculate sum."""
    return a + b

class Calculator:
    """A calculator class."""
    def add(self, a, b):
        return a + b
```

**Expected Results**:
- 3 function chunks (greet, calculate)
- 1 class chunk (Calculator)
- Chunk types should be FUNCTION and CLASS
- Docstrings should be included in metadata

**Pass Criteria**: ✅ 3 function chunks, 1 class chunk, correct types

---

### Test 4: JSON/YAML Parsing

**Objective**: Verify structured data files are parsed with key-value chunks

**Steps**:
1. Create a JSON file with nested objects/arrays
2. Create a YAML file with similar structure
3. Parse both files
4. Verify chunk structure

**Expected Results**:
- JSON: Chunks created for each top-level key
- YAML: Same structure as JSON
- Metadata should include key name and value type

**Pass Criteria**: ✅ Both files parse correctly, keys preserved

---

### Test 5: CSV Parsing

**Objective**: Verify CSV files are parsed with row-level chunks

**Steps**:
1. Create a CSV file with headers and multiple rows
2. Parse using CSV parser
3. Verify row chunks

**Expected Results**:
- Each row becomes a chunk
- Chunk type = ROW
- Metadata includes row number, column names, data

**Pass Criteria**: ✅ Row chunks match CSV structure

---

### Test 6: PDF Parsing (Optional - Requires pdfplumber)

**Objective**: Verify PDF text extraction

**Steps**:
1. Create a test PDF (or use existing)
2. Parse using PDF parser
3. Verify page/chapter extraction

**Expected Results**:
- Text extracted from each page
- Page numbers in metadata
- Chunks preserve document structure

**Pass Criteria**: ✅ Text extracted correctly

**Note**: Requires `pip install pdfplumber`

---

### Test 7: Knowledge Manager Initialization

**Objective**: Verify all components initialize correctly

**Steps**:
1. Import KnowledgeManager
2. Initialize with default parameters
3. Check all components are accessible

**Expected Results**:
- KnowledgeManager initializes successfully
- All subcomponents accessible:
  - knowledge_db
  - cache_manager
  - topic_memory
  - knowledge_graph
  - freshness_checker
  - learning_engine

**Pass Criteria**: ✅ All components initialized

---

### Test 8: Vector Store Initialization

**Objective**: Verify vector store creates storage directory

**Steps**:
1. Initialize VectorStore
2. Check storage directory created
3. Verify embeddings and metadata lists

**Expected Results**:
- Storage directory created at `data/knowledge_store`
- Empty embeddings and metadata lists
- Store loaded successfully

**Pass Criteria**: ✅ Directory created, lists initialized

---

### Test 9: Graph Store Initialization

**Objective**: Verify graph store initializes node indices

**Steps**:
1. Initialize GraphStore with VectorStore
2. Check node and edge dictionaries
3. Verify indices created

**Expected Results**:
- Nodes dictionary created
- Edges dictionary created
- Indices for node_type, source, project created

**Pass Criteria**: ✅ All data structures initialized

---

### Test 10: Retrieval Engine Initialization

**Objective**: Verify retrieval engine combines all components

**Steps**:
1. Initialize RetrievalEngine
2. Verify components are accessible
3. Test basic retrieval call

**Expected Results**:
- Vector store accessible
- Graph store accessible
- Chunker accessible

**Pass Criteria**: ✅ All components accessible

---

### Test 11: Citation Engine

**Objective**: Verify citations can be generated from chunks

**Steps**:
1. Create test chunks
2. Generate citations
3. Verify citation structure

**Expected Results**:
- Citations created with chunk metadata
- Score-based relevance tracking
- Proper source attribution

**Pass Criteria**: ✅ Citations generated successfully

---

### Test 12: Indexer Initialization

**Objective**: Verify indexer can be instantiated

**Steps**:
1. Initialize Indexer with all dependencies
2. Check worker thread and queue
3. Test start/stop methods

**Expected Results**:
- Worker thread initialized
- Indexing queue created
- Statistics counters initialized

**Pass Criteria**: ✅ Indexer ready to process files

---

### Test 13: File Watcher Initialization

**Objective**: Verify file watcher can monitor directories

**Steps**:
1. Initialize KnowledgeFileWatcher
2. Check directory watching setup
3. Test event handler creation

**Expected Results**:
- Directory paths stored
- Recursive flag applied
- File event handlers created

**Pass Criteria**: ✅ File watcher ready to monitor

---

### Test 14: Learning Engine

**Objective**: Verify learning engine structure

**Steps**:
1. Initialize LearningEngine
2. Check dependencies
3. Test learned fact structure

**Expected Results**:
- Dependencies (db, graph, freshness, cache) accessible
- LearnedFact dataclass has all fields

**Pass Criteria**: ✅ Learning engine ready for auto-learning

---

### Test 15: Freshness Checker

**Objective**: Verify knowledge lifecycle management

**Steps**:
1. Initialize FreshnessChecker
2. Test category expiry calculation
3. Check category enum

**Expected Results**:
- Categories defined with appropriate lifetimes
- Weather: 0 days (10 min), News: 1 day, Programming: 30 days
- Other categories have defined values

**Pass Criteria**: ✅ All categories configured correctly

---

### Test 16: Multi-Mode Retrieval

**Objective**: Verify different retrieval strategies work

**Steps**:
1. Test each retrieval mode:
   - SEMANTIC
   - KEYWORD
   - HYBRID
   - GRAPH
2. Verify each mode initializes correctly

**Expected Results**:
- Each mode has a handler
- No runtime errors during initialization

**Pass Criteria**: ✅ All retrieval modes available

---

### Test 17: Topic Memory

**Objective**: Verify topic tree structure

**Steps**:
1. Create test topics
2. Add subtopics
3. Verify hierarchical structure

**Expected Results**:
- Topic nodes can be created
- Subtopics can be nested
- Facts can be added to topics

**Pass Criteria**: ✅ Topic hierarchy works correctly

---

### Test 18: Cache Manager

**Objective**: Verify caching system works

**Steps**:
1. Create cache entry
2. Test cache lookup
3. Test cache validity check

**Expected Results**:
- Cache entries can be stored
- Cache can be retrieved by hash
- Cache expiry check works

**Pass Criteria**: ✅ Caching system functional

---

### Test 19: Metadata Extraction

**Objective**: Verify metadata is extracted correctly

**Steps**:
1. Test extraction for Python files
2. Test extraction for Markdown files
3. Verify metadata fields

**Expected Results**:
- Source, file_type, created, modified extracted
- File-type-specific metadata included
- Chunk type assigned

**Pass Criteria**: ✅ Metadata extraction works

---

### Test 20: Complete Integration Test

**Objective**: Test complete pipeline end-to-end

**Steps**:
1. Create test documents (Python, Markdown, JSON)
2. Parse all documents
3. Create embeddings
4. Store in vector database
5. Query and verify results

**Expected Results**:
- Documents parse correctly
- Embeddings generated
- Results retrieved
- Citations generated

**Pass Criteria**: ✅ Full pipeline works

---

## Performance Benchmarks

### Indexing Speed Test

**Objective**: Measure document indexing performance

**Test Procedure**:
1. Index 10 Python files (1000 lines each)
2. Measure time
3. Calculate speed (chunks/second)

**Expected Performance**:
- Should process at least 1000 chunks per second
- Should be CPU-bound with minimal I/O

---

### Retrieval Performance Test

**Objective**: Measure retrieval query performance

**Test Procedure**:
1. Index 1000 documents
2. Run 100 retrieval queries
3. Measure average response time

**Expected Performance**:
- Average response time < 100ms
- Should scale with dataset size

---

### Memory Usage Test

**Objective**: Measure memory consumption

**Test Procedure**:
1. Index 1000 documents
2. Monitor memory usage
3. Check for leaks

**Expected Results**:
- Memory usage proportional to dataset size
- No memory leaks over time

---

## Known Issues & Limitations

### Current Limitations:
1. **PDF Parsing**: Requires `pdfplumber` package (optional)
2. **Embedding Providers**: OpenAI requires API key (local default provided)
3. **File Watching**: Requires Python 3.8+ with watchdog library
4. **Testing**: Cannot test without Python environment setup

### Required Dependencies:
```bash
# Core
pytest>=7.0.0

# PDF (optional)
pip install pdfplumber

# File watching
pip install watchdog

# Optional embeddings
pip install sentence-transformers
pip install openai
```

---

## Test Execution

### Run All Tests:
```bash
cd D:\Sreekanta\VS Code Project\Desktop AI\AuraAI
python -m pytest tests/test_milestone_11_integration.py -v
```

### Run Specific Test Class:
```bash
python -m pytest tests/test_milestone_11_integration.py::TestKnowledgeManagerIntegration -v
```

### Run Specific Test:
```bash
python -m pytest tests/test_milestone_11_integration.py::TestKnowledgeManagerIntegration::test_markdown_parsing -v
```

### Run with Coverage:
```bash
python -m pytest tests/test_milestone_11_integration.py --cov=src/knowledge --cov-report=html
```

---

## Success Criteria

### Component Success:
- ✅ All 10 parsers work
- ✅ All 3 storage engines work
- ✅ All 4 retrieval modes work
- ✅ All management modules work
- ✅ All integration points work

### Integration Success:
- ✅ Documents parse correctly
- ✅ Indexing pipeline works
- ✅ Retrieval returns results
- ✅ Citations are generated
- ✅ Context is built correctly

### Performance Success:
- ✅ Indexing > 1000 chunks/second
- ✅ Retrieval < 100ms average
- ✅ Memory usage is reasonable
- ✅ No memory leaks

---

## Test Results Summary

### Expected Results:
```
Test 1: Parser Registry                    ✅ PASS
Test 2: Markdown Parsing                   ✅ PASS
Test 3: Python Parsing                     ✅ PASS
Test 4: JSON/YAML Parsing                  ✅ PASS
Test 5: CSV Parsing                        ✅ PASS
Test 6: PDF Parsing                        ⏸️  OPTIONAL
Test 7: Knowledge Manager Init             ✅ PASS
Test 8: Vector Store Init                  ✅ PASS
Test 9: Graph Store Init                   ✅ PASS
Test 10: Retrieval Engine Init             ✅ PASS
Test 11: Citation Engine                   ✅ PASS
Test 12: Indexer Init                      ✅ PASS
Test 13: File Watcher Init                 ✅ PASS
Test 14: Learning Engine                   ✅ PASS
Test 15: Freshness Checker                 ✅ PASS
Test 16: Multi-Mode Retrieval              ✅ PASS
Test 17: Topic Memory                      ✅ PASS
Test 18: Cache Manager                     ✅ PASS
Test 19: Metadata Extraction               ✅ PASS
Test 20: Complete Integration              ✅ PASS

BENCHMARKS:
- Indexing Speed:       > 1000 chunks/sec
- Retrieval Latency:    < 100ms avg
- Memory Usage:         Proportional to data
```

---

## Next Steps

1. ✅ **Code Complete** - All components implemented
2. ⏳ **Run Tests** - Execute test suite (requires Python)
3. ⏳ **Fix Issues** - Address any failures
4. ⏳ **Performance Test** - Verify benchmarks
5. ⏳ **Documentation** - Add user guides
6. ⏳ **Mark Complete** - All tests pass

---

## Questions or Issues?

- Run `pytest --collect-only` to see all test cases
- Use `pytest -x` to stop on first failure
- Use `pytest -v` for verbose output
- Use `pytest --tb=short` for short traceback

---

**Last Updated**: 2026-07-30
**Status**: ✅ Code Complete, ⏳ Testing Pending
