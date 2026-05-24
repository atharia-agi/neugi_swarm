"""
MCP Prompt Manager - Manages prompt template registration and retrieval
========================================================================
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from neugi_swarm_v2.mcp.messages import ListPromptsResult

logger = logging.getLogger(__name__)


@dataclass
class PromptTemplate:
    """Represents a registered MCP prompt template."""
    name: str
    description: str
    template: str
    input_variables: list[str] = field(default_factory=list)
    metadata: dict[str, Any] | None = None


class PromptManager:
    """Manages prompt templates for MCP clients."""

    def __init__(self) -> None:
        self._prompts: dict[str, PromptTemplate] = {}
        self._default_prompts_installed = False

    def register(self, template: PromptTemplate) -> None:
        """Register a prompt template."""
        self._prompts[template.name] = template
        logger.debug("Registered MCP prompt: %s", template.name)

    def register_prompt(
        self,
        name: str,
        description: str,
        template: str,
        input_variables: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PromptTemplate:
        """Convenience method to register a prompt template."""
        pt = PromptTemplate(
            name=name,
            description=description,
            template=template,
            input_variables=input_variables or [],
            metadata=metadata,
        )
        self.register(pt)
        return pt

    def get_prompt(self, name: str, arguments: dict | None = None) -> PromptTemplate | None:
        """Get a prompt template by name."""
        return self._prompts.get(name)

    def render_prompt(self, name: str, arguments: dict | None = None) -> str:
        """Render a prompt template with given arguments."""
        template = self.get_prompt(name)
        if template is None:
            raise ValueError(f"Prompt template not found: {name}")

        result = template.template
        if arguments:
            for var in template.input_variables:
                if var in arguments:
                    result = result.replace(f"{{{var}}}", str(arguments[var]))
        return result

    def list_prompts(self) -> ListPromptsResult:
        """List all registered prompt templates."""
        prompts = [
            {
                "name": pt.name,
                "description": pt.description,
                "inputVariables": [
                    {"name": v} for v in pt.input_variables
                ] if pt.input_variables else None,
                "metadata": pt.metadata,
            }
            for pt in self._prompts.values()
        ]
        return ListPromptsResult(prompts=prompts)

    def list_prompt_templates(self) -> list[dict]:
        """List all prompt templates as dicts."""
        return [
            {
                "name": pt.name,
                "description": pt.description,
                "template": pt.template,
                "input_variables": pt.input_variables,
                "metadata": pt.metadata,
            }
            for pt in self._prompts.values()
        ]

    def install_default_prompts(self, swarm: Any = None) -> None:
        """Install default NEUGI prompt templates."""
        defaults = [
            self.register_prompt(
                name="neugi-system-check",
                description="Perform a comprehensive system health check",
                template=(
                    "You are a NEUGI system diagnostic agent. Perform the following checks:\n"
                    "1. Check memory system integrity\n"
                    "2. Verify all plugin dependencies\n"
                    "3. Test sandbox connectivity\n"
                    "4. Validate configuration consistency\n"
                    "5. Check for any pending updates\n"
                    "Report findings in structured JSON with status, severity, and recommendations."
                ),
                input_variables=[],
            ),
            self.register_prompt(
                name="neugi-security-audit",
                description="Conduct a focused security audit on a given target",
                template=(
                    "You are a NEUGI security audit agent. Conduct an audit on: {target}\n"
                    "1. Identify attack surface\n"
                    "2. Check for known vulnerabilities\n"
                    "3. Assess configuration weaknesses\n"
                    "4. Evaluate access controls\n"
                    "5. Prioritize findings by risk level\n"
                    "Output a structured report with severity ratings and remediation steps."
                ),
                input_variables=["target"],
            ),
            self.register_prompt(
                name="neugi-code-review",
                description="Review code for bugs, security issues, and best practices",
                template=(
                    "You are a NEUGI code review agent. Review the following code:\n"
                    "```\n{code}\n```\n"
                    "1. Identify bugs and potential runtime errors\n"
                    "2. Check for security vulnerabilities (injection, auth bypass, etc.)\n"
                    "3. Evaluate code quality and adherence to standards\n"
                    "4. Suggest improvements with specific line references\n"
                    "5. Rate overall quality on a 1-10 scale\n"
                    "Output findings in a structured format."
                ),
                input_variables=["code"],
            ),
            self.register_prompt(
                name="neugi-research",
                description="Conduct in-depth research on a topic",
                template=(
                    "You are a NEUGI research agent. Research the following topic:\n"
                    "Topic: {topic}\n"
                    "1. Gather information from multiple perspectives\n"
                    "2. Identify key facts, figures, and trends\n"
                    "3. Analyze strengths and weaknesses\n"
                    "4. Compare with alternatives\n"
                    "5. Provide a balanced summary with citations\n"
                    "Depth: {depth}\n"
                    "Format: {format}"
                ),
                input_variables=["topic", "depth", "format"],
            ),
            self.register_prompt(
                name="neugi-task-plan",
                description="Break down a complex task into actionable steps",
                template=(
                    "You are a NEUGI planning agent. Break down this task:\n"
                    "Goal: {goal}\n"
                    "1. Define the end state clearly\n"
                    "2. Decompose into sub-tasks\n"
                    "3. Identify dependencies between tasks\n"
                    "4. Estimate effort and priority for each task\n"
                    "5. Create a sequential or parallel execution plan\n"
                    "6. Identify potential risks and mitigations\n"
                    "Constraints: {constraints}\n"
                    "Resources: {resources}"
                ),
                input_variables=["goal", "constraints", "resources"],
            ),
            self.register_prompt(
                name="neugi-decision-framework",
                description="Apply structured decision-making framework",
                template=(
                    "You are a NEUGI decision analysis agent. Help evaluate:\n"
                    "Decision: {decision}\n"
                    "1. Identify all relevant options\n"
                    "2. Define evaluation criteria (weight each 1-10)\n"
                    "3. Score each option against each criterion\n"
                    "4. Perform sensitivity analysis\n"
                    "5. Recommend the best option with confidence level\n"
                    "6. Identify the reversal point (what would change your mind?)\n"
                    "Context: {context}"
                ),
                input_variables=["decision", "context"],
            ),
        ]
        self._default_prompts_installed = True
        logger.info("Installed %d default NEUGI prompt templates", len(defaults))

    def has_prompt(self, name: str) -> bool:
        """Check if a prompt template exists."""
        return name in self._prompts

    def remove(self, name: str) -> bool:
        """Remove a prompt template by name."""
        if name in self._prompts:
            del self._prompts[name]
            logger.debug("Removed prompt template: %s", name)
            return True
        return False

    def count(self) -> int:
        """Return number of registered prompts."""
        return len(self._prompts)

    def clear(self) -> None:
        """Clear all registered prompts."""
        self._prompts.clear()
        self._default_prompts_installed = False
        logger.debug("Cleared all MCP prompts")
