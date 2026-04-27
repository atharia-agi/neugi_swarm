"""
Computer Use Subsystem for NEUGI v2
=====================================
Vision-guided computer/browser automation inspired by Claude Computer Use.

Features:
    - Screenshot → Vision Model → Action Loop
    - DOM state grounding for precise actions
    - Action validation and retry
    - Task decomposition for complex workflows
    - Safety guards for destructive actions

Usage:
    from computer_use.controller import ComputerUseController
    
    controller = ComputerUseController()
    result = controller.execute_task(
        "Go to github.com and search for 'neugi swarm'",
        max_steps=10
    )
"""

from __future__ import annotations

import base64
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Callable

from tools.browser import BrowserTool, BrowserConfig, BrowserAction

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    """Types of computer actions."""
    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    TYPE = "type"
    SCROLL = "scroll"
    SCREENSHOT = "screenshot"
    WAIT = "wait"
    KEYPRESS = "keypress"
    HOVER = "hover"
    SELECT = "select"
    DRAG = "drag"
    TERMINATE = "terminate"


@dataclass
class ComputerAction:
    """A structured computer action."""
    action: ActionType
    selector: str = ""
    text: str = ""
    url: str = ""
    coordinates: Optional[Tuple[int, int]] = None
    key: str = ""
    reason: str = ""  # Why this action was chosen


@dataclass
class StepResult:
    """Result of a single step."""
    step: int
    action: ComputerAction
    screenshot_b64: str = ""
    dom_state: List[Dict] = field(default_factory=list)
    success: bool = True
    error: str = ""
    observation: str = ""  # What the agent observed


@dataclass
class TaskResult:
    """Final result of a computer use task."""
    task: str
    success: bool
    steps: List[StepResult]
    final_screenshot: str = ""
    final_url: str = ""
    extracted_data: Dict[str, Any] = field(default_factory=dict)
    total_time_seconds: float = 0.0


class ComputerUseConfig:
    """Configuration for Computer Use."""
    max_steps: int = 20
    screenshot_interval: int = 1  # Every N steps
    wait_after_action_ms: int = 500
    safety_check: bool = True
    destructive_actions_require_confirm: bool = True
    vision_model: str = "claude-3-5-sonnet-20241022"  # or local equivalent
    action_retry_attempts: int = 2


