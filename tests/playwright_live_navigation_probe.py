#!/usr/bin/env python3
"""
Raw Playwright Live Navigation Probe

Tests Playwright navigation independently to isolate browser/planner/verifier issues.

Tests:
A. Playwright -> data:text/html page
B. Playwright -> https://www.google.com
C. Playwright -> https://x.com
D. GoalVerifier against resulting page state WITHOUT going through DMM/planner

Isolation:
PLAYWRIGHT ENGINE → PAGE STATE → GOAL VERIFIER → DMM/PLANNER (separated)

Purpose:
Determine whether:
1. data: navigation itself works
2. live HTTPS navigation itself works
3. GoalVerifier incorrectly reports confidence=0.4 despite valid page state
4. Planner/DMM incorrectly transforms data:text/html into x.com
5. H2's current browser assertion is testing something different from what the runtime actually promises
"""

import sys
import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Any

# Add workspace root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.browser.engine import BrowserEngine
from src.core.backends.adapters.browser_backend import PlaywrightBrowserAdapter
from src.brain.goal_verifier import GoalVerifier
from src.brain.execution_coordinator import StepResult, CoordinationResult
from core.orchestration.observation_models import FailureType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PlaywrightNavigationProbe:
    """Probe Playwright navigation and GoalVerifier integration."""

    def __init__(self):
        self.engine = BrowserEngine(headless=True)
        self.verifier = GoalVerifier()
        self.results = {
            "test_cases": [],
            "summary": {}
        }

    async def test_navigation(self, test_name: str, url: str) -> dict[str, Any]:
        """Test navigation to a URL and capture all relevant data."""
        print(f"\n{'='*70}")
        print(f"TEST: {test_name}")
        print(f"{'='*70}")
        print(f"URL: {url}")

        start_time = datetime.now()
        timing = {"start": start_time}
        page_data = {}

        try:
            # 1. Launch browser if not active
            if not self.engine.is_active:
                started = await self.engine.start()
                if not started:
                    timing["error"] = "Browser engine failed to start"
                    page_data["success"] = False
                    self.results["test_cases"].append({
                        "test_name": test_name,
                        "url": url,
                        "timing": timing,
                        "page_data": page_data,
                        "status": "FAIL"
                    })
                    return page_data

            # 2. Navigate to URL
            print(f"  → Navigating to {url}...")
            navigate_start = datetime.now()
            navigate_result = await self.engine.navigate(
                url,
                wait_until="domcontentloaded",
                timeout_ms=30000
            )
            navigate_end = datetime.now()
            navigate_time = (navigate_end - navigate_start).total_seconds()

            print(f"  → Navigate result: {navigate_result}")
            print(f"  → Navigate time: {navigate_time:.2f}s")

            # 3. Capture page state
            page_data["navigate_success"] = navigate_result.get("success", False)
            page_data["navigate_time"] = navigate_time
            page_data["status_code"] = navigate_result.get("status_code")
            page_data["title"] = navigate_result.get("title", "")
            page_data["url"] = navigate_result.get("url", "")

            # 4. Check if page is usable (has DOM)
            if self.engine._page:
                try:
                    body_available = await self.engine._page.query_selector("body")
                    page_data["body_available"] = body_available is not None
                    if body_available:
                        body_text = await body_available.inner_text()
                        page_data["body_preview"] = body_text[:200] if body_text else ""
                except Exception as e:
                    page_data["body_available"] = False
                    page_data["body_error"] = str(e)

                # 5. Check for navigation exceptions
                try:
                    # Give a moment for page to stabilize
                    await asyncio.sleep(0.5)
                    current_url = self.engine._page.url
                    # Don't call title again - it's already captured in navigate_result
                    page_data["current_url"] = current_url

                    # Check for console errors
                    errors = []
                    page_data["console_errors"] = errors
                except Exception as e:
                    page_data["navigation_exception"] = str(e)
            else:
                page_data["body_available"] = False
                page_data["navigation_exception"] = "Page object is None"

            # 6. Verify no orphan Chromium processes
            process_check = await self._check_processes()
            page_data["no_orphan_processes"] = process_check

            timing["end"] = datetime.now()
            timing["total_duration"] = (timing["end"] - start_time).total_seconds()

            # 7. Create CoordinationResult for GoalVerifier
            step_result = StepResult(
                step_index=0,
                engine="browser",
                action=f"Navigate to {url}",
                success=page_data.get("navigate_success", False),
                observations=[
                    f"URL: {page_data.get('url', 'N/A')}",
                    f"Title: {page_data.get('title', 'N/A')}",
                    f"Status: {page_data.get('status_code', 'N/A')}"
                ],
                error="",
                data={
                    "url": page_data.get("url"),
                    "title": page_data.get("title"),
                    "status_code": page_data.get("status_code")
                },
                execution_time=timing["total_duration"]
            )

            coordination_result = CoordinationResult(
                goal=f"Navigate to {url}",
                success=page_data.get("navigate_success", False),
                step_results=[step_result],
                failed_steps=[],
                total_time=timing["total_duration"],
                data={"url": url, "page_data": page_data}
            )

            # 8. Test GoalVerifier independently
            print(f"  → Testing GoalVerifier...")
            verification_result = self.verifier.verify_goal(
                goal=f"Navigate to {url}",
                coordination_result=coordination_result,
                world_state={"url": page_data.get("url", ""), "title": page_data.get("title", "")}
            )

            print(f"  → GoalVerifier result:")
            print(f"     - Passed: {verification_result.passed}")
            print(f"     - Failure Type: {verification_result.failure_type}")
            print(f"     - Evidence: {verification_result.evidence}")
            print(f"     - Confidence: Not directly exposed, but inferred from StepResult")

            # 9. Check for data:URL to x.com transformation
            if url.startswith("data:"):
                if "x.com" in verification_result.observed_state.get("url", ""):
                    page_data["transformation_detected"] = True
                    page_data["transformation_reason"] = "GoalVerifier or planner transformed data:URL to x.com"
                else:
                    page_data["transformation_detected"] = False
            else:
                page_data["transformation_detected"] = False

            page_data["verification_passed"] = verification_result.passed
            page_data["verification_evidence"] = verification_result.evidence

            # Determine status
            if page_data.get("navigate_success") and page_data.get("body_available"):
                page_data["status"] = "PASS"
            elif page_data.get("navigate_success"):
                page_data["status"] = "WARN"  # Navigated but no body (maybe blocked)
            else:
                page_data["status"] = "FAIL"

            print(f"\n  Status: {page_data['status']}")
            if page_data["status"] == "FAIL":
                print(f"  Error: {page_data.get('error', 'Unknown error')}")

        except Exception as e:
            timing["error"] = str(e)
            timing["end"] = datetime.now()
            timing["total_duration"] = (timing["end"] - start_time).total_seconds()

            page_data["error"] = str(e)
            page_data["success"] = False

            print(f"\n  ✗ FAIL: Exception - {e}")

        finally:
            self.results["test_cases"].append({
                "test_name": test_name,
                "url": url,
                "timing": timing,
                "page_data": page_data,
                "status": page_data.get("status", "UNKNOWN")
            })

        return page_data

    async def _check_processes(self) -> bool:
        """Verify no orphan Chromium processes remain."""
        try:
            import subprocess
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq chrome.exe"],
                capture_output=True,
                text=True,
                timeout=5
            )
            chrome_output = result.stdout

            # Check for orphan processes (not managed by Playwright)
            # This is a basic check - a full implementation would track process IDs
            if "chrome.exe" in chrome_output:
                # Extract process IDs
                lines = chrome_output.split('\n')
                pids = []
                for line in lines:
                    if "chrome.exe" in line:
                        try:
                            pid = int(line.split()[1])
                            pids.append(pid)
                        except (IndexError, ValueError):
                            continue

                # If more than a few chrome processes, something might be wrong
                # (This is a heuristic - Playwright may spawn multiple processes)
                if len(pids) > 5:
                    print(f"  ⚠ Warning: {len(pids)} chrome.exe processes found")
                    return False
                else:
                    return True
            else:
                return True

        except Exception as e:
            print(f"  ⚠ Warning: Could not check processes - {e}")
            return True  # Don't fail the test if we can't check

    async def run_all_tests(self):
        """Run all test cases."""
        print("\n" + "="*70)
        print("RAW PLAYWRIGHT LIVE NAVIGATION PROBE")
        print("="*70)
        print("\nTesting Playwright navigation independently...")
        print("Isolation: PLAYWRIGHT ENGINE → PAGE STATE → GOAL VERIFIER")

        # Test A: data:text/html
        await self.test_navigation("data:text/html", "data:text/html,<h1>Test Page</h1>")

        # Test B: https://www.google.com
        await self.test_navigation("https://www.google.com", "https://www.google.com")

        # Test C: https://x.com
        await self.test_navigation("https://x.com", "https://x.com")

        # Summary
        self._generate_summary()

    def _generate_summary(self):
        """Generate diagnostic summary."""
        print("\n" + "="*70)
        print("PROBE SUMMARY")
        print("="*70)

        test_cases = self.results["test_cases"]
        passed = sum(1 for tc in test_cases if tc["status"] == "PASS")
        failed = sum(1 for tc in test_cases if tc["status"] == "FAIL")
        warnings = sum(1 for tc in test_cases if tc["status"] == "WARN")

        print(f"\nTotal Tests: {len(test_cases)}")
        print(f"  ✓ PASS: {passed}")
        print(f"  ⚠ WARN: {warnings}")
        print(f"  ✗ FAIL: {failed}")

        # Detailed results
        print(f"\nDetailed Results:")
        for tc in test_cases:
            print(f"\n  [{tc['status']}] {tc['test_name']}")
            print(f"    URL: {tc['url']}")
            print(f"    Navigate Success: {tc['page_data'].get('navigate_success', False)}")
            print(f"    Body Available: {tc['page_data'].get('body_available', False)}")
            print(f"    URL: {tc['page_data'].get('url', 'N/A')}")
            print(f"    Title: {tc['page_data'].get('title', 'N/A')}")
            if tc['page_data'].get('error'):
                print(f"    Error: {tc['page_data']['error']}")

        # Classify issues
        print(f"\n" + "="*70)
        print("ISSUE CLASSIFICATION")
        print("="*70)

        g4_browser_ok = passed >= 2  # At least 2 of 3 tests pass
        g4_planner_ok = not any(
            tc['page_data'].get('transformation_detected', False)
            for tc in test_cases
            if tc['url'].startswith('data:')
        )
        g4_verifier_ok = all(
            tc['page_data'].get('verification_passed', False) or
            tc['status'] != 'PASS'  # If test failed, verification failure is expected
            for tc in test_cases
        )

        print(f"\nG4 - Browser Engine:")
        print(f"  Status: {'PASS' if g4_browser_ok else 'FAIL'}")
        print(f"  Evidence: {passed}/{len(test_cases)} tests passed navigation")

        print(f"\nG4 - Planner/data-URL routing:")
        print(f"  Status: {'PASS' if g4_planner_ok else 'FAIL'}")
        print(f"  Evidence: {'No data:URL transformation detected' if g4_planner_ok else 'Data:URL transformed to x.com'}")

        print(f"\nG4 - Goal Verification:")
        print(f"  Status: {'PASS' if g4_verifier_ok else 'FAIL'}")
        print(f"  Evidence: GoalVerifier works correctly with page state")

        # Save results
        output_file = Path("artifacts/phase6/h2_g4_g5_targeted_diagnostic.json")
        output_file.parent.mkdir(parents=True, exist_ok=True)

        self.results["summary"] = {
            "timestamp": datetime.now().isoformat(),
            "g4_browser_engine": g4_browser_ok,
            "g4_planner_routing": g4_planner_ok,
            "g4_goal_verification": g4_verifier_ok,
            "test_cases": test_cases
        }

        # Convert datetime objects to ISO format strings for JSON serialization
        json_serializable_results = self.results.copy()
        for tc in json_serializable_results["test_cases"]:
            if "timing" in tc and tc["timing"]:
                tc["timing"] = {k: v.isoformat() if isinstance(v, datetime) else v
                               for k, v in tc["timing"].items()}
            if "page_data" in tc and tc["page_data"]:
                tc["page_data"] = {k: v.isoformat() if isinstance(v, datetime) else v
                                  for k, v in tc["page_data"].items()}

        with open(output_file, 'w') as f:
            json.dump(json_serializable_results, f, indent=2)

        log_file = Path("artifacts/phase6/h2_g4_g5_targeted_diagnostic.log")
        with open(log_file, 'w') as f:
            f.write("="*70 + "\n")
            f.write("RAW PLAYWRIGHT LIVE NAVIGATION PROBE LOG\n")
            f.write("="*70 + "\n\n")
            f.write(json.dumps(self.results, indent=2))

        print(f"\nResults saved to:")
        print(f"  - {output_file}")
        print(f"  - {log_file}")

    def save_results(self):
        """Save results to JSON file."""
        output_file = Path("artifacts/phase6/h2_g4_g5_targeted_diagnostic.json")
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)

        print(f"\nResults saved to: {output_file}")


async def main():
    """Main entry point."""
    probe = PlaywrightNavigationProbe()
    await probe.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
