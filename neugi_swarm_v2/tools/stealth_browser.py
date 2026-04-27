"""
Stealth Browser for NEUGI v2
==============================
Anti-detection browser automation inspired by browser-use.

Features:
    - Fingerprint randomization
    - User-agent rotation
    - WebDriver property hiding
    - Canvas/WebGL noise injection
    - Proxy rotation support
    - Request interception for stealth headers

Usage:
    from tools.stealth_browser import StealthBrowser
    
    browser = StealthBrowser()
    browser.navigate("https://bot-detector.example.com")
    print(browser.stealth_info)
"""

from __future__ import annotations

import json
import logging
import random
import string
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from tools.browser import BrowserTool, BrowserConfig

logger = logging.getLogger(__name__)


# Common user agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# Screen resolutions for variety
SCREEN_RESOLUTIONS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1280, "height": 720},
    {"width": 2560, "height": 1440},
]

# Color depths
COLOR_DEPTHS = [24, 32]

# Timezones
TIMEZONES = [
    "America/New_York",
    "America/Los_Angeles",
    "Europe/London",
    "Europe/Paris",
    "Asia/Tokyo",
    "Asia/Singapore",
    "Australia/Sydney",
]

# Languages
LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9",
    "en-US,en;q=0.9,fr;q=0.8",
    "ja-JP,ja;q=0.9,en;q=0.8",
    "de-DE,de;q=0.9,en;q=0.8",
]


@dataclass
class StealthConfig:
    """Configuration for stealth mode."""
    randomize_user_agent: bool = True
    randomize_viewport: bool = True
    randomize_timezone: bool = True
    randomize_language: bool = True
    hide_webdriver: bool = True
    inject_canvas_noise: bool = True
    inject_webgl_noise: bool = True
    mask_chrome_features: bool = True
    disable_automation_flags: bool = True
    proxy: str = ""
    plugins_length: int = 3


@dataclass
class BrowserFingerprint:
    """Generated browser fingerprint."""
    user_agent: str
    viewport: Dict[str, int]
    color_depth: int
    timezone: str
    language: str
    platform: str
    hardware_concurrency: int
    device_memory: int
    max_touch_points: int
    plugins_length: int
    vendor: str


