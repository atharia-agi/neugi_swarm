"""
Browser Tool for NEUGI v2
==========================
Lightweight to heavy browser automation with tiered capabilities.

Features:
    - Tier 1: Jina Reader (no browser, fast)
    - Tier 2: Playwright headless (screenshots, clicks, forms)
    - Tier 3: Browser-Use integration (stealth, cloud)
    - DOM state extraction for Computer Use
    - Vision model integration ready
    - Action history and replay

Usage:
    from tools.browser import BrowserTool
    
    browser = BrowserTool()
    
    # Tier 1: Fast read
    text = browser.read("https://example.com")
    
    # Tier 2: Interactive
    browser.navigate("https://example.com")
    browser.click("button#submit")
    screenshot = browser.screenshot()
    
    # Tier 3: Full automation
    browser.automate([
        {"action": "navigate", "url": "https://example.com"},
        {"action": "fill", "selector": "#search", "text": "AI"},
        {"action": "click", "selector": "#submit"},
        {"action": "screenshot"}
    ])
"""

from __future__ import annotations

import base64
import json
import logging
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class BrowserConfig:
    """Browser tool configuration."""
    headless: bool = True
    browser_type: str = "chromium"  # chromium, firefox, webkit
    viewport_width: int = 1280
    viewport_height: int = 720
    timeout_ms: int = 30000
    screenshot_dir: str = ""
    stealth_mode: bool = False
    user_agent: str = ""


@dataclass
class DOMElement:
    """Represents a DOM element for Computer Use."""
    tag: str
    selector: str
    text: str = ""
    attributes: Dict[str, str] = field(default_factory=dict)
    children: List["DOMElement"] = field(default_factory=list)
    clickable: bool = False
    input_type: str = ""
    bounding_box: Optional[Dict[str, float]] = None


@dataclass
class BrowserAction:
    """A single browser action."""
    action: str  # navigate, click, fill, screenshot, scroll, wait
    selector: str = ""
    text: str = ""
    url: str = ""
    scroll_amount: int = 0
    wait_ms: int = 1000


class BrowserToolError(Exception):
    """Base exception for browser tool errors."""
    pass


