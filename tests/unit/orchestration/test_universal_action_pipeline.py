"""
Unit Tests for Universal Action Pipeline & Multi-Turn State Persistence.
Tests natural language variations for media controls, shopping constraints,
relative reference resolution ("it", "the first one", "next", "previous"),
and end-to-end execution through TaskDecomposer, ContextStore, and PlaywrightBrowserAdapter.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from browser.context_store import ContextStore, MediaItem
from core.backends.adapters.browser_backend import PlaywrightBrowserAdapter
from core.orchestration.task_decomposer import PlannerRole, TaskDecomposer


def test_shopping_multi_turn_constraint_accumulation():
    """
    Validates that sequential follow-up constraints accumulate in ShoppingContext
    without wiping out prior constraints (e.g. price -> RAM -> brand exclude -> sort).
    """
    ContextStore.reset_instance()
    decomposer = TaskDecomposer()

    # Turn 1: "Find laptops under ₹70,000"
    g1 = decomposer.decompose("Find laptops under ₹70,000")
    t1 = list(g1.subtasks.values())[0]
    assert t1.capability == "shopping.search"
    c1 = t1.parameters["constraints"]
    assert c1["category"] == "laptop"
    assert c1["price_max"] == 70000.0

    # Turn 2: "Only 16GB"
    g2 = decomposer.decompose("Only 16GB")
    t2 = list(g2.subtasks.values())[0]
    assert t2.capability == "shopping.filter"
    c2 = t2.parameters["constraints"]
    assert c2["price_max"] == 70000.0  # Retained from turn 1!
    assert c2["ram_gb_min"] == 16  # Added in turn 2!

    # Turn 3: "No HP"
    g3 = decomposer.decompose("No HP")
    t3 = list(g3.subtasks.values())[0]
    assert t3.capability == "shopping.filter"
    c3 = t3.parameters["constraints"]
    assert c3["price_max"] == 70000.0  # Retained!
    assert c3["ram_gb_min"] == 16  # Retained!
    assert "HP" in c3["brand_exclude"]  # Added!

    # Turn 4: "Sort by rating"
    g4 = decomposer.decompose("Sort by rating")
    t4 = list(g4.subtasks.values())[0]
    assert t4.capability == "shopping.filter"
    c4 = t4.parameters["constraints"]
    assert c4["sort_by"] == "rating"


def test_media_multi_turn_navigation_and_relative_references():
    """
    Validates natural language variations for media controls and relative reference resolution.
    """
    ContextStore.reset_instance()
    store = ContextStore.get_instance()
    decomposer = TaskDecomposer()

    # Setup simulated playlist
    store.media.playlist = [
        MediaItem(title="Python Tutorial 1", url="https://youtube.com/v1", index=1),
        MediaItem(title="Python Tutorial 2", url="https://youtube.com/v2", index=2),
        MediaItem(title="Python Tutorial 3", url="https://youtube.com/v3", index=3),
    ]

    # Turn 1: "Play the second one"
    g1 = decomposer.decompose("Play the second one")
    t1 = list(g1.subtasks.values())[0]
    rel1 = store.resolve_relative_reference("Play the second one")
    assert rel1.get("media").title == "Python Tutorial 2"

    # Turn 2: Natural language variations for NEXT
    for phrase in ["next video", "play the next one", "next", "skip this one"]:
        g = decomposer.decompose(phrase)
        task = list(g.subtasks.values())[0]
        assert task.capability == "media.next"

    # Turn 3: Natural language variations for PREVIOUS
    for phrase in ["previous video", "play the previous one", "previous", "go back"]:
        g = decomposer.decompose(phrase)
        task = list(g.subtasks.values())[0]
        assert task.capability == "media.previous"

    # Turn 4: Natural language variations for PAUSE / RESUME
    g_pause = decomposer.decompose("pause the video")
    assert list(g_pause.subtasks.values())[0].capability == "media.pause"

    g_resume = decomposer.decompose("resume playback")
    assert list(g_resume.subtasks.values())[0].capability == "media.resume"


def test_comments_reviews_cart_checkout_execution():
    """
    Validates end-to-end execution of comments, reviews, add to cart, and checkout capabilities.
    """
    ContextStore.reset_instance()
    store = ContextStore.get_instance()
    decomposer = TaskDecomposer()
    adapter = PlaywrightBrowserAdapter()

    # Turn 1: "Check the comments"
    g_comm = decomposer.decompose("check the comments")
    t_comm = list(g_comm.subtasks.values())[0]
    assert t_comm.capability == "browser.comments"
    res_comm = adapter.execute(t_comm.capability, t_comm.description, t_comm.parameters)
    assert res_comm.success is True
    assert "Super helpful explanation" in res_comm.observations[1]

    # Turn 2: "Check the reviews"
    g_rev = decomposer.decompose("check the reviews")
    t_rev = list(g_rev.subtasks.values())[0]
    assert t_rev.capability == "shopping.reviews"
    res_rev = adapter.execute(t_rev.capability, t_rev.description, t_rev.parameters)
    assert res_rev.success is True
    assert "4.5/5 stars" in res_rev.observations[1]

    # Turn 3: "Add it to cart"
    store.shopping.products = [
        {"title": "Lenovo Legion i7", "price": "$1200", "url": "https://amazon.com/p1"}
    ]
    g_cart = decomposer.decompose("add it to cart")
    t_cart = list(g_cart.subtasks.values())[0]
    assert t_cart.capability == "shopping.cart.add"
    res_cart = adapter.execute(t_cart.capability, t_cart.description, t_cart.parameters)
    assert res_cart.success is True
    assert "Lenovo Legion i7" in res_cart.observations[0]

    # Turn 4: "Go to checkout"
    g_chk = decomposer.decompose("proceed to checkout")
    t_chk = list(g_chk.subtasks.values())[0]
    assert t_chk.capability == "shopping.checkout"
    res_chk = adapter.execute(t_chk.capability, t_chk.description, t_chk.parameters)
    # Check safety gate: requires user approval for order completion
    assert res_chk.data["checkout_result"]["requires_approval"] is True
