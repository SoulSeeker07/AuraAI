"""
Observability Layer - Logging, metrics, and debugging.

The Observability Layer provides:
- Structured logging
- Performance metrics
- Error tracking
- Debug information
- Task execution monitoring
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .task_model import Task, TaskStatus


class MetricType(Enum):
    """Types of metrics."""

    TASK_DURATION = "task_duration"
    TASK_SUCCESS_RATE = "task_success_rate"
    AGENT_EXECUTION_TIME = "agent_execution_time"
    CACHE_HIT_RATE = "cache_hit_rate"
    SEARCH_LATENCY = "search_latency"
    MEMORY_USAGE = "memory_usage"
    ERROR_COUNT = "error_count"
    CUSTOM = "custom"


@dataclass
class Metric:
    """Represents a performance metric."""

    metric_type: MetricType
    value: float
    labels: dict[str, str]
    timestamp: datetime = field(default_factory=datetime.now)
    unit: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert metric to dictionary."""
        return {
            "metric_type": self.metric_type.value,
            "value": self.value,
            "labels": self.labels,
            "timestamp": self.timestamp.isoformat(),
            "unit": self.unit,
        }


@dataclass
class TaskExecutionEvent:
    """Represents a task execution event."""

    task_id: str
    task_type: str
    status: TaskStatus
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None
    duration_ms: float = 0.0
    agent_used: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class MetricCollector:
    """
    Collects and manages performance metrics.

    Features:
    - Metric recording
    - Metric aggregation
    - Metric reporting
    - Metric storage
    """

    def __init__(self):
        """Initialize the metric collector."""
        self._metrics: list[Metric] = []
        self._counters: dict[str, int] = {}
        self._timers: dict[str, list[float]] = {}
        self._histograms: dict[str, list[float]] = {}
        self._gauges: dict[str, float] = {}
        self._labels: dict[str, dict[str, str]] = {}

    def record_metric(
        self,
        metric_type: MetricType,
        value: float,
        labels: dict[str, str] | None = None,
        unit: str = "",
    ):
        """
        Record a metric.

        Args:
            metric_type: Type of metric
            value: Metric value
            labels: Metric labels
            unit: Unit of measurement
        """
        labels = labels or {}
        self._metrics.append(
            Metric(metric_type=metric_type, value=value, labels=labels, unit=unit)
        )

    def increment_counter(
        self, name: str, amount: int = 1, labels: dict[str, str] | None = None
    ):
        """
        Increment a counter.

        Args:
            name: Counter name
            amount: Amount to increment
            labels: Counter labels
        """
        key = self._make_key(name, labels)
        self._counters[key] = self._counters.get(key, 0) + amount

        self.record_metric(
            MetricType.CUSTOM,
            value=amount,
            labels={**labels, "metric": name, "type": "counter"},
            unit="count",
        )

    def start_timer(self, name: str, labels: dict[str, str] | None = None) -> str:
        """
        Start a timer for measurement.

        Args:
            name: Timer name
            labels: Timer labels

        Returns:
            Timer ID
        """
        key = self._make_key(name, labels)
        timer_id = f"{key}_{int(time.time() * 1000)}"
        self._timers[timer_id] = time.time()
        return timer_id

    def stop_timer(self, timer_id: str, labels: dict[str, str] | None = None):
        """
        Stop a timer.

        Args:
            timer_id: Timer ID to stop
            labels: Timer labels (for aggregation)
        """
        if timer_id not in self._timers:
            return

        elapsed = time.time() - self._timers[timer_id]
        del self._timers[timer_id]

        key = self._make_key("execution_time", labels)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(elapsed * 1000)  # Convert to milliseconds

    def record_gauge(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ):
        """
        Record a gauge value.

        Args:
            name: Gauge name
            value: Gauge value
            labels: Gauge labels
        """
        key = self._make_key(name, labels)
        self._gauges[key] = value

    def record_task_duration(
        self, task_type: str, duration_ms: float, labels: dict[str, str] | None = None
    ):
        """Record task duration."""
        labels = labels or {}
        self.record_metric(
            MetricType.TASK_DURATION,
            value=duration_ms,
            labels={**labels, "task_type": task_type},
            unit="ms",
        )

    def record_task_success(self, task_type: str, labels: dict[str, str] | None = None):
        """Record task success."""
        labels = labels or {}
        self.increment_counter(
            "task_success", 1, labels={**labels, "task_type": task_type}
        )

    def record_task_failure(self, task_type: str, labels: dict[str, str] | None = None):
        """Record task failure."""
        labels = labels or {}
        self.increment_counter(
            "task_failure", 1, labels={**labels, "task_type": task_type}
        )

    def get_metrics(self) -> list[Metric]:
        """Get all recorded metrics."""
        return self._metrics.copy()

    def get_counters(self) -> dict[str, int]:
        """Get all counters."""
        return self._counters.copy()

    def get_histogram(
        self, name: str, labels: dict[str, str] | None = None
    ) -> list[float]:
        """Get histogram for a metric."""
        key = self._make_key(name, labels)
        return self._histograms.get(key, []).copy()

    def get_avg(self, name: str, labels: dict[str, str] | None = None) -> float:
        """Get average value for a metric."""
        histogram = self.get_histogram(name, labels)
        if not histogram:
            return 0.0
        return sum(histogram) / len(histogram)

    def get_median(self, name: str, labels: dict[str, str] | None = None) -> float:
        """Get median value for a metric."""
        histogram = self.get_histogram(name, labels)
        if not histogram:
            return 0.0
        sorted_h = sorted(histogram)
        n = len(sorted_h)
        mid = n // 2
        if n % 2 == 0:
            return (sorted_h[mid - 1] + sorted_h[mid]) / 2
        return sorted_h[mid]

    def reset(self):
        """Reset all metrics."""
        self._metrics.clear()
        self._counters.clear()
        self._timers.clear()
        self._histograms.clear()
        self._gauges.clear()