class BrowserTool:
    """Tiered browser automation tool."""

    def __init__(self, config: Optional[BrowserConfig] = None):
        self.config = config or BrowserConfig()
        self._playwright = None
        self._browser = None
        self._page = None
        self._context = None
        self._action_history: List[BrowserAction] = []
        self._screenshot_dir = Path(self.config.screenshot_dir or tempfile.gettempdir()) / "neugi_browser"
        self._screenshot_dir.mkdir(parents=True, exist_ok=True)

    def _ensure_playwright(self) -> None:
        """Lazy-load Playwright."""
        if self._playwright is not None:
            return
        try:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
        except ImportError:
            raise BrowserToolError(
                "Playwright not installed. Run: pip install playwright && playwright install"
            )

    def _get_browser(self) -> Any:
        """Get or create browser instance."""
        if self._browser is not None:
            return self._browser
        
        self._ensure_playwright()
        browser_type = getattr(self._playwright, self.config.browser_type, self._playwright.chromium)
        
        launch_options = {"headless": self.config.headless}
        if self.config.stealth_mode:
            launch_options["args"] = [
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process"
            ]
        
        self._browser = browser_type.launch(**launch_options)
        return self._browser

    def _get_page(self) -> Any:
        """Get or create page."""
        if self._page is not None:
            return self._page
        
        browser = self._get_browser()
        context_options = {
            "viewport": {
                "width": self.config.viewport_width,
                "height": self.config.viewport_height
            }
        }
        if self.config.user_agent:
            context_options["user_agent"] = self.config.user_agent
        
        self._context = browser.new_context(**context_options)
        self._page = self._context.new_page()
        self._page.set_default_timeout(self.config.timeout_ms)
        return self._page

    # === Tier 1: Fast Read (no browser) ===

    def read(self, url: str) -> str:
        """Read webpage content without launching browser (Jina Reader)."""
        from tools.web_search import WebSearch
        ws = WebSearch()
        return ws.read_url(url)

    # === Tier 2: Interactive Browser ===

    def navigate(self, url: str) -> "BrowserTool":
        """Navigate to URL."""
        page = self._get_page()
        page.goto(url, wait_until="networkidle")
        self._action_history.append(BrowserAction(action="navigate", url=url))
        return self

    def click(self, selector: str) -> "BrowserTool":
        """Click element."""
        page = self._get_page()
        page.click(selector)
        self._action_history.append(BrowserAction(action="click", selector=selector))
        return self

    def fill(self, selector: str, text: str) -> "BrowserTool":
        """Fill form field."""
        page = self._get_page()
        page.fill(selector, text)
        self._action_history.append(BrowserAction(action="fill", selector=selector, text=text))
        return self

    def type_text(self, selector: str, text: str, delay_ms: int = 50) -> "BrowserTool":
        """Type text with human-like delay."""
        page = self._get_page()
        page.type(selector, text, delay=delay_ms)
        self._action_history.append(BrowserAction(action="fill", selector=selector, text=text))
        return self

    def scroll(self, direction: str = "down", amount: int = 500) -> "BrowserTool":
        """Scroll page."""
        page = self._get_page()
        if direction == "down":
            page.evaluate(f"window.scrollBy(0, {amount})")
        elif direction == "up":
            page.evaluate(f"window.scrollBy(0, -{amount})")
        self._action_history.append(BrowserAction(action="scroll", scroll_amount=amount if direction == "down" else -amount))
        return self

    def wait(self, milliseconds: int = 1000) -> "BrowserTool":
        """Wait for specified milliseconds."""
        time.sleep(milliseconds / 1000)
        self._action_history.append(BrowserAction(action="wait", wait_ms=milliseconds))
        return self

    def screenshot(self, full_page: bool = False) -> str:
        """Take screenshot and return base64."""
        page = self._get_page()
        timestamp = int(time.time())
        path = self._screenshot_dir / f"screenshot_{timestamp}.png"
        page.screenshot(path=str(path), full_page=full_page)
        
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        
        self._action_history.append(BrowserAction(action="screenshot"))
        return b64

    def get_text(self) -> str:
        """Get visible text content."""
        page = self._get_page()
        return page.inner_text("body")

    def get_title(self) -> str:
        """Get page title."""
        page = self._get_page()
        return page.title()

    def get_url(self) -> str:
        """Get current URL."""
        page = self._get_page()
        return page.url

    # === Computer Use: DOM Extraction ===

    def get_dom_state(self) -> List[DOMElement]:
        """Extract DOM state for Computer Use / Vision models."""
        page = self._get_page()
        
        js_script = """
        () => {
            const elements = [];
            const interactiveTags = ['a', 'button', 'input', 'select', 'textarea'];
            
            function extractElement(el, depth = 0) {
                if (depth > 3) return null;  // Limit depth
                
                const tag = el.tagName.toLowerCase();
                const rect = el.getBoundingClientRect();
                const isVisible = rect.width > 0 && rect.height > 0;
                
                if (!isVisible) return null;
                
                const info = {
                    tag: tag,
                    selector: el.id ? `#${el.id}` : el.className ? `.${el.className.split(' ')[0]}` : tag,
                    text: el.innerText?.substring(0, 200) || '',
                    attributes: {},
                    children: [],
                    clickable: interactiveTags.includes(tag) || el.onclick !== null,
                    input_type: el.type || '',
                    bounding_box: {
                        x: rect.x, y: rect.y,
                        width: rect.width, height: rect.height
                    }
                };
                
                // Key attributes
                ['id', 'class', 'name', 'placeholder', 'href', 'src', 'alt'].forEach(attr => {
                    if (el.hasAttribute(attr)) info.attributes[attr] = el.getAttribute(attr);
                });
                
                // Children (limited)
                if (depth < 2) {
                    Array.from(el.children).slice(0, 5).forEach(child => {
                        const childInfo = extractElement(child, depth + 1);
                        if (childInfo) info.children.push(childInfo);
                    });
                }
                
                return info;
            }
            
            // Extract top-level interactive elements
            document.querySelectorAll('body > *').forEach(el => {
                const info = extractElement(el, 0);
                if (info) elements.push(info);
            });
            
            // Also get all buttons and links
            document.querySelectorAll('button, a, input').forEach(el => {
                const info = extractElement(el, 0);
                if (info && !elements.find(e => e.attributes.id === info.attributes.id)) {
                    elements.push(info);
                }
            });
            
            return elements.slice(0, 50);  // Limit total
        }
        """
        
        result = page.evaluate(js_script)
        return [DOMElement(**item) for item in result]

    def get_clickable_elements(self) -> List[Dict[str, Any]]:
        """Get list of clickable elements with coordinates."""
        page = self._get_page()
        
        js_script = """
        () => {
            const elements = [];
            const tags = ['button', 'a', 'input[type="submit"]', 'input[type="button"]', '[role="button"]'];
            
            tags.forEach(tag => {
                document.querySelectorAll(tag).forEach((el, idx) => {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        elements.push({
                            index: idx,
                            tag: el.tagName.toLowerCase(),
                            text: (el.innerText || el.value || el.placeholder || '').substring(0, 50),
                            id: el.id,
                            class: el.className,
                            x: rect.x + rect.width / 2,
                            y: rect.y + rect.height / 2,
                            selector: el.id ? `#${el.id}` : `${el.tagName.toLowerCase()}:has-text("${(el.innerText || '').substring(0, 20)}")`
                        });
                    }
                });
            });
            
            return elements.slice(0, 30);
        }
        """
        
        return page.evaluate(js_script)

    def get_form_fields(self) -> List[Dict[str, Any]]:
        """Get all form input fields."""
        page = self._get_page()
        
        js_script = """
        () => {
            const fields = [];
            document.querySelectorAll('input, textarea, select').forEach((el, idx) => {
                const rect = el.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    fields.push({
                        index: idx,
                        tag: el.tagName.toLowerCase(),
                        type: el.type || 'text',
                        name: el.name,
                        id: el.id,
                        placeholder: el.placeholder,
                        label: document.querySelector(`label[for="${el.id}"]`)?.innerText || '',
                        selector: el.id ? `#${el.id}` : `input[name="${el.name}"]`
                    });
                }
            });
            return fields;
        }
        """
        
        return page.evaluate(js_script)

    # === Tier 3: Automation ===

    def automate(self, actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute a sequence of browser actions."""
        results = []
        
        for action_dict in actions:
            action = BrowserAction(**action_dict)
            try:
                if action.action == "navigate":
                    self.navigate(action.url)
                    results.append({"action": "navigate", "status": "ok", "url": action.url})
                elif action.action == "click":
                    self.click(action.selector)
                    results.append({"action": "click", "status": "ok", "selector": action.selector})
                elif action.action == "fill":
                    self.fill(action.selector, action.text)
                    results.append({"action": "fill", "status": "ok", "selector": action.selector})
                elif action.action == "screenshot":
                    b64 = self.screenshot()
                    results.append({"action": "screenshot", "status": "ok", "base64": b64[:100] + "..."})
                elif action.action == "scroll":
                    self.scroll(amount=action.scroll_amount)
                    results.append({"action": "scroll", "status": "ok"})
                elif action.action == "wait":
                    self.wait(action.wait_ms)
                    results.append({"action": "wait", "status": "ok"})
                else:
                    results.append({"action": action.action, "status": "unknown"})
            except Exception as e:
                results.append({"action": action.action, "status": "error", "error": str(e)})
        
        return {"results": results, "final_url": self.get_url() if self._page else ""}

    # === Utilities ===

    def get_action_history(self) -> List[Dict[str, Any]]:
        """Get action history."""
        return [vars(a) for a in self._action_history]

    def clear_history(self) -> None:
        """Clear action history."""
        self._action_history.clear()

    def close(self) -> None:
        """Close browser and cleanup."""
        if self._context:
            self._context.close()
            self._context = None
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None
        self._page = None

    def __enter__(self) -> "BrowserTool":
        return self

    def __exit__(self, *args) -> None:
        self.close()
