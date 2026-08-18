"""
Research Execution Metrics

Centralized tracking of research operation performance and quality metrics.
Used for diagnostics, monitoring, and user-facing dashboards.

Milestone 14: Research Foundation
"""

import time
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ResearchExecutionMetrics:
    """
    Centralized metrics for research operations.

    Attributes:
        planning_ms: Time spent planning research steps
        search_ms: Time spent executing searches
        extraction_ms: Time spent extracting evidence
        reasoning_ms: Time spent reasoning over evidence
        llm_ms: Time spent in LLM calls
        total_ms: Total execution time
        iterations: Number of research iterations performed
        confidence_history: List of confidence values across iterations
        providers_used: List of providers used for searches
        evidence_count: Total number of evidence items
        strong_count: Number of strong evidence items
        weak_count: Number of weak evidence items
        conflicts: Number of conflicts detected
        missing_information: List of missing information items
        started_at: Timestamp when research began
        finished_at: Timestamp when research completed
        query: Original research query
    """

    planning_ms: float = 0.0
    search_ms: float = 0.0
    extraction_ms: float = 0.0
    reasoning_ms: float = 0.0
    llm_ms: float = 0.0
    total_ms: float = 0.0
    iterations: int = 0
    confidence_history: list[float] = field(default_factory=list)
    providers_used: list[str] = field(default_factory=list)
    evidence_count: int = 0
    strong_count: int = 0
    weak_count: int = 0
    conflicts: int = 0
    missing_information: list[str] = field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    query: str = ""

    def to_dict(self) -> dict:
        """Convert metrics to dictionary."""
        return {
            "planning_ms": self.planning_ms,
            "search_ms": self.search_ms,
            "extraction_ms": self.extraction_ms,
            "reasoning_ms": self.reasoning_ms,
            "llm_ms": self.llm_ms,
            "total_ms": self.total_ms,
            "iterations": self.iterations,
            "confidence_history": self.confidence_history,
            "providers_used": self.providers_used,
            "evidence_count": self.evidence_count,
            "strong_count": self.strong_count,
            "weak_count": self.weak_count,
            "conflicts": self.conflicts,
            "missing_information": self.missing_information,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "query": self.query,
        }

    def print_summary(self):
        """Print a formatted summary of metrics."""
        print("\n" + "=" * 70)
        print("RESEARCH EXECUTION METRICS")
        print("=" * 70)
        print(f"Query: {self.query}")
        print(f"Started: {self.started_at}")
        print(f"Finished: {self.finished_at}")
        print(f"Total Time: {self.total_ms:.1f}ms ({self.total_ms/1000:.2f}s)")
        print(f"Iterations: {self.iterations}")
        print("\nTiming Breakdown:")
        # Avoid division by zero when total_ms is 0
        total = self.total_ms if self.total_ms > 0 else 1.0
        print(
            f"  Planning:    {self.planning_ms:.1f}ms ({(self.planning_ms/total*100):.1f}%)"
        )
        print(
            f"  Search:      {self.search_ms:.1f}ms ({(self.search_ms/total*100):.1f}%)"
        )
        print(
            f"  Extraction:  {self.extraction_ms:.1f}ms ({(self.extraction_ms/total*100):.1f}%)"
        )
        print(
            f"  Reasoning:   {self.reasoning_ms:.1f}ms ({(self.reasoning_ms/total*100):.1f}%)"
        )
        print(f"  LLM:         {self.llm_ms:.1f}ms ({(self.llm_ms/total*100):.1f}%)")
        print("\nEvidence:")
        print(f"  Total:       {self.evidence_count}")
        print(f"  Strong:      {self.strong_count}")
        print(f"  Weak:        {self.weak_count}")
        print(f"  Conflicts:   {self.conflicts}")
        print(f"  Missing:     {len(self.missing_information)}")
        if self.confidence_history:
            print("\nConfidence Progression:")
            for i, conf in enumerate(self.confidence_history, 1):
                print(f"  Iteration {i}: {conf:.2f}")
        if self.providers_used:
            print(f"\nProviders Used: {', '.join(self.providers_used)}")
        print("=" * 70)


class MetricsCollector:
    """
    Helper class to collect metrics during research operations.
    """

    def __init__(self, query: str):
        self.metrics = ResearchExecutionMetrics(query=query, started_at=datetime.now())
        self._timers = {}

    def start_timer(self, name: str):
        """Start a named timer."""
        self._timers[name] = time.perf_counter()

    def stop_timer(self, name: str):
        """Stop a named timer and record duration."""
        if name in self._timers:
            duration_ms = (time.perf_counter() - self._timers[name]) * 1000
            self.metrics.__setattr__(f"{name}_ms", duration_ms)
            del self._timers[name]

    def record_confidence(self, confidence: float):
        """Record a confidence value."""
        self.metrics.confidence_history.append(confidence)

    def record_iteration(self):
        """Record that an iteration was performed."""
        self.metrics.iterations += 1

    def add_provider(self, provider: str):
        """Record a provider used."""
        if provider not in self.metrics.providers_used:
            self.metrics.providers_used.append(provider)

    def finalize(self):
        """Finalize metrics collection."""
        self.metrics.finished_at = datetime.now()
        self.metrics.total_ms = (
            self.metrics.planning_ms
            + self.metrics.search_ms
            + self.metrics.extraction_ms
            + self.metrics.reasoning_ms
            + self.metrics.llm_ms
        )

    @property
    def total_ms(self) -> float:
        """Total elapsed milliseconds from metrics."""
        return self.metrics.total_ms

    def print_summary(self):
        """Print a formatted summary of metrics."""
        self.metrics.print_summary()
