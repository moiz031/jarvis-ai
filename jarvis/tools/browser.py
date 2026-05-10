"""Browser operator utilities.

This module provides a small stateful browser operator that can execute
multi-step goals locally with Playwright when available.
"""

from __future__ import annotations

import re
import urllib.parse
import webbrowser
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(slots=True)
class BrowserStep:
    action: str
    value: str = ""


def _normalize_url(target: str) -> str:
    target = (target or "").strip()
    if not target:
        return "https://www.google.com"
    if target.startswith(("http://", "https://")):
        return target
    if "." in target and " " not in target:
        return "https://" + target
    return "https://www.google.com/search?q=" + urllib.parse.quote_plus(target)


class BrowserOperator:
    def __init__(self, headless: bool = False):
        self.headless = headless

    def plan_goal(self, goal: str) -> List[BrowserStep]:
        goal = (goal or "").strip()
        lowered = goal.lower()
        steps: List[BrowserStep] = []

        open_and_search = re.search(
            r"(?:open|go to|visit)\s+(.+?)\s+and\s+search\s+(.+)",
            goal,
            re.IGNORECASE,
        )
        if open_and_search:
            steps.append(BrowserStep("goto", _normalize_url(open_and_search.group(1))))
            steps.append(BrowserStep("type_search", open_and_search.group(2).strip()))
            steps.append(BrowserStep("open_first_result"))
            steps.append(BrowserStep("summarize"))
            return steps

        click_match = re.search(r"click\s+['\"]?(.+?)['\"]?$", goal, re.IGNORECASE)
        type_match = re.search(r"type\s+['\"]?(.+?)['\"]?$", goal, re.IGNORECASE)

        if any(token in lowered for token in ("open ", "go to ", "visit ")) and "search" not in lowered:
            cleaned = re.sub(r"^(?:open|go to|visit)\s+", "", goal, flags=re.IGNORECASE).strip()
            steps.append(BrowserStep("goto", _normalize_url(cleaned)))
        elif "search" in lowered:
            query_match = re.search(r"(?:search(?: for)?|look up)\s+(.+)", goal, re.IGNORECASE)
            query = query_match.group(1).strip() if query_match else goal
            steps.append(BrowserStep("search", query))
        else:
            steps.append(BrowserStep("search", goal))

        if type_match:
            steps.append(BrowserStep("type_first_input", type_match.group(1).strip()))
        if click_match:
            steps.append(BrowserStep("click_text", click_match.group(1).strip()))
        if "first result" in lowered or "open result" in lowered:
            steps.append(BrowserStep("open_first_result"))
        if any(token in lowered for token in ("summarize", "summary", "read this page", "what is on this page")):
            steps.append(BrowserStep("summarize"))
        elif steps[-1].action != "summarize":
            steps.append(BrowserStep("summarize"))
        return steps

    def execute_goal(self, goal: str) -> str:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            webbrowser.open(_normalize_url(goal))
            return (
                "Playwright install nahi tha, is liye browser ya search page open kar di gayi hai."
            )

        plan = self.plan_goal(goal)
        history: List[Dict[str, str]] = []

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context()
                page = context.new_page()
                page.set_default_timeout(15000)

                for step in plan:
                    result = self._run_step(page, step)
                    history.append({"action": step.action, "value": step.value, "result": result})

                summary = self._summarize_page(page)
                final_url = page.url
                browser.close()

            step_text = "; ".join(f"{item['action']}={item['result']}" for item in history[:4])
            return f"Browser operator complete. URL: {final_url}. Steps: {step_text}. Summary: {summary}"
        except Exception as exc:
            return f"Browser task failed: {exc}"

    def _run_step(self, page, step: BrowserStep) -> str:
        if step.action == "goto":
            page.goto(step.value, wait_until="domcontentloaded")
            return f"opened {page.url}"

        if step.action == "search":
            url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(step.value)
            page.goto(url, wait_until="domcontentloaded")
            return f"searched {step.value}"

        if step.action == "type_search":
            locator = self._first_visible(page, ["textarea[name='q']", "input[type='search']", "input[name='q']"])
            if locator is None:
                return "search box not found"
            locator.fill(step.value)
            locator.press("Enter")
            page.wait_for_load_state("domcontentloaded")
            return f"typed search {step.value}"

        if step.action == "type_first_input":
            locator = self._first_visible(page, ["input", "textarea"])
            if locator is None:
                return "input not found"
            locator.fill(step.value)
            return f"typed {step.value}"

        if step.action == "click_text":
            locator = page.get_by_text(step.value, exact=False).first
            if locator.count() == 0:
                return f"text '{step.value}' not found"
            locator.click(timeout=5000)
            page.wait_for_load_state("domcontentloaded")
            return f"clicked {step.value}"

        if step.action == "open_first_result":
            selectors = ["#search a h3", "a h3", "main a h3"]
            for selector in selectors:
                locator = page.locator(selector).first
                if locator.count() > 0:
                    locator.click(timeout=5000)
                    page.wait_for_load_state("domcontentloaded")
                    return "opened first result"
            link = page.locator("a").first
            if link.count() > 0:
                link.click(timeout=5000)
                page.wait_for_load_state("domcontentloaded")
                return "opened first link"
            return "first result not found"

        if step.action == "summarize":
            return self._summarize_page(page)

        return f"unsupported step {step.action}"

    def _first_visible(self, page, selectors: List[str]):
        for selector in selectors:
            locator = page.locator(selector).first
            try:
                if locator.count() > 0:
                    return locator
            except Exception:
                continue
        return None

    def _summarize_page(self, page) -> str:
        title = (page.title() or "").strip()
        pieces: List[str] = []
        for selector in ("main", "article", "body"):
            try:
                text = page.locator(selector).inner_text(timeout=2000).strip()
            except Exception:
                text = ""
            if text:
                compact = re.sub(r"\s+", " ", text)
                pieces.append(compact[:700])
                break
        content = pieces[0] if pieces else "Page text read nahi ho saka."
        return f"{title}: {content}"


def browser_task(goal: str) -> str:
    """Execute a browser goal using the local browser operator."""
    return BrowserOperator(headless=False).execute_goal(goal)