class ComputerUseController:
    """
    Vision-guided computer automation controller.
    
    Implements the core loop:
        1. Screenshot current state
        2. Send to vision model (or local equivalent)
        3. Parse action
        4. Execute action
        5. Validate result
        6. Repeat until task complete
    """

    def __init__(self, config: Optional[ComputerUseConfig] = None):
        self.config = config or ComputerUseConfig()
        self.browser = BrowserTool(BrowserConfig(headless=True))
        self._step_count = 0
        self._action_history: List[ComputerAction] = []
        self._safety_checker = SafetyChecker()

    def execute_task(
        self,
        task: str,
        max_steps: Optional[int] = None,
        starting_url: str = "",
        callback: Optional[Callable[[StepResult], None]] = None
    ) -> TaskResult:
        """
        Execute a computer use task.
        
        Args:
            task: Natural language description of the task
            max_steps: Override max steps from config
            starting_url: Optional URL to start from
            callback: Optional callback for each step
            
        Returns:
            TaskResult with full execution trace
        """
        max_steps = max_steps or self.config.max_steps
        start_time = time.time()
        steps: List[StepResult] = []
        
        try:
            # Initialize browser if starting URL provided
            if starting_url:
                self.browser.navigate(starting_url)
                time.sleep(0.5)
            
            # Main loop
            for step_num in range(1, max_steps + 1):
                self._step_count = step_num
                
                # 1. Capture state
                screenshot = self.browser.screenshot()
                dom_state = self.browser.get_clickable_elements()
                
                # 2. Determine next action
                action = self._determine_action(task, screenshot, dom_state, steps)
                
                if action.action == ActionType.TERMINATE:
                    break
                
                # 3. Safety check
                if self.config.safety_check:
                    safety = self._safety_checker.check(action)
                    if not safety["allowed"]:
                        steps.append(StepResult(
                            step=step_num,
                            action=action,
                            success=False,
                            error=f"Safety check failed: {safety['reason']}"
                        ))
                        break
                
                # 4. Execute action
                step_result = self._execute_action(action, screenshot, dom_state)
                steps.append(step_result)
                
                if callback:
                    callback(step_result)
                
                if not step_result.success:
                    # Retry if possible
                    if step_num < max_steps:
                        retry_result = self._retry_action(action)
                        if retry_result:
                            steps.append(retry_result)
                            if retry_result.success:
                                continue
                    break
                
                # 5. Check if task is complete
                if self._is_task_complete(task, steps):
                    break
                
                time.sleep(self.config.wait_after_action_ms / 1000)
            
            # Final screenshot
            final_screenshot = self.browser.screenshot() if self.browser._page else ""
            
            return TaskResult(
                task=task,
                success=all(s.success for s in steps),
                steps=steps,
                final_screenshot=final_screenshot,
                final_url=self.browser.get_url() if self.browser._page else "",
                total_time_seconds=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"Computer use task failed: {e}")
            return TaskResult(
                task=task,
                success=False,
                steps=steps,
                error=str(e),
                total_time_seconds=time.time() - start_time
            )
        finally:
            self.browser.close()

    def _determine_action(
        self,
        task: str,
        screenshot_b64: str,
        dom_state: List[Dict],
        previous_steps: List[StepResult]
    ) -> ComputerAction:
        """
        Determine next action based on current state.
        
        In production, this calls a vision model. Here we implement
        a rule-based fallback for when no vision model is available.
        """
        # Try vision model first
        try:
            action = self._call_vision_model(task, screenshot_b64, dom_state, previous_steps)
            if action:
                return action
        except Exception as e:
            logger.warning(f"Vision model failed, using rule-based: {e}")
        
        # Rule-based fallback
        return self._rule_based_action(task, dom_state, previous_steps)

    def _call_vision_model(
        self,
        task: str,
        screenshot_b64: str,
        dom_state: List[Dict],
        previous_steps: List[StepResult]
    ) -> Optional[ComputerAction]:
        """Call vision model to determine next action."""
        # This would integrate with your LLM provider
        # For now, return None to trigger rule-based fallback
        # TODO: Integrate with neugi_swarm_v2.llm_provider
        return None

    def _rule_based_action(
        self,
        task: str,
        dom_state: List[Dict],
        previous_steps: List[StepResult]
    ) -> ComputerAction:
        """Rule-based action determination for common tasks."""
        task_lower = task.lower()
        
        # Check if we need to navigate
        current_url = self.browser.get_url() if self.browser._page else ""
        
        if "github" in task_lower and "github" not in current_url:
            return ComputerAction(
                action=ActionType.NAVIGATE,
                url="https://github.com",
                reason="Task requires GitHub, navigating there"
            )
        
        if "google" in task_lower and "google" not in current_url:
            return ComputerAction(
                action=ActionType.NAVIGATE,
                url="https://google.com",
                reason="Task requires Google, navigating there"
            )
        
        # Search for search box
        if any(word in task_lower for word in ["search", "find", "look for"]):
            for el in dom_state:
                if el.get("tag") == "input" and any(
                    hint in (el.get("placeholder", "") + el.get("text", "")).lower()
                    for hint in ["search", "query", "find"]
                ):
                    # Extract search term
                    search_term = task_lower
                    for prefix in ["search for", "find", "look for", "search"]:
                        if prefix in search_term:
                            search_term = search_term.split(prefix, 1)[-1].strip()
                            break
                    
                    return ComputerAction(
                        action=ActionType.FILL,
                        selector=el.get("selector", "input[type='text']"),
                        text=search_term,
                        reason="Found search box, filling with query"
                    )
        
        # Look for buttons to click
        if any(word in task_lower for word in ["click", "press", "submit"]):
            for el in dom_state:
                text = (el.get("text", "") + el.get("placeholder", "")).lower()
                if any(hint in text for hint in ["search", "submit", "go", "find"]):
                    return ComputerAction(
                        action=ActionType.CLICK,
                        selector=el.get("selector", ""),
                        reason="Found action button"
                    )
        
        # Default: screenshot and wait
        if len(previous_steps) > 0 and previous_steps[-1].action.action == ActionType.SCREENSHOT:
            return ComputerAction(
                action=ActionType.TERMINATE,
                reason="No clear action determined, terminating"
            )
        
        return ComputerAction(
            action=ActionType.SCREENSHOT,
            reason="Capturing state to determine next action"
        )

    def _execute_action(
        self,
        action: ComputerAction,
        screenshot: str,
        dom_state: List[Dict]
    ) -> StepResult:
        """Execute a single action."""
        try:
            if action.action == ActionType.NAVIGATE:
                self.browser.navigate(action.url)
                observation = f"Navigated to {action.url}"
                
            elif action.action == ActionType.CLICK:
                self.browser.click(action.selector)
                observation = f"Clicked {action.selector}"
                
            elif action.action == ActionType.FILL:
                self.browser.fill(action.selector, action.text)
                observation = f"Filled {action.selector} with '{action.text}'"
                
            elif action.action == ActionType.TYPE:
                self.browser.type_text(action.selector, action.text)
                observation = f"Typed into {action.selector}"
                
            elif action.action == ActionType.SCROLL:
                self.browser.scroll(amount=action.coordinates[1] if action.coordinates else 500)
                observation = "Scrolled page"
                
            elif action.action == ActionType.SCREENSHOT:
                observation = "Captured screenshot"
                
            elif action.action == ActionType.WAIT:
                time.sleep(1)
                observation = "Waited"
                
            elif action.action == ActionType.KEYPRESS:
                # Keypress via page.keyboard
                if self.browser._page:
                    self.browser._page.keyboard.press(action.key)
                observation = f"Pressed key {action.key}"
                
            elif action.action == ActionType.HOVER:
                if self.browser._page:
                    self.browser._page.hover(action.selector)
                observation = f"Hovered over {action.selector}"
                
            elif action.action == ActionType.TERMINATE:
                observation = "Task terminated"
                
            else:
                observation = f"Unknown action: {action.action}"
            
            self._action_history.append(action)
            
            return StepResult(
                step=self._step_count,
                action=action,
                screenshot_b64=screenshot,
                dom_state=dom_state,
                success=True,
                observation=observation
            )
            
        except Exception as e:
            return StepResult(
                step=self._step_count,
                action=action,
                screenshot_b64=screenshot,
                dom_state=dom_state,
                success=False,
                error=str(e),
                observation=f"Failed to execute {action.action}: {e}"
            )

    def _retry_action(self, action: ComputerAction) -> Optional[StepResult]:
        """Retry a failed action with modifications."""
        logger.info(f"Retrying action: {action.action}")
        time.sleep(1)
        
        # Try with alternative selector strategies
        if action.selector and action.action in [ActionType.CLICK, ActionType.FILL]:
            # Get fresh DOM state
            dom_state = self.browser.get_clickable_elements()
            
            # Try finding by text content
            for el in dom_state:
                if action.text and action.text.lower() in el.get("text", "").lower():
                    action.selector = el.get("selector", action.selector)
                    break
        
        try:
            return self._execute_action(action, self.browser.screenshot(), [])
        except Exception as e:
            logger.error(f"Retry failed: {e}")
            return None

    def _is_task_complete(self, task: str, steps: List[StepResult]) -> bool:
        """Check if task appears to be complete."""
        if len(steps) < 2:
            return False
        
        # Check for completion indicators
        recent_actions = [s.action.action for s in steps[-3:]]
        
        # If we've been screenshotting without progress, we might be done
        if all(a == ActionType.SCREENSHOT for a in recent_actions):
            return True
        
        # If last action was terminate
        if steps[-1].action.action == ActionType.TERMINATE:
            return True
        
        # Check if URL contains expected result
        current_url = self.browser.get_url() if self.browser._page else ""
        task_keywords = task.lower().split()
        url_match = sum(1 for kw in task_keywords if len(kw) > 3 and kw in current_url.lower())
        if url_match >= 2:
            return True
        
        return False

    def get_history(self) -> List[Dict[str, Any]]:
        """Get full action history."""
        return [
            {
                "action": a.action.value,
                "selector": a.selector,
                "text": a.text,
                "url": a.url,
                "reason": a.reason
            }
            for a in self._action_history
        ]

    def reset(self) -> None:
        """Reset controller state."""
        self._step_count = 0
        self._action_history.clear()
        self.browser.close()
        self.browser = BrowserTool(BrowserConfig(headless=True))


class SafetyChecker:
    """Safety checks for computer use actions."""

    DESTRUCTIVE_KEYWORDS = [
        "delete", "remove", "drop", "truncate", "rm -rf",
        "format", "wipe", "destroy", "uninstall"
    ]

    SENSITIVE_URLS = [
        "bank", "paypal", "stripe", "account", "wallet",
        "login", "signin", "password", "credential"
    ]

    def check(self, action: ComputerAction) -> Dict[str, Any]:
        """Check if action is safe."""
        # Check for destructive text
        if action.text:
            text_lower = action.text.lower()
            for keyword in self.DESTRUCTIVE_KEYWORDS:
                if keyword in text_lower:
                    return {
                        "allowed": False,
                        "reason": f"Potentially destructive text detected: '{keyword}'"
                    }
        
        # Check for sensitive URLs
        if action.url:
            url_lower = action.url.lower()
            for sensitive in self.SENSITIVE_URLS:
                if sensitive in url_lower:
                    return {
                        "allowed": True,
                        "warning": f"Navigating to potentially sensitive site: {sensitive}"
                    }
        
        return {"allowed": True, "reason": "Action appears safe"}
