"""
FakeAgyClient — a test double for AgySubprocessClient.

Usage in tests:
    from tests.fake_agy_client import FakeAgyClient, FakeAgyError
    from core.backends.adapters.antigravity_backend import CodingBackendAdapter

    # Success: client returns a valid JSON plan
    client = FakeAgyClient(responses=[{"files": [{"path": "hello.py", "content": "print()"}]}])
    adapter = CodingBackendAdapter(agy_client=client)

    # Failure: client raises AgyError (e.g. simulate timeout or unavailable binary)
    from core.backends.adapters.agy_subprocess_client import AgyTimeoutError
    client = FakeAgyClient(error=AgyTimeoutError(45.0))
    adapter = CodingBackendAdapter(agy_client=client)
"""

from core.backends.adapters.agy_subprocess_client import (
    AgyError,
    AgyPlanResult,
)


class FakeAgyClient:
    """
    Synchronous test double for AgySubprocessClient.
    
    responses: list of dicts — returned in order, then the last one repeats.
    error:     if set, raised on every call (simulates binary unavailable / timeout).
    call_count: how many times run_plan() was called (assert in tests).
    """

    def __init__(
        self,
        responses: list[dict] | None = None,
        error: AgyError | None = None,
    ):
        self.responses: list[dict] = responses or []
        self.error = error
        self.call_count = 0
        self.last_goal: str | None = None
        self.last_add_dir: str | None = None

    def run_plan(
        self,
        goal: str,
        add_dir: str | None = None,
        json_schema: str | None = None,
        timeout_s: float | None = None,
    ) -> AgyPlanResult:
        self.call_count += 1
        self.last_goal = goal
        self.last_add_dir = add_dir

        if self.error is not None:
            raise self.error

        idx = min(self.call_count - 1, len(self.responses) - 1)
        raw = self.responses[idx] if self.responses else {}

        return AgyPlanResult(
            raw=raw,
            conversation_id=f"fake-conv-{self.call_count}",
            elapsed_s=0.01,
            input_tokens=100,
            output_tokens=200,
            total_tokens=300,
        )
