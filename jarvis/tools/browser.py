"""Browser tool utilities.

This module keeps Playwright optional so the app can start even if browser
automation dependencies are not installed.
"""

def browser_task(goal: str) -> str:
    """Execute a browser task (search/scrape) using Playwright.
    Currently implements a simple Google search + summarize first result logic for demo.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return (
            "Browser task unavailable: Playwright is not installed. "
            "Install dependency 'playwright' and run 'playwright install'."
        )

    try:
        with sync_playwright() as p:
            # Headful mode so user can see what's happening
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            
            # Simple heuristic: treat 'goal' as a search query
            # In a real agent, the LLM would decide specific URL or search
            print(f"[Browser] Searching for: {goal}")
            page.goto("https://www.google.com")
            page.fill("textarea[name='q']", goal)
            page.press("textarea[name='q']", "Enter")
            
            # Wait for results
            page.wait_for_selector("#search")
            
            # Extract text from first result snippet if possible
            # This is fragile but okay for a v1 demo
            snippet = "No direct snippet found."
            try:
                # Common Google snippet selector
                snippet_el = page.query_selector(".VwiC3b") 
                if snippet_el:
                    snippet = snippet_el.inner_text()
                else:
                    snippet_el = page.query_selector("#search")
                    if snippet_el:
                        snippet = snippet_el.inner_text()[:500] + "..."
            except:
                pass

            browser.close()
            return f"Browser Task Result: {snippet}"
    except Exception as e:
        return f"Browser task failed: {e}"
