"""
Example usage of the BrowserAgent plugin.
"""
from __future__ import annotations

from plugins.browser_agent import BrowserAgent

from neugi_swarm_v2.llm_provider import OllamaProvider, ProviderConfig, ProviderType


def main() -> None:
    """Run the browser agent example."""
    # Create an LLM provider (example using Ollama)
    config = ProviderConfig(
        provider_type=ProviderType.OLLAMA,
        base_url="http://localhost:11434",
        default_model="llama2",
    )
    llm_provider = OllamaProvider(config)

    # Create the browser agent
    agent = BrowserAgent(
        name="web_researcher",
        llm_provider=llm_provider,
        max_steps=5
    )

    # Define a goal
    goal = "What is the latest news about AI agents?"

    # Run the agent
    result = agent.run(goal)

    print("Agent result:")
    print(result.result)


if __name__ == "__main__":
    main()
