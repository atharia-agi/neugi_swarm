"""
Browser Agent for NEUGI Swarm v2.
A specialized agent that can control a web browser to accomplish tasks.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

# Add the neugi_swarm_v2 directory to the sys.path so we can import from agents and llm_provider
sys.path.append(str(Path(__file__).parent.parent.parent))

from agents import TypedAgent
from llm_provider import LLMProvider


class BrowserAgent(TypedAgent):
    """
    An agent that uses a language model to control a web browser.
    """

    def __init__(
        self,
        name: str = "browser_agent",
        llm_provider: Optional[LLMProvider] = None,
        system_prompt: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize the browser agent.

        Args:
            name: The name of the agent.
            llm_provider: The LLM provider to use for reasoning.
            system_prompt: The system prompt to use. If None, a default browser agent prompt is used.
            **kwargs: Additional arguments passed to TypedAgent.
        """
        if system_prompt is None:
            system_prompt = (
                "You are a browser agent. Your goal is to help the user accomplish tasks by controlling a web browser. "
                "You have access to a browser tool that can navigate, click, fill, extract text, take screenshots, etc. "
                "Use the browser tool to interact with web pages and achieve the user's goal. "
                "Always think about what you want to do next based on the current page content and the user's goal. "
                "If you are unsure, you can ask for clarification or try to explore the page to gather more information. "
                "When you believe the goal is achieved, clearly state what you have found or accomplished."
            )

        # By default, the browser agent has access to the browser and web search tools.
        # The user can override this by passing a 'tools' argument in kwargs.
        if "tools" not in kwargs:
            kwargs["tools"] = ["browser", "web_search"]

        super().__init__(
            name=name,
            llm_provider=llm_provider,
            system_prompt=system_prompt,
            **kwargs,
        )