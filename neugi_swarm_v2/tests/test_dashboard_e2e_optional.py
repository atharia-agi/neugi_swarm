"""Optional Playwright E2E checks for dashboard critical UX flows.

Run explicitly with:
  NEUGI_E2E=1 pytest tests/test_dashboard_e2e_optional.py -p no:anchorpy
"""

from __future__ import annotations

import os

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("NEUGI_E2E", "0") != "1",
    reason="Set NEUGI_E2E=1 to run optional browser E2E checks.",
)


def _import_playwright():
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Playwright unavailable: {exc}")
    return sync_playwright


def test_dashboard_critical_flows_optional():
    sync_playwright = _import_playwright()
    base_url = os.getenv("NEUGI_DASHBOARD_URL", "http://localhost:17901")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(base_url, wait_until="domcontentloaded", timeout=15000)

        # Core app loaded
        page.wait_for_selector("#chatInput", timeout=10000)
        page.wait_for_selector(".metrics-bar .metric-card[data-metric='agents']", timeout=10000)

        # Metric expand interaction
        page.click(".metrics-bar .metric-card[data-metric='agents']")
        expanded = page.get_attribute(".metrics-bar", "data-mode")
        assert expanded in {"expanded", "idle"}

        # Sidebar navigation to Config and Governance exists
        page.click(".nav-sidebar .nav-item[data-nav='config']")
        page.wait_for_selector("#tab-setup.active", timeout=8000)
        page.click(".nav-sidebar .nav-item[data-nav='governance']")
        page.wait_for_selector("#sidebarGovernance", timeout=8000)

        # Governance controls are present
        page.wait_for_selector("#setupGovernanceProfile", timeout=8000)
        page.wait_for_selector("#governanceStatus", timeout=8000)
        page.click("button:has-text('Preview Governance')")
        page.wait_for_timeout(400)

        # Provider setup flow smoke (must produce a status message)
        page.click(".nav-sidebar .nav-item[data-nav='config']")
        page.wait_for_selector("#tab-setup.active", timeout=8000)
        page.click("button:has-text('Test Provider')")
        page.wait_for_timeout(800)
        setup_status = page.locator("#setupStatus").inner_text().strip()
        assert setup_status != ""

        browser.close()
