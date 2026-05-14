#!/usr/bin/env python
"""Test the BrowserAgent plugin."""
import sys
from pathlib import Path

# Add the repo root to the sys.path so we can import neugi_swarm_v2 and the plugin
repo_root = Path(__file__).parent
sys.path.insert(0, str(repo_root))

from plugins.browser_agent import BrowserAgent
from neugi_swarm_v2.llm_provider import LLMResponse

class MockLLMProvider:
    """A mock LLM provider that returns a predefined response."""
    def generate(self, prompt):
        # We'll return a response that tells the agent to finish immediately.
        # The agent expects a JSON with thought, action, and action_input.
        # We'll make it finish with a simple answer.
        response_text = (
            '{"thought": "I have completed the goal.", "action": "finish", '
            '"action_input": {"answer": "The goal has been achieved."}}'
        )
        return LLMResponse(text=response_text)

def main():
    print("Creating BrowserAgent with mock LLM provider...")
    agent = BrowserAgent(name="test_browser_agent", llm_provider=MockLLMProvider())
    print("Agent created.")

    print("Running agent with goal: 'Test goal'")
    result = agent.run("Test goal")
    print(f"Agent result: {result.result}")
    print(f"Agent success: {result.success}")

    # Check that the result is as expected
    assert result.success, "Agent should have succeeded"
    assert result.result == "The goal has been achieved.", f"Unexpected result: {result.result}"
    print("Test passed!")

if __name__ == "__main__":
    main()