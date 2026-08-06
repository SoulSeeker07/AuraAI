"""
Pipeline Error Types
Location: src/core/orchestration/pipeline_error.py

Exceptions for fail-loud DAG execution.  When a required artifact payload
is missing, the pipeline must halt and report — never silently fabricate
placeholder content.
"""


class ArtifactPayloadMissing(Exception):
    """Raised when a required input artifact has no content payload.

    This means an upstream DAG stage either:
    - Failed to produce output (e.g. research backend returned nothing)
    - Produced an Artifact without populating its ``content`` field

    The pipeline cannot continue because downstream tasks depend on this data.
    """

    def __init__(self, task_id: str, artifact_id: str):
        self.task_id = task_id
        self.artifact_id = artifact_id
        super().__init__(
            f"Task '{task_id}' requires artifact '{artifact_id}' "
            f"but it has no content payload. Pipeline cannot continue."
        )


class PipelineStageFailure(Exception):
    """Raised when a DAG stage fails and downstream stages cannot proceed."""

    def __init__(self, stage_task_id: str, reason: str):
        self.stage_task_id = stage_task_id
        self.reason = reason
        super().__init__(
            f"Pipeline stage '{stage_task_id}' failed: {reason}. "
            f"Downstream stages have been cancelled."
        )
