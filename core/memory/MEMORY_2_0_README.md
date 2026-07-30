# Memory 2.0 Implementation

## Overview

Memory 2.0 transforms Aura from "remembering data" to "understanding what is worth remembering" through intelligent memory management with 5 layers, importance scoring, and smart retrieval.

## Key Features

### 1. Five Memory Layers

- **Working Layer**: Ephemeral, for current tasks (cleared on restart)
- **Session Layer**: Temporary, cleared at end of session
- **Long-Term Layer**: Persists across restarts (primary storage)
- **Knowledge Layer**: Broad knowledge and general facts
- **Workspace Layer**: Project/workspace-specific memories

### 2. Intelligent Memory Analyzer

The `MemoryAnalyzer` class analyzes incoming text to determine:

- **Should Store?**: Filters out noise like "Hello!"
- **Importance Level**: LOW → MEDIUM → HIGH → CRITICAL → VITAL
- **Category**: 10 categories (Preferences, Projects, People, Skills, Goals, Tasks, Files, Devices, Networking, Coding, Personal)
- **Key Extraction**: Creates normalized keys for storage
- **Sensitive Detection**: Identifies API keys, secrets, passwords

### 3. Smart Retrieval

- Keyword-based relevance scoring
- Importance-based ranking
- Access frequency tracking (frequently used memories rank higher)
- Configurable layer/category filters

### 4. Forgetting Engine

Automatically removes:
- Memories older than X days
- Low-importance memories
- Helps maintain memory freshness

### 5. Conflict Resolution

When updating existing memories:
- Automatically resolves conflicts
- Promotes importance level on updates
- Tracks original vs new values
- Maintains access statistics

### 6. Sensitive Data Handling

- Detects sensitive patterns (API keys, secrets, passwords)
- Encrypts sensitive memories automatically
- Secure deletion when forgetting
- Simple XOR encryption (use cryptography library in production)

## Architecture

```
MemoryManagerV2
├── MemoryAnalyzer (analyzes incoming text)
├── MemoryStore (per layer)
│   ├── Working Layer (ephemeral)
│   ├── Session Layer (temporary)
│   ├── Long-Term Layer (persistent)
│   ├── Knowledge Layer (broad)
│   └── Workspace Layer (project-specific)
└── Dependencies
    ├── MemoryTypes (enums, dataclasses)
    └── JSON persistence layer
```

## Usage Examples

### Basic Storage

```python
from core.memory import MemoryManagerV2, MemoryLayer, CategoryType

# Initialize
memory = MemoryManagerV2(data_path=Path("Data/memory_2.0.json"))

# Store a preference
await memory.analyze_and_remember(
    text="My favorite IDE is VS Code.",
    layer=MemoryLayer.LONG_TERM
)

# Store sensitive data (automatically encrypted)
await memory.analyze_and_remember(
    text="Remember my API key: sk-test123",
    layer=MemoryLayer.LONG_TERM
)
```

### Manual Storage

```python
# Store with specific parameters
await memory.remember(
    key="my favorite color",
    value="blue",
    category=CategoryType.PREFERENCES,
    layer=MemoryLayer.LONG_TERM,
    importance=ImportanceLevel.HIGH
)
```

### Retrieval

```python
# Get all preferences
preferences = memory.retrieve(category=CategoryType.PREFERENCES, limit=10)

# Get specific fact
my_ide = memory.retrieve(key="my favorite ide", layer=MemoryLayer.LONG_TERM)

# Smart retrieval with query
result = await memory.retrieve_with_reranking(
    query="what are my preferences",
    limit=5
)

print(f"Relevance: {result.score:.2f}")
print(f"Context:\n{result.context}")
```

### Forgetting

```python
# Forget specific memory
result = memory.forget("my api key", layer=MemoryLayer.LONG_TERM)
print(f"Deleted: {result.deleted}")

# Forget old memories
result = await memory.forget_old_memories(days=30, importance_threshold=ImportanceLevel.LOW)
print(f"Forgot {result.deleted} old memories")
```

### Conflict Resolution

