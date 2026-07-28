# Aura AI v2 Web Search System

## Overview

Aura AI v2 introduces a sophisticated web search system with AI-powered intent detection, intelligent source routing, deep research capabilities, and smart caching. This is a significant upgrade from the previous simple keyword-based search.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     User Query                               │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   Intent Analyzer    │
              │   (AI-powered)       │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Knowledge Router    │
              │  (Source selection)  │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   Live Search Engine │
              │  (Tavily API)        │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │    Source Ranker     │
              │  (Authority score)   │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │      Search Cache    │
              │   (TTL-based)        │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Citation Builder    │
              │   (Source citations) │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   Research Agent     │
              │   (Multi-step plan)  │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Page Reader         │
              │   (Content extraction)│
              └──────────────────────┘
```

## Core Components

### 1. Intent Analyzer

AI-powered intent detection that classifies user queries.

**Capabilities:**
- Detects query type (live info, programming, networking, medical, etc.)
- Calculates confidence scores
- Identifies specialized sources to prioritize
- Distinguishes between simple and deep research needs

**Example:**
```python
query = "Who won yesterday's IPL match?"
intent_analysis = intent_analyzer.analyze(query)
# Returns: {
#   intent: "LIVE_INFORMATION",
#   confidence: 0.98,
#   category: "live",
#   needs_web_search: true,
#   specialized_sources: ["cricbuzz.com", "ipl.com"]
# }
```

### 2. Knowledge Router

Routes queries to the most appropriate information sources.

**Routing Logic:**
- **LIVE_INFORMATION** → News sources (Google News, BBC, Reuters)
- **PROGRAMMING** → Technical sources (GitHub, StackOverflow, Python.org)
- **NETWORKING** → Cisco, Microsoft, Juniper documentation
- **MEDICAL** → WHO, Mayo Clinic, CDC
- **KNOWLEDGE_REQUEST** → Wikipedia, MDN, Microsoft Learn
- **RESEARCH** → Multiple academic sources

### 3. Live Search Engine

Uses Tavily API for high-quality, AI-optimized search results.

**Features:**
- API-based search (more reliable than web scraping)
- Search depth options (basic/advanced)
- Domain filtering
- Real-time results

**Configuration:**
```python
# Environment variable
export TAVILY_API_KEY="your-api-key"

# Or pass to constructor
search_engine = LiveSearchEngine(api_key="your-api-key")
```

### 4. Search Cache

Smart caching system with different TTLs for different query types.

**Cache Durations:**
- Weather: 10 minutes
- News: 30 minutes
- Stock/Crypto: 5 minutes
- Documentation: 24 hours
- Programming: 7 days

**Benefits:**
- Reduces API calls
- Faster response times
- Cost savings

### 5. Source Ranker

Ranks search results based on authority and relevance.

**Authority Weights:**
- .gov domains: 10.0
- Major tech sites (GitHub, StackOverflow): 8.0-8.5
- Wikipedia: 6.0
- Random blogs: 3.0

**Relevance Scoring:**
- Keyword matching in URL and title
- Exact phrase matching
- Semantic similarity

### 6. Citation Builder

Formats source citations for answers.

**Output:**
```markdown
### Sources

