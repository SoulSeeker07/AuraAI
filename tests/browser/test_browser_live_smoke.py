"""
Live Browser Automation Subsystem Smoke Test with Dynamic Asynchronous JS Content
Location: tests/browser/test_browser_live_smoke.py
"""

import pytest
import asyncio
from browser.engine import BrowserEngine, PLAYWRIGHT_AVAILABLE


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_browser_dynamic_js_rendering_and_interaction():
    """
    Live smoke test exercising real Playwright Chromium against dynamically injected DOM elements.
    Verifies that autowaiting resolves elements inserted asynchronously via JavaScript (post initial paint)
    and executes click mutation and content extraction.
    """
    if not PLAYWRIGHT_AVAILABLE:
        pytest.skip("Playwright is not available in current environment")

    engine = BrowserEngine(headless=True)
    started = await engine.start()
    assert started is True, "Failed to launch headless Chromium instance"
    assert engine.is_active is True
    assert engine._page is not None

    try:
        # 1. Load an initial HTML page that injects dynamic content after 400ms delay via JS
        html_payload = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Dynamic JS Test Page</title>
        </head>
        <body>
            <h1>AuraAI Dynamic Rendering Test</h1>
            <p id="status">Loading async dynamic elements...</p>
            <div id="container"></div>

            <script>
                setTimeout(() => {
                    const container = document.getElementById('container');
                    const btn = document.createElement('button');
                    btn.id = 'async-action-btn';
                    btn.textContent = 'Confirm Action';
                    btn.onclick = () => {
                        document.getElementById('status').textContent = 'Action Completed Successfully!';
                    };
                    container.appendChild(btn);
                }, 400);
            </script>
        </body>
        </html>
        """

        # Set page content directly
        await engine._page.set_content(html_payload)

        # 2. Strict find_element on the dynamic button with autowaiting timeout
        find_res = await engine.find_element("#async-action-btn", timeout_ms=4000)
        assert find_res["success"] is True, f"Failed to locate async-injected element: {find_res.get('error')}"
        assert find_res["count"] == 1

        # 3. Click the dynamic button (ActionRisk.HIGH mutation)
        click_res = await engine.click("#async-action-btn", timeout_ms=3000)
        assert click_res["success"] is True, f"Click failed: {click_res.get('error')}"

        # 4. Verify DOM mutation took effect
        await asyncio.sleep(0.1)
        status_text = await engine._page.locator("#status").inner_text()
        assert status_text == "Action Completed Successfully!"

        # 5. Extract content and verify formatting
        extract_res = await engine.extract_content(format="markdown")
        assert extract_res["success"] is True
        assert "AuraAI Dynamic Rendering Test" in extract_res["content"]
        assert "Action Completed Successfully!" in extract_res["content"]

        # 6. Page observation
        obs_res = await engine.observe()
        assert obs_res["is_active"] is True
        assert obs_res["title"] == "Dynamic JS Test Page"

    finally:
        # Teardown
        await engine.close()
        assert engine.is_active is False