```python
# Update existing memory (resolves conflict automatically)
result = memory.resolve_conflict(
    key="my favorite ide",
    new_value="Cursor",
    layer=MemoryLayer.LONG_TERM
)

print(f"Resolution: {result.resolution}")
print(f"Merged: {result.merged_fact.value}")
```

### Summary

```python
# Get memory statistics
summary = memory.get_summary()

print(f"Total Facts: {summary.total_facts}")
print(f"By Category: {summary.by_category}")
print(f"By Importance: {summary.by_importance}")
print(f"Recent Activity: {[f.key for f in summary.recent_activity]}")
```

## Test Coverage

All user requirements tested in `tests/test_memory_2_0.py`:

1. ✅ **Store Preference**: "My favorite IDE is VS Code." → Preference category
2. ✅ **Update Memory**: "Actually, I use Cursor now." → Updates existing
3. ✅ **Filter Noise**: "Hello!" → Not stored
4. ✅ **Encrypt Sensitive**: "Remember my API key." → Encrypted storage
5. ✅ **Forget Memory**: "Forget my API key." → Secure removal
6. ✅ **Retrieve**: "What's my favorite IDE?" → Returns updated value
7. ✅ **Smart Retrieval**: "Summarize what you know" → Combines relevant memories

## Category Definitions

| Category | Description | Examples |
|----------|-------------|----------|
| Preferences | User preferences and choices | Favorite color, IDE, food |
| Projects | Project-related information | Deadlines, milestones, teams |
| People | People information | Names, contacts, relationships |
| Skills | Skills and learning | Languages learned, certifications |
| Goals | Goals and objectives | Targets, achievements |
| Tasks | Task-related information | To-dos, assignments |
| Files | File information | Locations, names, types |
| Devices | Device information | Computers, phones, specs |
| Networking | Network settings | Servers, APIs, services |
| Coding | Code-related information | Functions, bugs, fixes |
| Personal | General personal info | Birthdays, addresses, etc. |

## Importance Levels

| Level | Value | Description |
|-------|-------|-------------|
| LOW | 1 | Temporary information |
| MEDIUM | 2 | General facts (default) |
| HIGH | 3 | Important updates |
| CRITICAL | 4 | Very important |
| VITAL | 5 | Essential information |

## Running Tests

```bash
pytest tests/test_memory_2_0.py -v
```

Or run the test file directly:

```bash
python tests/test_memory_2_0.py
```

## Integration with AuraBrain

Memory 2.0 is ready to integrate with AuraBrain's `process()` method:

```python
from core.memory import MemoryManagerV2, MemoryLayer

class AuraBrain:
    def __init__(self, ...):
        # Initialize memory manager
        self.memory_manager = MemoryManagerV2(...)

    async def process(self, request, context):
        # Analyze and store user input
        await self.memory_manager.analyze_and_remember(
            text=request.text,
            layer=MemoryLayer.SESSION
        )

        # Retrieve relevant memories
        result = await self.memory_manager.retrieve_with_reranking(
            query=request.text,
            limit=10
        )

        # Use retrieved memories in response
        context["retrieved_memories"] = result.memories
        # ... rest of processing
```

## Future Enhancements

1. **LLM-based Classification**: Use AI to better categorize memories
2. **Advanced Encryption**: Use cryptography library for proper AES-256
3. **Vector Search**: Implement semantic search for smarter retrieval
4. **Memory Timeline**: Visualize memory history and changes
5. **Memory Analytics**: Detailed insights into memory usage patterns
6. **Cross-layer Sync**: Automatically sync relevant memories across layers

## Implementation Status

✅ **Completed**:
- Core type definitions
- Memory analyzer
- Memory manager v2 orchestrator
- 5 memory layers
- Importance scoring
- Category classification
- Smart retrieval
- Forgetting engine
- Conflict resolution
- Sensitive data encryption
- JSON persistence
- Comprehensive test coverage

📊 **Test Coverage**: 15+ test classes covering all requirements

🚀 **Ready for Integration**: Memory 2.0 is complete and ready to be integrated with AuraBrain