class TaskMonitor:
    """
    Monitors task execution and logs events.

    Features:
    - Task execution tracking
    - Performance measurement
    - Error tracking
    - Debug information
    """

    def __init__(self, logger: logging.Logger | None = None):
        """
        Initialize the task monitor.

        Args:
            logger: Optional logger instance
        """
        self._logger = logger or logging.getLogger(__name__)
        self._execution_events: list[TaskExecutionEvent] = []
        self._task_start_times: dict[str, float] = {}

    def start_task(self, task: Task, agent: str | None = None):
        """
        Start tracking a task.

        Args:
            task: Task to track
            agent: Agent executing the task
        """
        event = TaskExecutionEvent(
            task_id=task.id,
            task_type=task.type.value,
            status=TaskStatus.PENDING,
            agent_used=agent,
        )

        self._execution_events.append(event)
        self._task_start_times[task.id] = time.time()

        self._logger.info(f"Task started: {task.id} ({task.type.value})")

    def complete_task(
        self,
        task_id: str,
        success: bool,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Mark a task as complete.

        Args:
            task_id: Task ID to complete
            success: Whether task succeeded
            error: Optional error message
            metadata: Optional metadata
        """
        if task_id not in self._task_start_times:
            return

        duration = (time.time() - self._task_start_times[task_id]) * 1000
        del self._task_start_times[task_id]

        # Find the event
        for event in reversed(self._execution_events):
            if event.task_id == task_id:
                event.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
                event.end_time = datetime.now()
                event.duration_ms = duration
                event.error = error
                event.metadata = metadata or {}
                break

        status_str = "COMPLETED" if success else "FAILED"
        self._logger.info(
            f"Task completed: {task_id} ({status_str}), duration: {duration:.2f}ms"
        )

    def record_task_status_change(self, task_id: str, status: TaskStatus):
        """Record status change for a task."""
        for event in self._execution_events:
            if event.task_id == task_id:
                event.status = status
                self._logger.info(f"Task status change: {task_id} -> {status.value}")
                break

    def get_events(self, task_id: str | None = None) -> list[TaskExecutionEvent]:
        """Get execution events."""
        if task_id:
            return [e for e in self._execution_events if e.task_id == task_id]
        return self._execution_events.copy()

    def get_summary(self) -> dict[str, Any]:
        """Get execution summary."""
        total = len(self._execution_events)
        if total == 0:
            return {
                "total_tasks": 0,
                "completed": 0,
                "failed": 0,
                "average_duration_ms": 0,
            }

        completed = sum(
            1 for e in self._execution_events if e.status == TaskStatus.COMPLETED
        )
        failed = sum(1 for e in self._execution_events if e.status == TaskStatus.FAILED)

        durations = [e.duration_ms for e in self._execution_events if e.duration_ms > 0]
        avg_duration = sum(durations) / len(durations) if durations else 0

        return {
            "total_tasks": total,
            "completed": completed,
            "failed": failed,
            "average_duration_ms": avg_duration,
        }


class Observability:
    """
    Main observability class.

    Combines metrics collection and task monitoring.
    """

    def __init__(self, logger: logging.Logger | None = None):
        """Initialize observability."""
        self._logger = logger or logging.getLogger(__name__)
        self._metric_collector = MetricCollector()
        self._task_monitor = TaskMonitor(self._logger)

    def get_metric_collector(self) -> MetricCollector:
        """Get metric collector."""
        return self._metric_collector

    def get_task_monitor(self) -> TaskMonitor:
        """Get task monitor."""
        return self._task_monitor

    def log_info(self, message: str, **kwargs):
        """Log info message."""
        self._logger.info(message, **kwargs)

    def log_debug(self, message: str, **kwargs):
        """Log debug message."""
        self._logger.debug(message, **kwargs)

    def log_warning(self, message: str, **kwargs):
        """Log warning message."""
        self._logger.warning(message, **kwargs)

    def log_error(self, message: str, **kwargs):
        """Log error message."""
        self._logger.error(message, **kwargs)

    def get_summary(self) -> dict[str, Any]:
        """Get observability summary."""
        return {
            "metrics": self._metric_collector.get_metrics(),
            "execution_summary": self._task_monitor.get_summary(),
            "counters": self._metric_collector.get_counters(),
        }


# Global observability instance
_global_observability: Observability | None = None


def get_observability() -> Observability:
    """Get global observability instance."""
    global _global_observability
    if _global_observability is None:
        _global_observability = Observability()
    return _global_observability
