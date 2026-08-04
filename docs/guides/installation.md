# Migration Guide: Integrating Aura AI v2 Web Search

This guide shows how to integrate the new Aura AI v2 web search system with your existing ConversationEngine.

## Step 1: Update Dependencies

Update your `requirements.txt`:

```txt
tavily-python>=0.5.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
```

Install the new dependencies:

```bash
pip install -r requirements.txt
```

## Step 2: Update ConversationEngine

### Option A: Simple Integration (Recommended)

Update `src/brain/conversation_engine.py`:

```python
from brain.aura_search_system import AuraSearchSystem

class ConversationEngine:
    def __init__(
        self,
        memory: Memory,
        provider_manager: ProviderManager,
        settings: dict[str, Any] | None = None,
        username: str = "User",
        assistant_name: str = "Aura",
        model: str | None = None,
        tavily_api_key: str | None = None,  # NEW
    ):
        self.memory = memory
        self.provider_manager = provider_manager
        self.settings = settings or {}
        self.model = model

        # Initialize Aura Search System
        self.aura_search = AuraSearchSystem(
            provider_manager=provider_manager,
            tavily_api_key=tavily_api_key or self.settings.get("tavily_api_key"),
        )

        # Existing components
        self.intent_router = IntentRouter(memory)
        self.context_builder = ContextBuilder(memory, self.settings, username, assistant_name)

    def process(
        self,
        user_input: str,
        attachments: list[ConversationAttachment] | None = None,
    ) -> ConversationResult:
        user_input = user_input.strip()
        if not user_input:
            return ConversationResult("Ask me something and I will help.", Intent("provider_chat"))

        # NEW: Use intent analyzer
        intent_analysis = self.aura_search.analyze_intent(user_input)

        # OLD: Intent router (keep for backward compatibility)
        intent = self.intent_router.detect(user_input, attachments)

        # NEW: Use Aura Search for web search
        web_results = self._lookup_web_aura(user_input, intent_analysis)

        # Context builder uses existing code
        context = self.context_builder.build(user_input, intent, attachments, web_results)

        # ... rest of existing code ...
```

### Option B: Enhanced Integration with Advanced Features

For a more advanced integration with research and page reading:

```python
class ConversationEngine:
    def __init__(self, ...):
        # ... existing initialization ...

        # Initialize Aura Search System
        self.aura_search = AuraSearchSystem(
            provider_manager=provider_manager,
            tavily_api_key=tavily_api_key or self.settings.get("tavily_api_key"),
        )

    def process(self, user_input: str, ...) -> ConversationResult:
        # Analyze intent
        intent_analysis = self.aura_search.analyze_intent(user_input)

        # Check if it's a complex research query
        if self.aura_search.research_agent.is_complex_query(user_input):
            return self._process_research_query(user_input, attachments, intent_analysis)

        # Regular processing
        web_results = self._lookup_web_aura(user_input, intent_analysis)
        context = self.context_builder.build(user_input, intent, attachments, web_results)

        # ... rest of existing code ...

    def _lookup_web_aura(
        self,
        user_input: str,
        intent_analysis
    ) -> list[dict[str, str]]:
        """Use Aura Search for intelligent web lookup."""
        if not intent_analysis.needs_web_search:
            return []

        if self.settings.get("web_search_enabled", True) is False:
            return []

        try:
            # Use Aura Search
            results = self.aura_search.search(
                query=user_input,
                intent_analysis=intent_analysis,
                use_cache=True,
            )

            # Convert to format expected by existing code
            return [
                {
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet,
                }
                for r in results
            ]

        except Exception as e:
            # Fallback to old search if needed
            print(f"Web search failed: {e}, using fallback")
            return self._lookup_web_legacy(user_input)

    def _lookup_web_legacy(self, user_input: str) -> list[dict[str, str]]:
        """Legacy web search method for backward compatibility."""
        if self.web_search:
            try:
                return self.web_search.search(user_input, limit=5)
            except Exception:
                pass

        return []

    def _process_research_query(
        self,
        user_input: str,
        attachments,
        intent_analysis
    ) -> ConversationResult:
        """Process complex research queries with multi-step research."""
        # Create research plan
        plan = self.aura_search.create_research_plan(user_input)

        # Execute research
        research_results = self.aura_search.execute_research(
            query=user_input,
            use_cache=True,
        )

        # Build context with research results
        web_results = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("snippet", ""),
            }
            for r in research_results.get("all_results", [])
        ]

        context = self.context_builder.build(user_input, intent, attachments, web_results)

        # Process normally
        if local_answer := self._answer_local_intent(intent):
            self._save_turn(context, local_answer)
            return ConversationResult(local_answer, intent)

        return self._process_provider_chat(context)
```

## Step 3: Update Settings

