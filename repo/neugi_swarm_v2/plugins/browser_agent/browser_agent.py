"""
Browser Agent Plugin for NEUGI Swarm v2.
A simple prototype of a browsing agent that can reason and act in a web browser.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from ..agents import TypedAgent, AgentResult
from ..llm_provider import LLMProvider
from ..tools.browser import BrowserTool
from ..tools.tool_executor import ToolExecutor

logger = logging.getLogger(__name__)

# Define the available browser actions that the agent can take
AVAILABLE_ACTIONS = [
    "navigate",
    "click",
    "fill",
    "extract_text",
    "screenshot",
    "get_clickable_elements",
]


class BrowserAgent(TypedAgent):
    """
    A browser agent that uses an LLM to reason about and control a web browser.
    """

    def __init__(
        self,
        name: str = "browser_agent",
        llm_provider: Optional[LLMProvider] = None,
        system_prompt: Optional[str] = None,
        max_steps: int = 10,
        **kwargs,
    ):
        """
        Initialize the browser agent.

        Args:
            name: The name of the agent.
            llm_provider: The LLM provider to use for reasoning.
            system_prompt: The system prompt to use. If None, a default browser agent prompt is used.
            max_steps: Maximum number of steps the agent can take before stopping.
            **kwargs: Additional arguments passed to TypedAgent.
        """
        if system_prompt is None:
            system_prompt = (
                "You are a browser agent. Your goal is to help the user accomplish tasks by controlling a web browser. "
                "You have access to a browser tool that can perform actions like navigate, click, fill, extract text, etc. "
                "You will be given a goal and you must use the browser tool to achieve it. "
                "Think step by step: first, think about what you know and what you need to do. "
                "Then, decide on a single browser action to take. "
                "After executing the action, you will receive an observation. "
                "Repeat until the goal is achieved or you cannot proceed. "
                "When you believe the goal is achieved, clearly state what you have found or accomplished in your final response. "
                "Always format your response as a JSON object with the following keys: "
                "'thought': your reasoning, "
                "'action': the browser action to take (one of: navigate, click, fill, extract_text, screenshot, get_clickable_elements), "
                "'action_input': the input for the action (a JSON object specific to the action). "
                "For example, for navigate: {\"url\": \"https://example.com\"}. "
                "For click: {\"selector\": \"button#submit\"}. "
                "For fill: {\"selector\": \"#input\", \"text\": \"hello\"}. "
                "For extract_text: {\"selector\": \"#content\"} (optional, if not provided extracts all visible text). "
                "For screenshot: {} (no input). "
                "For get_clickable_elements: {} (no input). "
                "If you want to finish, set action to \"finish\" and provide a thought and a final answer in action_input as {\"answer\": \"your final answer\"}. "
                "Do not perform any action that could be harmful or illegal. "
                "Only interact with web pages in a safe and respectful manner."
            )

        # By default, the browser agent has access to no tools because we will handle the browser tool internally.
        # However, we can still allow the user to add other tools if they wish.
        super().__init__(
            name=name,
            llm_provider=llm_provider,
            system_prompt=system_prompt,
            tools=[],  # We handle the browser tool internally
            **kwargs,
        )

        self.max_steps = max_steps
        self.browser_tool = BrowserTool()
        self.tool_executor = ToolExecutor()

    def _execute_browser_action(self, action: str, action_input: Dict[str, Any]) -> Any:
        """
        Execute a browser action using the BrowserTool.

        Args:
            action: The browser action to perform.
            action_input: The input for the action.

        Returns:
            The result of the action.
        """
        logger.info(f"Executing browser action: {action} with input: {action_input}")
        try:
            if action == "navigate":
                return self.browser_tool.navigate(**action_input)
            elif action == "click":
                return self.browser_tool.click(**action_input)
            elif action == "fill":
                return self.browser_tool.fill(**action_input)
            elif action == "extract_text":
                # If selector is not provided, extract all visible text
                if "selector" in action_input:
                    return self.browser_tool.extract_text(**action_input)
                else:
                    return self.browser_tool.extract_text()
            elif action == "screenshot":
                return self.browser_tool.screenshot()
            elif action == "get_clickable_elements":
                return self.browser_tool.get_clickable_elements()
            elif action == "finish":
                # This is a special action that signals the agent to stop
                return action_input
            else:
                raise ValueError(f"Unknown browser action: {action}")
        except Exception as e:
            logger.error(f"Error executing browser action {action}: {e}")
            return {"error": str(e)}

    def _format_observation(self, observation: Any) -> str:
        """
        Format the observation from the browser tool into a string for the LLM.

        Args:
            observation: The raw observation from the browser tool.

        Returns:
            A string representation of the observation.
        """
        if isinstance(observation, dict) and "error" in observation:
            return f"Error: {observation['error']}"
        elif isinstance(observation, str):
            # Truncate long strings to avoid overwhelming the LLM
            if len(observation) > 2000:
                return observation[:2000] + "... [truncated]"
            return observation
        else:
            # For other types (like lists, dicts), convert to JSON string
            try:
                obs_str = json.dumps(observation, indent=2)
                if len(obs_str) > 2000:
                    return obs_str[:2000] + "... [truncated]"
                return obs_str
            except Exception:
                return str(observation)

    def _call_llm(self, prompt: str) -> str:
        """
        Call the LLM to get a response.

        Args:
            prompt: The prompt to send to the LLM.

        Returns:
            The LLM's response as a string.
        """
        if self.llm_provider is None:
            raise ValueError("LLM provider is not set for the agent.")
        # Use the LLM provider to generate a response
        response = self.llm_provider.generate(prompt)
        return response.text

    def run(self, goal: str) -> AgentResult:
        """
        Run the browser agent to achieve the given goal.

        Args:
            goal: The goal that the agent should try to achieve.

        Returns:
            An AgentResult containing the outcome.
        """
        logger.info(f"Browser agent starting with goal: {goal}")
        thoughts: List[str] = []
        actions: List[Dict[str, Any]] = []
        observations: List[Any] = []

        # Initial prompt to the LLM
        prompt = (
            f"You are a browser agent. Your goal is: {goal}\n"
            "You will now start interacting with the browser to achieve this goal. "
            "Think about what you need to do first. "
            "Remember to output your response as a JSON object with keys: thought, action, action_input. "
            "Do not include any other text in your response."
        )

        for step in range(self.max_steps):
            logger.info(f"Browser agent step {step + 1}/{self.max_steps}")
            # Get the LLM's decision
            try:
                llm_response = self._call_llm(prompt)
                logger.debug(f"LLM response: {llm_response}")
                # Parse the JSON response
                # We expect the response to be a JSON object, but it might be wrapped in markdown or have extra text.
                # Try to extract JSON from the response.
                import re
                json_match = re.search(r"\{.*\}", llm_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    decision = json.loads(json_str)
                else:
                    # If no JSON found, treat the whole response as a thought and finish
                    decision = {
                        "thought": llm_response,
                        "action": "finish",
                        "action_input": {"answer": llm_response},
                    }

                thought = decision.get("thought", "")
                action = decision.get("action", "")
                action_input = decision.get("action_input", {})

                # Validate action
                if action not in AVAILABLE_ACTIONS and action != "finish":
                    logger.warning(f"Invalid action '{action}' chosen by LLM. Defaulting to finish.")
                    action = "finish"
                    action_input = {"answer": f"I encountered an error: the action '{action}' is not valid. I will stop here."}

                thoughts.append(thought)
                actions.append({"action": action, "action_input": action_input})

                # Execute the action
                observation = self._execute_browser_action(action, action_input)
                observations.append(observation)

                # If the action is finish, break the loop
                if action == "finish":
                    logger.info("Browser agent finished.")
                    break

                # Prepare the observation for the LLM
                obs_str = self._format_observation(observation)

                # Build the prompt for the next step
                prompt = (
                    f"You are a browser agent. Your goal is: {goal}\n"
                    f"You have taken {step + 1} actions so far. "
                    f"Your last thought was: {thought}\n"
                    f"You took the action: {action} with input: {json.dumps(action_input)}\n"
                    f"You observed: {obs_str}\n"
                    "Based on this observation, think about what you know now and what you need to do next to achieve the goal. "
                    "If you believe the goal is achieved, set action to 'finish' and provide your final answer in action_input. "
                    "Otherwise, decide on the next browser action to take. "
                    "Remember to output your response as a JSON object with keys: thought, action, action_input. "
                    "Do not include any other text in your response."
                )

            except Exception as e:
                logger.error(f"Error in browser agent step {step}: {e}")
                # If there's an error, we try to finish with what we have
                thoughts.append(f"Error occurred: {e}")
                actions.append({"action": "finish", "action_input": {"answer": f"An error occurred: {e}"})
                observations.append({"error": str(e)})
                break

        # If we exited the loop without finishing, we add a finish action
        if actions[-1].get("action") != "finish":
            thoughts.append("Reached maximum steps.")
            actions.append({"action": "finish", "action_input": {"answer": "I reached the maximum number of steps without achieving the goal."}})
            observations.append({"info": "max_steps_reached"})

        # Compile the final result
        final_answer = ""
        for action in reversed(actions):
            if action.get("action") == "finish":
                final_answer = action.get("action_input", {}).get("answer", "")
                break

        if not final_answer:
            final_answer = "I was unable to determine a final answer."

        # We could also return the full trace, but for now we just return the answer.
        return AgentResult(
            agent=self.name,
            success=True,
            result=final_answer,
            metadata={
                "thoughts": thoughts,
                "actions": actions,
                "observations": observations,
            }
        )