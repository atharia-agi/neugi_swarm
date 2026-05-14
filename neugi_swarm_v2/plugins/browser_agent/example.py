"""
Example usage of the BrowserAgent plugin.
"""
from plugins.browser_agent import BrowserAgent
from neugi_swarm_v2.llm_provider import LLMProvider, OllamaProvider

# Create an LLM provider (example using Ollama)
llm_provider = OllamaProvider(model="llama2")

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