Update your `settings.json` or configuration:

```json
{
  "web_search_enabled": true,
  "tavily_api_key": "your-api-key-here",
  "search_cache_enabled": true,
  "cache_dir": "Data/search_cache",
  "max_search_results": 10
}
```

## Step 4: Add Configuration to Desktop App

If you're using the desktop app, add these settings to your configuration:

```python
# desktop/app.py or controller.py
settings = {
    "web_search_enabled": True,
    "tavily_api_key": os.environ.get("TAVILY_API_KEY"),
    "search_cache_enabled": True,
    "cache_dir": "Data/search_cache",
}

# Initialize with settings
engine = ConversationEngine(
    memory=memory,
    provider_manager=provider_manager,
    settings=settings,
    username=username,
    assistant_name="Aura",
)
```

## Step 5: Add Environment Variables

For desktop applications, set the environment variable:

```python
import os
os.environ["TAVILY_API_KEY"] = "your-api-key"
```

Or in your desktop app's configuration file or startup script.

## Step 6: Test the Integration

Create a simple test:

```python
# tests/test_integration.py
from ai.provider_manager import ProviderManager
from Memory import Memory
from src.brain.conversation_engine import ConversationEngine

# Initialize components
memory = Memory()
provider_manager = ProviderManager()
settings = {"tavily_api_key": "your-api-key"}

# Initialize engine
engine = ConversationEngine(
    memory=memory,
    provider_manager=provider_manager,
    settings=settings,
)

# Test
query = "What is Python 3.15?"
result = engine.process(query)

print(f"Response: {result.text}")
print(f"Intent: {result.intent.name}")
```

Run the test:

```bash
python tests/test_integration.py
```

## Step 7: Verify Cache Stats

After running a few searches, check the cache:

```python
cache_stats = engine.aura_search.get_cache_stats()
print(f"Cache hit rate: {cache_stats['hit_rate']:.1f}%")
print(f"Hits: {cache_stats['hits']}")
print(f"Misses: {cache_stats['misses']}")
```

## Step 8: Monitor Performance

Track the performance of the new system:

```python
import time

query = "What is Python 3.15?"

# First search (cache miss)
start = time.time()
result1 = engine.process(query)
duration1 = time.time() - start

# Second search (cache hit)
start = time.time()
result2 = engine.process(query)
duration2 = time.time() - start

print(f"First search: {duration1:.3f}s")
print(f"Second search: {duration2:.3f}s")
print(f"Speedup: {duration1/duration2:.1f}x")
```

## Step 9: Handle Errors Gracefully

The new system will fallback gracefully if Tavily is not configured:

```python
try:
    engine = ConversationEngine(
        memory=memory,
        provider_manager=provider_manager,
        settings=settings,
    )
except ValueError as e:
    if "Tavily API key" in str(e):
        print("Please configure TAVILY_API_KEY environment variable")
    else:
        raise
```

## Step 10: Update Documentation

Update your README to mention the new features:

```markdown
## Web Search Features

Aura now uses intelligent web search with:
- AI-powered intent detection
- Multiple search sources based on query type
- Smart caching for faster responses
- Source ranking and citations
- Deep research for complex queries
- Page content extraction
```

## Rollback Plan

If you need to rollback to the old system:

```python
class ConversationEngine:
    def __init__(self, ...):
        # Keep old WebSearchClient
        self.web_search = WebSearchClient()

        # Keep old intent router
        self.intent_router = IntentRouter(memory)

        # Only initialize Aura Search if configured
        if settings.get("tavily_api_key"):
            self.aura_search = AuraSearchSystem(
                provider_manager=provider_manager,
                tavily_api_key=settings.get("tavily_api_key"),
            )
        else:
            self.aura_search = None

    def _lookup_web(self, user_input: str, intent: Intent) -> list[dict[str, str]]:
        """Choose between Aura Search and legacy search."""
        if self.aura_search and self.aura_search.search.__self__.api_key:
            # Use Aura Search
            return self._lookup_web_aura(user_input)
        else:
            # Use legacy search
            return self.web_search.search(user_input, limit=5)
```

## Performance Expectations

- **Intent Analysis:** ~1-2 seconds
- **Web Search (first time):** ~3-5 seconds
- **Web Search (cached):** ~0.5-1 second
- **Page Reading:** ~2-4 seconds per page

## Next Steps

1. Test with various query types
2. Monitor cache hit rate
3. Adjust cache TTLs if needed
4. Tune authority weights if ranking needs improvement
5. Add custom sources for your use case

## Support

For issues or questions:
- Check the [Aura AI v2 Web Search documentation](aura_ai_v2_web_search.md)
- Review the [test file](../tests/test_aura_search.py) for examples
- Check cache statistics and logs for debugging