**1. Python 3.15 Release Notes**
Source: [docs.python.org](https://docs.python.org/release/3.15.0/)
Reasoning: high_authority, government_source

**2. Python 3.15 New Features**
Source: [blog.python.org](https://blog.python.org/2024/python-3-15)
Reasoning: high_authority, technical_source
```

### 7. Research Agent

Plans and executes multi-step research for complex queries.

**Example:**
```python
query = "Compare CCNA vs CCNP vs JNCIA"
plan = research_agent.create_plan(query)
# Step 1: Search Cisco CCNA
# Step 2: Search Cisco CCNP
# Step 3: Search Juniper JNCIA
# Step 4: Compare certifications
# Step 5: Generate table
```

### 8. Page Reader

Reads and extracts meaningful content from webpages.

**Filters out:**
- Ads and sponsored content
- Navigation menus
- Cookie banners
- Scripts and stylesheets
- Empty elements

**Preserves:**
- Main article text
- Headings
- Code blocks
- Tables

## Installation

### Prerequisites

1. **Tavily API Key**
   - Sign up at [tavily.com](https://tavily.com)
   - Get your API key from the dashboard
   - Set as environment variable:
     ```bash
     export TAVILY_API_KEY="your-api-key"
     ```

2. **Required Packages**
   ```bash
   pip install tavily-python beautifulsoup4
   ```

### Installation Steps

1. The new modules are already created in `src/brain/`:
   - `intent_analyzer.py`
   - `knowledge_router.py`
   - `live_search_engine.py`
   - `search_cache.py`
   - `page_reader.py`
   - `source_ranker.py`
   - `citation_builder.py`
   - `research_agent.py`
   - `models_extended.py`
   - `aura_search_system.py`

2. Update `requirements.txt`:
   ```
   tavily-python>=0.5.0
   beautifulsoup4>=4.12.0
   ```

3. Install the package:
   ```bash
   pip install -r requirements.txt
   ```

## Usage Examples

### Basic Web Search

```python
from ai.provider_manager import ProviderManager
from brain.aura_search_system import AuraSearchSystem

# Initialize search system
search_system = AuraSearchSystem(
    provider_manager=ProviderManager(),
    tavily_api_key="your-api-key",
)

# Perform search
query = "What is Python 3.15 new features?"
results = search_system.search(query)

for result in results:
    print(f"{result.title}: {result.url}")
```

### Intent Analysis

```python
# Analyze user intent
query = "Compare React and Vue"
intent = search_system.analyze_intent(query)

print(f"Intent: {intent.intent}")
print(f"Confidence: {intent.confidence}")
print(f"Needs Web Search: {intent.needs_web_search}")
print(f"Specialized Sources: {intent.specialized_sources}")
```

### Smart Search with Intent

```python
# Get intent analysis first
intent = search_system.analyze_intent(query)

# Perform search with routing
results = search_system.search(
    query=query,
    intent_analysis=intent,
    use_cache=True,
)

# Get ranked results
ranked = search_system.rank_results(
    results=[r.__dict__ for r in results],
    query=query,
)
```

### Deep Research

```python
# Check if complex query
if search_system.research_agent.is_complex_query(query):
    # Create research plan
    plan = search_system.create_research_plan(query)

    # Execute plan
    results = search_system.execute_research(query)
    print(f"Research completed in {plan.estimated_duration}")
else:
    # Simple search
    results = search_system.search(query)
```

### Page Reading

```python
# Read a webpage
content = search_system.read_page("https://docs.python.org/3.15/")

print(f"Title: {content.title}")
print(f"Main text: {content.main_text[:500]}")
print(f"Headings: {content.headings[:5]}")
print(f"Code blocks: {len(content.code_blocks)}")
```

### Source Citations

```python
# Get search results
results = search_system.search(query)

# Build citations
citations = search_system.get_citations(results, max_citations=5)

for citation in citations:
    print(f"{citation.rank}. {citation.title}")
    print(f"   {citation.url}")
```

### Cache Management

```python
# Get cache statistics
stats = search_system.get_cache_stats()
print(f"Cache hit rate: {stats['hit_rate']:.1f}%")
print(f"Hits: {stats['hits']}, Misses: {stats['misses']}")

# Clear cache
search_system.clear_cache()
```

## Integration with ConversationEngine

### Update ConversationEngine to Use Intent Analyzer

```python
from brain.aura_search_system import AuraSearchSystem

class ConversationEngine:
    def __init__(self, ...):
        # ... existing initialization ...
        self.aura_search = AuraSearchSystem(
            provider_manager=self.provider_manager,
            tavily_api_key=self.settings.get("tavily_api_key"),
        )

    def process(self, user_input: str, ...) -> ConversationResult:
        # ... existing code ...

        # Use intent analyzer
        intent_analysis = self.aura_search.analyze_intent(user_input)

        # Perform smart search if needed
        if intent_analysis.needs_web_search:
            search_results = self.aura_search.search(
                query=user_input,
                intent_analysis=intent_analysis,
                use_cache=True,
            )

            # Convert to WebSearchResult objects
            web_results = [
                {
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet,
                }
                for r in search_results
            ]
        else:
            web_results = []

        # ... rest of existing code ...
```

## Testing

Run the test suite:

```bash
python tests/test_aura_search.py
```

**Test Coverage:**
- Intent analysis with various query types
- Web search with Tavily API
- Search caching
- Source ranking
- Citation generation
- Research agent for complex queries
- Page reading

## Performance Optimizations

### 1. Caching Strategy

```python
# Use cache for frequent queries
results = search_system.search(
    query="weather in Tokyo",
    intent_analysis=intent,
    use_cache=True,  # Cache enabled
)

# Disable cache for sensitive/real-time queries
results = search_system.search(
    query="latest stock prices",
    intent_analysis=intent,
    use_cache=False,  # Cache disabled
)
```

### 2. Search Depth Selection

```python
# For general queries (faster)
results = search_system.search(
    query="what is Python?",
    search_depth="basic",
)

# For deep research (more comprehensive)
results = search_system.search(
    query="Compare React and Vue frameworks",
    search_depth="advanced",
)
```

### 3. Limit Results

```python
# Get top 3 results for quick answers
results = search_system.search(query=query, max_results=3)

# Get more results for comprehensive research
results = search_system.search(query=query, max_results=10)
```

## Troubleshooting

### Tavily API Key Issues

**Error:** `ValueError: Tavily API key is required`

**Solution:**
```bash
# Set environment variable
export TAVILY_API_KEY="your-key-here"

# Or update settings
settings = {"tavily_api_key": "your-key-here"}
```

### Rate Limit Errors

**Error:** `ValueError: Tavily API rate limit exceeded`

**Solution:**
- Implement exponential backoff
- Increase cache duration for frequently searched queries
- Use search depth "basic" instead of "advanced" for bulk searches

### Page Reading Failures

**Error:** `ValueError: Failed to read page: HTTP error 404`

**Solution:**
- Verify URL is correct
- Check if site blocks bots
- Increase timeout:
  ```python
  page_reader = PageReader(timeout_seconds=30.0)
  ```

## Future Enhancements

- [ ] Multi-language search
- [ ] Custom authority weights per user
- [ ] Source verification
- [ ] Fact-checking capabilities
- [ ] Real-time data integration
- [ ] User preference-based ranking
- [ ] Search history analytics
- [ ] Progressive web app interface

## Contributing

1. Add new intent categories to `intent_analyzer.py`
2. Update routing rules in `knowledge_router.py`
3. Add authority weights to `source_ranker.py`
4. Update test cases in `tests/test_aura_search.py`
5. Document new features in this file

## License

See [LICENSE](LICENSE) file for details.
