"""
integration_example.py
=======================
Real integration guide for CapabilityUsageTracker in AuraAI.

This file shows WHERE and HOW to wire the tracker into the existing codebase.
Do NOT run this directly -- it is a reference guide with copy-paste snippets.
"""

# =============================================================================
# HOW THE TRACKER IS ALREADY WIRED (as of this commit)
# =============================================================================
#
# The hook is in _execute_level_task() in:
#   src/core/orchestration/master_orchestrator.py  (~line 2105)
#
# After all policy/auth checks pass and a backend is confirmed non-None,
# immediately before _dispatch_to_backend() is called:
#
#   try:
#       from core.capabilities.capability_usage_tracker import get_tracker as _get_cap_tracker
#       _pd = locals().get("policy_decision")
#       _risk_str = getattr(getattr(_pd, "risk", None), "value", None)
#       _session_obj = context.get("session") if isinstance(context, dict) else None
#       _src = getattr(_session_obj, "session_id", None) or "orchestrator"
#       _get_cap_tracker().record_usage(
#           capability_id=subtask.capability,
#           risk_level=_risk_str,
#           source=_src,
#       )
#   except Exception as _track_err:
#       logger.debug(f"[CapabilityTracker] record_usage skipped: {_track_err}")
#
# WHY THIS CHOKEPOINT:
#   - Every dispatched capability in every path (Desktop, CodeAct, Browser,
#     Research, Trigger) passes through _execute_level_task.
#   - Policy checks have already run -- we only record approved dispatches.
#   - Backend is confirmed non-None -- we only record real execution attempts.
#   - Same chokepoint as the OrchestrationStore task status update (line 2011).
#   - Anything that bypasses this also bypasses governance, which already
#     fails the AST guardrail test.
#
# DO NOT also hook ExecutionPolicy.evaluate_action() -- that double-counts,
# since evaluate_action fires even for requests that later fail or are denied.


# =============================================================================
# READING DATA FROM THE TRACKER
# =============================================================================

from pathlib import Path


def example_read_coverage():
    """Get live coverage stats -- usable from CLI, tests, or GUI."""
    from core.capabilities.capability_usage_tracker import get_tracker
    from core.capabilities.capability_registry import CapabilityRegistry

    reg = CapabilityRegistry.get_instance()
    all_ids = [c.name for c in reg.list()]
    tracker = get_tracker()

    # Coverage %
    coverage = tracker.get_coverage(len(all_ids))
    print(f"Coverage: {coverage['coverage_pct']}% "
          f"({coverage['used_at_least_once']}/{coverage['total_registered']})")

    # Least used (includes never-used as 0x)
    least = tracker.get_least_used(all_ids, n=10)
    for s in least:
        print(f"  {s.capability_id:40s}  {s.usage_count}x")

    # Most recently fired
    recent = tracker.get_most_recent(n=5)
    for s in recent:
        import time
        ago = int(time.time() - s.last_used_at) if s.last_used_at else -1
        print(f"  {s.capability_id:40s}  {ago}s ago")


# =============================================================================
# FEEDING THE HTML DASHBOARD (file-poll pattern)
# =============================================================================

def example_start_dashboard_file_writer(output_dir: Path) -> None:
    """
    Call once from your main GUI startup to begin writing dashboard.json
    every 3s for the HTML dashboard to file-poll.

    Place in your GUIClient.__init__ or AuraCore._init_executive_brain:

        from integration_example import example_start_dashboard_file_writer
        example_start_dashboard_file_writer(Path('storage/dashboard'))
    """
    try:
        from PySide6.QtCore import QTimer
        from core.capabilities.capability_usage_tracker import get_tracker
        from core.capabilities.capability_registry import CapabilityRegistry

        tracker = get_tracker()
        out_path = output_dir / "dashboard.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        def _write():
            try:
                ids = [c.name for c in CapabilityRegistry.get_instance().list()]
                tracker.export_dashboard_file(ids, out_path)
            except Exception as e:
                import logging
                logging.getLogger(__name__).debug(f"Dashboard write error: {e}")

        timer = QTimer()
        timer.setInterval(3000)
        timer.timeout.connect(_write)
        timer.start()
        _write()  # Immediate first write
        return timer  # Keep reference to prevent GC
    except ImportError:
        pass


# =============================================================================
# EMBEDDING THE NATIVE QT WIDGET IN ChatRightRail
# =============================================================================
#
# In src/gui/widgets/chat_right_rail.py, inside _build_accordion() or wherever
# you add accordion sections, add:
#
#   from gui.widgets.capability_dashboard_widget import CapabilityDashboardWidget
#
#   cap_section = self._make_accordion_section("Capability Coverage")
#   self._cap_dashboard = CapabilityDashboardWidget(parent=self)
#   cap_section.addWidget(self._cap_dashboard)
#
# The widget self-manages its QTimer. No external refresh calls needed.


# =============================================================================
# READING FROM THE DB DIRECTLY (for scripts / aura --doctor)
# =============================================================================

def example_cli_report() -> None:
    """Equivalent of `aura capability-coverage` -- print a text report."""
    from core.capabilities.capability_usage_tracker import get_tracker
    from core.capabilities.capability_registry import CapabilityRegistry

    reg = CapabilityRegistry.get_instance()
    all_ids = [c.name for c in reg.list()]
    data = get_tracker().export_dashboard_json(all_ids)

    cov = data["coverage"]
    print(f"\n=== Capability Coverage ===")
    print(f"  Total registered : {cov['total_registered']}")
    print(f"  Used at least 1x : {cov['used_at_least_once']}")
    print(f"  Never used       : {cov['never_used']}")
    print(f"  Coverage         : {cov['coverage_pct']}%")

    print(f"\n--- Top 10 Least Used ---")
    for s in data["least_used"][:10]:
        marker = "[NEVER]" if s["usage_count"] == 0 else f"[{s['usage_count']}x]"
        print(f"  {marker:10s}  {s['capability_id']}")

    print(f"\n--- 10 Most Recently Used ---")
    import time
    for s in data["most_recent"][:10]:
        ago = int(time.time() - s["last_used_at"]) if s["last_used_at"] else -1
        print(f"  {ago:6d}s ago  {s['capability_id']}  (risk={s['last_risk_level']})")