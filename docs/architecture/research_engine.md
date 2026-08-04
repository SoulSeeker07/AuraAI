# Research Engine Integration

## Overview

The Research Engine is now integrated with Aura's Brain, enabling live data research before answering questions. This is infrastructure for almost every later milestone.

### Key Capabilities

- **Live Data Research**: Research known issues, recent driver bugs, GitHub issues, Microsoft documentation, Reddit discussions, and vendor advisories
- **Multi-Provider Search**: Supports Tavily, GitHub, Wikipedia, and more (Brave, StackOverflow, Documentation, News coming soon)
- **Smart Query Detection**: Automatically detects when research is needed
- **Evidence-Based Responses**: Research results are incorporated into responses with confidence scores
- **Citation Generation**: Automatic citations for all research sources
- **Conflict Detection**: Detects conflicting information across sources
- **TTL Caching**: Results are cached for 30 minutes to improve performance

## Architecture

```
Aura Core
    └── Research Engine Integration
            ├── ResearchEngine (src/research/)
            │   ├── Search Manager
            │   ├── Content Fetcher
            │   ├── Cache Manager
            │   ├── Citation Builder
            │   └── Providers
            │       ├── TavilyProvider
            │       ├── GitHubProvider
            │       └── WikipediaProvider
            └── ResearchIntegration (src/brain/research_integration.py)
```

## Configuration

Research can be enabled/disabled and configured in `config/settings.json`:

```json
{
  "research": {
    "enabled": true,
    "settings": {
      "cache_enabled": true,
      "max_results": 10,
      "timeout": 30,
      "search_mode": "standard"
    }
  }
}
```

### Search Modes

- **Quick**: Fast, limited results (for latest news, recent updates)
- **Standard**: Balanced approach (default)
- **Deep**: Comprehensive search with high confidence

## Usage

### 1. Check if Research is Needed

```python
from aura_core import AuraCore

core = AuraCore(config)

if core.is_research_needed("What is the latest Python version?"):
    print("Research needed for this query")
```

### 2. Perform Research

```python
from aura_core import AuraCore

core = AuraCore(config)

results = core.perform_research(
    query="What is the latest Python version?",
    mode='standard'
)

if results:
    print(f"Confidence: {results['confidence_score']}/100")
    print(f"Sources: {results['primary_sources']}")
    print(f"Citations: {len(results['citations'])}")
```

### 3. Enhance Response with Research

```python
from aura_core import AuraCore

core = AuraCore(config)

# Enhance a response with research findings
enhancement = core.enhance_response_with_research(
    query="What is the latest Python version?",
    user_message="What is the latest Python version?",
    max_results=5
)

if enhancement['research_used']:
    print("Enhanced message:")
    print(enhancement['enhanced_message'])

    # Access detailed research results
    results = enhancement['research_results']
    print(f"Confidence: {results['confidence_score']}/100")
```

### 4. Get Research Statistics

```python
stats = core.get_research_stats()
print(stats)
```

Output:
```json
{
  "research_engine_initialized": true,
  "cache_stats": {
    "hits": 0,
    "misses": 0,
    "hits_rate": 0.0,
    "size_bytes": 0
  }
}
```

## Integration with Conversation Engine

The Research Engine can be integrated with the Conversation Engine in `src/brain/conversation_engine.py`:

```python
async def process(self, user_message: str):
    # Check if research is needed
    if self.aura_core.is_research_needed(user_message):
        # Perform research
        research = self.aura_core.perform_research(user_message)

        # Enhance response with research
        enhancement = self.aura_core.enhance_response_with_research(
            user_message, user_message
        )

        # Add research to context
        self.context['research_used'] = enhancement['research_used']

        if enhancement['research_used']:
            self.context['research_results'] = enhancement['research_results']

    # Process message with LLM
    response = self.generate_response(user_message)
    return response
```

## Examples

### Example 1: Checking CPU Usage

```python
# User asks: "Why is my CPU at 100%?"

# 1. Research detects that research is needed
if core.is_research_needed("Why is my CPU at 100%?"):
    # 2. Perform research
    results = core.perform_research("Why is my CPU at 100%?", mode='quick')

    # 3. Get enhanced response
    enhancement = core.enhance_response_with_research(
        query="Why is my CPU at 100%?",
        user_message="Why is my CPU at 100%?"
    )

    # 4. LLM uses research results to generate answer
    # The enhanced message includes:
    # - Summary of findings
    # - Key sources
    # - Confidence score
    # - Citations
```

### Example 2: Driver Issues

```python
# User asks: "What's wrong with my NVIDIA driver?"

research = core.perform_research(
    query="NVIDIA driver issues Windows 11",
    mode='deep'
)

# Get research report
report = research_engine.research(
    query="NVIDIA driver issues Windows 11",
    mode=SearchMode.DEEP
)

# Access report details
print(f"Query: {report.query}")
print(f"Confidence: {report.get_confidence_score()}")
print(f"Results: {len(report.results)}")
print(f"Citations: {len(report.citations)}")
print(f"Conflicts: {len(report.conflicts)}")
```

## Provider Capabilities

### TavilyProvider

- **Trust Level**: Official (Score: 5)
- **API Required**: Tavily API Key
- **Best For**: General web search, news, current events
- **Features**: Real-time search, citations, smart filtering

### GitHubProvider

- **Trust Level**: GitHub (Score: 4)
- **API Required**: GitHub API Token
- **Best For**: GitHub issues, repositories, pull requests
- **Features**: Repository search, issue search, detailed repo info

### WikipediaProvider

- **Trust Level**: Wikipedia (Score: 3)
- **API Required**: None
- **Best For**: Encyclopedic knowledge, historical information
- **Features**: Article fetching, category search, disambiguation

## Next Steps

1. ✅ Research data models
2. ✅ Provider interface
3. ✅ Search Manager
4. ✅ Research Engine
5. ✅ Cache Manager
6. ✅ Tavily provider
7. ✅ GitHub provider
8. ✅ Official documentation provider
9. ✅ Citation builder
10. ✅ Brain integration
11. ⏳ Research CLI tests
12. ⏳ Deep research mode integration with Agent Runtime

## Implementation Status

- [x] Research Engine core components
- [x] Aura Core integration
- [x] Research capability detection
- [x] Response enhancement
- [x] Statistics tracking
- [ ] Brave provider
- [ ] StackOverflow provider
- [ ] Documentation provider
- [ ] News provider
- [ ] Deep research mode with Agent Runtime
- [ ] Research capability to Capability Router

## Testing

Run the integration test:

```bash
python tests/test_research_integration.py
```

Run the research engine tests:

```bash
python tests/test_research_engine.py
```

Run the research CLI:

```bash
python research_cli.py
```

## Dependencies

- `requests`: HTTP requests
- `beautifulsoup4`: HTML parsing
- `wikipedia`: Wikipedia API
- `urllib3`: Retry logic

## API Keys Required

- **Tavily API Key**: Set in environment or config
  ```bash
  export TAVILY_API_KEY="your-key-here"
  ```

- **GitHub Token** (optional): Set in environment or config
  ```bash
  export GITHUB_TOKEN="your-token-here"
  ```