class StealthBrowser(BrowserTool):
    """Browser with anti-detection stealth capabilities."""
    
    def __init__(self, config: Optional[BrowserConfig] = None, stealth: Optional[StealthConfig] = None):
        super().__init__(config)
        self.stealth_config = stealth or StealthConfig()
        self.fingerprint: Optional[BrowserFingerprint] = None
        self._stealth_scripts: List[str] = []
        self._init_stealth()
    
    def _init_stealth(self) -> None:
        """Initialize stealth settings."""
        self.fingerprint = self._generate_fingerprint()
        self._build_stealth_scripts()
        
        # Apply config overrides based on fingerprint
        if self.stealth_config.randomize_user_agent:
            self.config.user_agent = self.fingerprint.user_agent
        if self.stealth_config.randomize_viewport:
            self.config.viewport_width = self.fingerprint.viewport["width"]
            self.config.viewport_height = self.fingerprint.viewport["height"]
    
    def _generate_fingerprint(self) -> BrowserFingerprint:
        """Generate a realistic browser fingerprint."""
        return BrowserFingerprint(
            user_agent=random.choice(USER_AGENTS),
            viewport=random.choice(SCREEN_RESOLUTIONS),
            color_depth=random.choice(COLOR_DEPTHS),
            timezone=random.choice(TIMEZONES),
            language=random.choice(LANGUAGES),
            platform="Win32" if "Windows" in random.choice(USER_AGENTS) else "MacIntel",
            hardware_concurrency=random.choice([4, 8, 12, 16]),
            device_memory=random.choice([4, 8, 16, 32]),
            max_touch_points=0,  # Desktop
            plugins_length=self.stealth_config.plugins_length,
            vendor="Google Inc." if "Chrome" in random.choice(USER_AGENTS) else "Apple Computer, Inc.",
        )
    
    def _build_stealth_scripts(self) -> None:
        """Build JavaScript scripts to inject for stealth."""
        fp = self.fingerprint
        if not fp:
            return
        
        scripts = []
        
        # 1. Hide webdriver property
        if self.stealth_config.hide_webdriver:
            scripts.append("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
            """)
        
        # 2. Override plugins
        scripts.append(f"""
            Object.defineProperty(navigator, 'plugins', {{
                get: () => {{
                    const plugins = [];
                    for (let i = 0; i < {fp.plugins_length}; i++) {{
                        plugins.push({{
                            name: `Plugin ${{i+1}}`,
                            filename: `plugin${{i+1}}.dll`,
                            description: `Plugin ${{i+1}} description`,
                            version: `1.0.0`,
                            length: 1,
                            item: () => null,
                            namedItem: () => null,
                        }});
                    }}
                    return plugins;
                }},
            }});
        """)
        
        # 3. Override platform
        scripts.append(f"""
            Object.defineProperty(navigator, 'platform', {{
                get: () => '{fp.platform}',
            }});
        """)
        
        # 4. Override hardware concurrency
        scripts.append(f"""
            Object.defineProperty(navigator, 'hardwareConcurrency', {{
                get: () => {fp.hardware_concurrency},
            }});
        """)
        
        # 5. Override device memory
        scripts.append(f"""
            Object.defineProperty(navigator, 'deviceMemory', {{
                get: () => {fp.device_memory},
            }});
        """)
        
        # 6. Override max touch points
        scripts.append(f"""
            Object.defineProperty(navigator, 'maxTouchPoints', {{
                get: () => {fp.max_touch_points},
            }});
        """)
        
        # 7. Override language
        scripts.append(f"""
            Object.defineProperty(navigator, 'language', {{
                get: () => '{fp.language.split(',')[0]}',
            }});
            Object.defineProperty(navigator, 'languages', {{
                get: () => {json.dumps(fp.language.split(','))},
            }});
        """)
        
        # 8. Canvas noise injection
        if self.stealth_config.inject_canvas_noise:
            scripts.append("""
                const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
                CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {
                    const imageData = originalGetImageData.call(this, x, y, w, h);
                    const data = imageData.data;
                    for (let i = 0; i < data.length; i += 4) {
                        data[i] = data[i] + (Math.random() > 0.5 ? 1 : -1);
                    }
                    return imageData;
                };
            """)
        
        # 9. WebGL noise injection
        if self.stealth_config.inject_webgl_noise:
            scripts.append("""
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) {  // UNMASKED_VENDOR_WEBGL
                        return 'Intel Inc.';
                    }
                    if (parameter === 37446) {  // UNMASKED_RENDERER_WEBGL
                        return 'Intel Iris OpenGL Engine';
                    }
                    return getParameter.call(this, parameter);
                };
            """)
        
        # 10. Mask Chrome automation features
        if self.stealth_config.mask_chrome_features:
            scripts.append("""
                window.chrome = {
                    runtime: {},
                    loadTimes: () => ({}),
                    csi: () => ({}),
                    app: {},
                };
            """)
        
        # 11. Permissions API override
        scripts.append("""
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' 
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters)
            );
        """)
        
        self._stealth_scripts = scripts
    
    def _get_page(self):
        """Override to inject stealth scripts after page creation."""
        page = super()._get_page()
        
        # Inject stealth scripts
        if self._stealth_scripts and not hasattr(self, '_stealth_injected'):
            for script in self._stealth_scripts:
                try:
                    page.evaluate(script)
                except Exception as e:
                    logger.warning(f"Stealth script injection failed: {e}")
            self._stealth_injected = True
        
        return page
    
    def navigate(self, url: str) -> "StealthBrowser":
        """Navigate with stealth headers."""
        super().navigate(url)
        
        # Re-inject stealth after navigation
        if self._stealth_scripts:
            for script in self._stealth_scripts:
                try:
                    self._page.evaluate(script)
                except Exception as e:
                    logger.warning(f"Stealth re-injection failed: {e}")
        
        return self
    
    @property
    def stealth_info(self) -> Dict[str, Any]:
        """Get current stealth configuration info."""
        if not self.fingerprint:
            return {}
        
        return {
            "user_agent": self.fingerprint.user_agent,
            "viewport": self.fingerprint.viewport,
            "timezone": self.fingerprint.timezone,
            "language": self.fingerprint.language,
            "platform": self.fingerprint.platform,
            "hardware_concurrency": self.fingerprint.hardware_concurrency,
            "device_memory": self.fingerprint.device_memory,
            "plugins_length": self.fingerprint.plugins_length,
            "scripts_injected": len(self._stealth_scripts),
        }
    
    def detect_bot(self) -> Dict[str, Any]:
        """Run basic bot detection test."""
        page = self._get_page()
        
        detection_script = """
        () => {
            const checks = {
                webdriver: navigator.webdriver === undefined ? 'hidden' : 'detected',
                plugins: navigator.plugins.length > 0 ? 'ok' : 'suspicious',
                languages: navigator.languages ? 'ok' : 'suspicious',
                platform: navigator.platform ? 'ok' : 'suspicious',
                chrome: window.chrome ? 'ok' : 'suspicious',
                notification_permission: 'default',
            };
            
            // Check notification permission
            if (typeof Notification !== 'undefined') {
                checks.notification_permission = Notification.permission;
            }
            
            return checks;
        }
        """
        
        try:
            return page.evaluate(detection_script)
        except Exception as e:
            return {"error": str(e)}
    
    def rotate_fingerprint(self) -> None:
        """Generate a new fingerprint for fresh identity."""
        self.fingerprint = self._generate_fingerprint()
        self._build_stealth_scripts()
        self._init_stealth()
        
        # Close and recreate browser context
        if self._context:
            self._context.close()
            self._context = None
        if self._page:
            self._page = None
        
        logger.info("Fingerprint rotated")


__all__ = [
    "StealthBrowser",
    "StealthConfig",
    "BrowserFingerprint",
    "USER_AGENTS",
    "SCREEN_RESOLUTIONS",
    "TIMEZONES",
    "LANGUAGES",
]
