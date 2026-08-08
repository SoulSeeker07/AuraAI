"""
End-to-End Integration Test for Universal Action Pipeline via MasterOrchestrator.
Tests multi-turn user requests through MasterOrchestrator and verifies state retention,
capability resolution, execution observations, and safety gates.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from browser.context_store import ContextStore, MediaItem
from core.orchestration.master_orchestrator import MasterOrchestrator


def run_e2e_shopping_flow():
    """Run multi-turn e-commerce shopping flow through MasterOrchestrator."""
    ContextStore.reset_instance()
    orchestrator = MasterOrchestrator.get_instance()

    # Turn 1: Search
    r1 = orchestrator.process_request("Find laptops under ₹70,000")
    assert r1.success is True
    assert "Found" in r1.observations[0] or "products" in r1.observations[0]

    # Turn 2: Filter RAM
    r2 = orchestrator.process_request("Only 16GB")
    assert r2.success is True
    assert "Filter applied" in r2.observations[0]

    # Turn 3: Filter Brand
    r3 = orchestrator.process_request("No HP")
    assert r3.success is True
    assert "Filter applied" in r3.observations[0]

    # Turn 4: Check reviews
    r4 = orchestrator.process_request("Check the reviews")
    assert r4.success is True
    assert "Customer reviews summary" in r4.observations[1]

    # Turn 5: Add to cart
    r5 = orchestrator.process_request("Add it to cart")
    assert r5.success is True
    assert "Added" in r5.observations[0]

    # Turn 6: Proceed to checkout
    r6 = orchestrator.process_request("Proceed to checkout")
    # Verify safety gate (requires user approval for placing payment)
    assert r6.data["checkout_result"]["requires_approval"] is True


def run_e2e_media_flow():
    """Run multi-turn YouTube/media playback flow through MasterOrchestrator."""
    ContextStore.reset_instance()
    store = ContextStore.get_instance()
    orchestrator = MasterOrchestrator.get_instance()

    # Setup simulated playlist in MediaContext
    store.media.playlist = [
        MediaItem(
            title="Python Full Course", url="https://youtube.com/watch?v=1", index=1
        ),
        MediaItem(
            title="Python Intermediate Tutorial",
            url="https://youtube.com/watch?v=2",
            index=2,
        ),
        MediaItem(
            title="Python Advanced OOP", url="https://youtube.com/watch?v=3", index=3
        ),
    ]

    # Turn 1: Play second
    r1 = orchestrator.process_request("Play the second one")
    assert r1.success is True

    # Turn 2: Next
    r2 = orchestrator.process_request("Next")
    assert r2.success is True
    assert "Played next video" in r2.observations[0]

    # Turn 3: Previous
    r3 = orchestrator.process_request("Previous")
    assert r3.success is True
    assert "Played previous video" in r3.observations[0]

    # Turn 4: Pause
    r4 = orchestrator.process_request("Pause")
    assert r4.success is True
    assert "paused" in r4.observations[0]

    # Turn 5: Resume
    r5 = orchestrator.process_request("Resume")
    assert r5.success is True
    assert "resumed" in r5.observations[0]

    # Turn 6: Check comments
    r6 = orchestrator.process_request("Check the comments")
    assert r6.success is True
    assert "Super helpful explanation" in r6.observations[1]


if __name__ == "__main__":
    run_e2e_shopping_flow()
    print("✓ E2E Shopping Flow Passed!")
    run_e2e_media_flow()
    print("✓ E2E Media Flow Passed!")
