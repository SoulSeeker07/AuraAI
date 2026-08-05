"""
Native Diagnostics
Detailed timing breakdown for native operations.

Shows:
- Permission check time
- Execution time
- Verification time
- Events time
- Context update time
- Total time
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from .native_execution_context import NativeExecutionContext


class DiagnosticsStage(Enum):
    """Stages in the execution pipeline"""

    PERMISSION = "permission"
    EXECUTION = "execution"
    VERIFICATION = "verification"
    EVENTS = "events"
    CONTEXT = "context"
    COMPLETE = "complete"


@dataclass
class StageTiming:
    """
    Timing information for a specific stage.

    Tracks when the stage started, completed, and duration.
    """

    stage: DiagnosticsStage
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: float = 0.0

    def start(self) -> None:
        """Start timing"""
        self.started_at = datetime.now()

    def complete(self) -> None:
        """Complete timing"""
        if self.started_at:
            self.completed_at = datetime.now()
            self.duration_ms = (
                self.completed_at - self.started_at
            ).total_seconds() * 1000

    def get_formatted_duration(self) -> str:
        """Get duration formatted as readable string"""
        if self.duration_ms < 1000:
            return f"{self.duration_ms:.2f}ms"
        elif self.duration_ms < 60000:
            return f"{self.duration_ms / 1000:.2f}s"
        else:
            return f"{self.duration_ms / 60000:.2f}m"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "stage": self.stage.value,
            "duration_ms": self.duration_ms,
            "duration_formatted": self.get_formatted_duration(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }


class NativeDiagnostics:
    """
    Diagnostics for native operations.

    Provides detailed timing and performance metrics.
    """

    def __init__(self):
        """Initialize diagnostics"""
        self.timings: dict[DiagnosticsStage, StageTiming] = {}
        self.operation_started_at: datetime | None = None
        self.total_duration_ms: float = 0.0

    def start_operation(self) -> None:
        """Start timing for the operation"""
        self.operation_started_at = datetime.now()
        self.timings = {}
        self.total_duration_ms = 0.0

    def start_stage(self, stage: DiagnosticsStage) -> None:
        """
        Start timing for a stage.

        Args:
            stage: Stage to start timing
        """
        if stage in self.timings:
            # If stage already exists, use the existing one
            self.timings[stage].start()
        else:
            # Create new timing
            timing = StageTiming(stage=stage)
            timing.start()
            self.timings[stage] = timing

    def complete_stage(self, stage: DiagnosticsStage) -> None:
        """
        Complete timing for a stage.

        Args:
            stage: Stage to complete timing
        """
        if stage in self.timings:
            self.timings[stage].complete()

    def get_stage_duration(self, stage: DiagnosticsStage) -> float:
        """
        Get duration for a specific stage.

        Args:
            stage: Stage to get duration for

        Returns:
            Duration in milliseconds
        """
        if stage in self.timings:
            return self.timings[stage].duration_ms
        return 0.0

    def complete_operation(self) -> None:
        """Complete timing for the operation"""
        # Calculate total duration
        if self.operation_started_at and self.timings:
            last_stage = list(self.timings.values())[-1]
            if last_stage.completed_at:
                self.total_duration_ms = (
                    last_stage.completed_at - self.operation_started_at
                ).total_seconds() * 1000
            else:
                self.total_duration_ms = (
                    datetime.now() - self.operation_started_at
                ).total_seconds() * 1000

    def to_dict(self) -> dict[str, Any]:
        """
        Convert diagnostics to dictionary.

        Returns:
            Dictionary with complete diagnostics
        """
        return {
            "total_duration_ms": self.total_duration_ms,
            "total_duration_formatted": self._format_duration(self.total_duration_ms),
            "operation_started_at": (
                self.operation_started_at.isoformat()
                if self.operation_started_at
                else None
            ),
            "stages": {
                stage.value: timing.to_dict() for stage, timing in self.timings.items()
            },
            "stage_durations_ms": {
                stage.value: timing.duration_ms
                for stage, timing in self.timings.items()
            },
            "stage_durations_formatted": {
                stage.value: timing.get_formatted_duration()
                for stage, timing in self.timings.items()
            },
        }

    def to_detailed_report(self) -> str:
        """
        Generate a detailed text report.

        Returns:
            Formatted report string
        """
        report = f"\n{'='*60}\n"
        report += "NATIVE OPERATION DIAGNOSTICS\n"
        report += f"{'='*60}\n\n"
        report += "Operation: N/A\n"
        report += f"Started: {self.operation_started_at.isoformat() if self.operation_started_at else 'N/A'}\n"
        report += f"Total Duration: {self.total_duration_ms:.2f}ms ({self._format_duration(self.total_duration_ms)})\n\n"
        report += f"{'-'*60}\n"
        report += "STAGE TIMINGS:\n"
        report += f"{'-'*60}\n\n"

        for stage, timing in self.timings.items():
            report += f"{stage.value.upper():<15} : {timing.get_formatted_duration():>10} ({timing.duration_ms:>6.2f}ms)\n"
            if timing.started_at:
                report += f"  Started: {timing.started_at.isoformat()}\n"
            if timing.completed_at:
                report += f"  Completed: {timing.completed_at.isoformat()}\n"

        report += f"\n{'-'*60}\n"
        report += "STAGE BREAKDOWN:\n"
        report += f"{'-'*60}\n\n"

        for stage, timing in self.timings.items():
            percentage = (
                (timing.duration_ms / self.total_duration_ms * 100)
                if self.total_duration_ms > 0
                else 0
            )
            report += f"{stage.value.upper():<15} : {timing.duration_ms:>6.2f}ms ({percentage:>5.1f}%)\n"

        report += f"\n{'='*60}\n\n"

        return report

    def _format_duration(self, duration_ms: float) -> str:
        """
        Format duration for display.

        Args:
            duration_ms: Duration in milliseconds

        Returns:
            Formatted duration string
        """
        if duration_ms < 1000:
            return f"{duration_ms:.2f}ms"
        elif duration_ms < 60000:
            return f"{duration_ms / 1000:.2f}s"
        else:
            return f"{duration_ms / 60000:.2f}m"


class DiagnosticsReporter:
    """
    Reporter for native diagnostics.

    Provides methods to generate diagnostics for different scenarios.
    """

    @staticmethod
    def generate_execution_diagnostics(
        context: NativeExecutionContext,
    ) -> dict[str, Any]:
        """
        Generate diagnostics from execution context.

        Args:
            context: Execution context

        Returns:
            Dictionary with diagnostics
        """
        return {
            "capability": context.capability,
            "stage": context.stage.value,
            "status": context.status.value,
            "permission": {
                "required": context.permission.value if context.permission else None,
                "granted": context.permission_granted,
                "denied_reason": context.permission_denied_reason,
            },
            "timing": {
                "total_duration_ms": context.get_duration_ms(),
                "total_duration_formatted": context.get_duration_ms_formatted(),
            },
            "metrics": context.get_metrics(),
            "manager": context.manager_name,
            "category": context.category,
            "verification": {
                "passed": context.verification_passed,
                "error": context.verification_error,
            },
            "events": context.events_triggered,
            "aborted": context.aborted,
            "rollback_available": context.rollback_function is not None,
        }

    @staticmethod
    def generate_stage_breakdown(context: NativeExecutionContext) -> dict[str, Any]:
        """
        Generate stage-by-stage breakdown.

        Args:
            context: Execution context

        Returns:
            Dictionary with stage breakdown
        """
        # This would require timing each stage explicitly
        # For now, we'll provide estimated timing based on metrics
        return {
            "total_duration_ms": context.get_duration_ms(),
            "stages": {
                "permission_check": {
                    "estimated_ms": 1.0,  # Permission checks are fast
                    "description": "Permission verification",
                },
                "execution": {
                    "estimated_ms": context.get_duration_ms()
                    * 0.8,  # Most time is in execution
                    "description": "Capability execution",
                },
                "verification": {
                    "estimated_ms": context.get_duration_ms()
                    * 0.1,  # Verification is usually fast
                    "description": "Result verification",
                },
                "events": {
                    "estimated_ms": context.get_duration_ms()
                    * 0.05,  # Events are quick
                    "description": "Event triggering",
                },
                "context": {
                    "estimated_ms": context.get_duration_ms()
                    * 0.05,  # Context updates are quick
                    "description": "Context synchronization",
                },
            },
        }

    @staticmethod
    def generate_performance_summary(diagnostics: NativeDiagnostics) -> str:
        """
        Generate a performance summary.

        Args:
            diagnostics: Diagnostics object

        Returns:
            Formatted summary string
        """
        summary = f"\n{'='*60}\n"
        summary += "PERFORMANCE SUMMARY\n"
        summary += f"{'='*60}\n\n"

        summary += f"Total Duration: {diagnostics.total_duration_ms:.2f}ms\n\n"
        summary += f"{'-'*60}\n"
        summary += "STAGE BREAKDOWN:\n"
        summary += f"{'-'*60}\n\n"

        for stage, timing in diagnostics.timings.items():
            percentage = (
                (timing.duration_ms / diagnostics.total_duration_ms * 100)
                if diagnostics.total_duration_ms > 0
                else 0
            )
            bar_length = int(percentage / 2)  # Scale for display
            bar = "█" * bar_length

            summary += f"{stage.value.upper():<15} {timing.get_formatted_duration():>10} ({percentage:>5.1f}%)\n"
            summary += f"{' ' * 20}{bar}\n\n"

        summary += f"{'='*60}\n\n"

        return summary

    @staticmethod
    def generate_gui_timeline(diagnostics: NativeDiagnostics) -> dict[str, Any]:
        """
        Generate a GUI timeline for visualization.

        Args:
            diagnostics: Diagnostics object

        Returns:
            Dictionary with timeline data
        """
        timeline = []

        for stage, timing in diagnostics.timings.items():
            timeline.append(
                {
                    "stage": stage.value,
                    "duration_ms": timing.duration_ms,
                    "percentage": (
                        (timing.duration_ms / diagnostics.total_duration_ms * 100)
                        if diagnostics.total_duration_ms > 0
                        else 0
                    ),
                    "color": _get_stage_color(stage.value),
                }
            )

        return {
            "total_duration_ms": diagnostics.total_duration_ms,
            "stages": timeline,
        }


def _get_stage_color(stage: str) -> str:
    """
    Get color for stage in GUI.

    Args:
        stage: Stage name

    Returns:
        Color name
    """
    colors = {
        "permission": "#3b82f6",  # Blue
        "execution": "#10b981",  # Green
        "verification": "#f59e0b",  # Amber
        "events": "#8b5cf6",  # Purple
        "context": "#ec4899",  # Pink
        "complete": "#6b7280",  # Gray
    }

    return colors.get(stage.lower(), "#6b7280")


# Singleton instance
_diagnostics: NativeDiagnostics | None = None


def get_diagnostics() -> NativeDiagnostics:
    """
    Get or create the global diagnostics singleton.

    Returns:
        NativeDiagnostics instance
    """
    global _diagnostics
    if _diagnostics is None:
        _diagnostics = NativeDiagnostics()
    return _diagnostics


def reset_diagnostics() -> None:
    """Reset the global diagnostics"""
    global _diagnostics
    _diagnostics = None
