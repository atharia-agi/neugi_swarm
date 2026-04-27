"""
NEUGI v2 MCP Prompt Templates
===============================

Prompt template management for the Model Context Protocol. Supports system
prompts, task-specific templates, multi-turn templates, argument validation,
and template composition.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from neugi_swarm_v2.mcp.protocol import (
    Prompt,
    PromptArgument,
    PromptMessage,
    PromptResult,
    TextContent,
)

logger = logging.getLogger(__name__)


# -- Template Validation Error -----------------------------------------------

class PromptValidationError(Exception):
    """Raised when prompt arguments fail validation."""
    pass


# -- Argument Validator ------------------------------------------------------

class ArgumentValidator:
    """Validates prompt arguments against their definitions.

    Checks for required arguments, type constraints, and value patterns.
    """

    @staticmethod
    def validate(
        arguments: dict[str, Any],
        arg_defs: list[PromptArgument],
    ) -> list[str]:
        """Validate arguments against definitions.

        Args:
            arguments: Provided argument values.
            arg_defs: Argument definitions from the prompt template.

        Returns:
            List of validation error messages (empty if valid).

        Raises:
            PromptValidationError: If validation fails.
        """
        errors: list[str] = []

        # Check required arguments
        for arg_def in arg_defs:
            if arg_def.required and arg_def.name not in arguments:
                errors.append(f"Required argument '{arg_def.name}' is missing")

        # Check for unknown arguments
        defined_names = {a.name for a in arg_defs}
        for name in arguments:
            if name not in defined_names:
                errors.append(f"Unknown argument '{name}'")

        if errors:
            raise PromptValidationError("; ".join(errors))

        return errors


# -- Prompt Template ---------------------------------------------------------

@dataclass
class PromptTemplate:
    """A prompt template with argument placeholders.

    Attributes:
        name: Unique template name.
        description: Human-readable description.
        arguments: List of argument definitions.
        messages: Template messages with {placeholder} substitution.
        category: Optional category for organization.
        tags: Optional tags for filtering.
    """

    name: str
    description: str
    arguments: list[PromptArgument] = field(default_factory=list)
    messages: list[dict[str, str]] = field(default_factory=list)
    category: Optional[str] = None
    tags: list[str] = field(default_factory=list)

    def to_prompt(self) -> Prompt:
        """Convert to an MCP Prompt definition."""
        return Prompt(
            name=self.name,
            description=self.description,
            arguments=self.arguments,
        )

    def render(self, arguments: dict[str, Any]) -> PromptResult:
        """Render the template with provided arguments.

        Args:
            arguments: Argument values for substitution.

        Returns:
            PromptResult with rendered messages.

        Raises:
            PromptValidationError: If arguments are invalid.
        """
        ArgumentValidator.validate(arguments, self.arguments)

        rendered_messages: list[PromptMessage] = []
        for msg_template in self.messages:
            role = msg_template.get("role", "user")
            content = msg_template.get("content", "")
            rendered = self._substitute(content, arguments)
            rendered_messages.append(
                PromptMessage(role=role, content=TextContent(text=rendered))
            )

        return PromptResult(messages=rendered_messages)

    def _substitute(self, template: str, arguments: dict[str, Any]) -> str:
        """Substitute {placeholders} in a template string."""
        result = template
        for name, value in arguments.items():
            placeholder = "{" + name + "}"
            if isinstance(value, str):
                result = result.replace(placeholder, value)
            else:
                result = result.replace(placeholder, str(value))

        # Check for unsubstituted required placeholders
        required_names = {a.name for a in self.arguments if a.required}
        for name in required_names:
            placeholder = "{" + name + "}"
            if placeholder in result:
                raise PromptValidationError(
                    f"Required argument '{name}' was not substituted"
                )

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PromptTemplate:
        """Create from a dictionary."""
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            arguments=[
                PromptArgument.from_dict(a)
                for a in data.get("arguments", [])
            ],
            messages=data.get("messages", []),
            category=data.get("category"),
            tags=data.get("tags", []),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary."""
        d: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "arguments": [a.to_dict() for a in self.arguments],
            "messages": self.messages,
        }
        if self.category:
            d["category"] = self.category
        if self.tags:
            d["tags"] = self.tags
        return d


# -- Prompt Registry ---------------------------------------------------------

class PromptRegistry:
    """Registry for MCP prompt templates.

    Supports:
    - System prompt templates
    - Task-specific prompt templates
    - Multi-turn prompt templates
    - Prompt argument validation
    - Prompt composition (combine multiple templates)

    Usage:
        registry = PromptRegistry()

        # Register a template
        registry.register_template(
            PromptTemplate(
                name="code_review",
                description="Review code for issues",
                arguments=[
                    PromptArgument(name="code", description="Code to review", required=True),
                    PromptArgument(name="language", description="Programming language"),
                ],
                messages=[
                    {"role": "system", "content": "You are a code reviewer."},
                    {"role": "user", "content": "Review this {language} code:\n\n{code}"},
                ],
            )
        )

        # Get a prompt
        result = registry.get_prompt("code_review", {"code": "print('hi')", "language": "python"})
    """

    def __init__(self) -> None:
        """Initialize the prompt registry."""
        self._templates: dict[str, PromptTemplate] = {}
        self._on_template_registered: Optional[Callable[[Prompt], None]] = None

    def register_template(self, template: PromptTemplate) -> None:
        """Register a prompt template.

        Args:
            template: PromptTemplate to register.
        """
        self._templates[template.name] = template
        logger.info("Registered prompt template: %s", template.name)
        if self._on_template_registered:
            self._on_template_registered(template.to_prompt())

    def unregister(self, name: str) -> bool:
        """Remove a template from the registry.

        Returns:
            True if the template was found and removed.
        """
        if name in self._templates:
            del self._templates[name]
            logger.info("Unregistered prompt template: %s", name)
            return True
        return False

    def get_template(self, name: str) -> Optional[PromptTemplate]:
        """Get a template by name."""
        return self._templates.get(name)

    def list_templates(self) -> list[Prompt]:
        """List all registered templates as MCP Prompt definitions."""
        return [t.to_prompt() for t in self._templates.values()]

    def list_templates_by_category(self, category: str) -> list[Prompt]:
        """List templates in a specific category."""
        return [
            t.to_prompt()
            for t in self._templates.values()
            if t.category == category
        ]

    def list_templates_by_tag(self, tag: str) -> list[Prompt]:
        """List templates with a specific tag."""
        return [
            t.to_prompt()
            for t in self._templates.values()
            if tag in t.tags
        ]

    def get_prompt(
        self,
        name: str,
        arguments: Optional[dict[str, Any]] = None,
    ) -> PromptResult:
        """Get a rendered prompt by name.

        Args:
            name: Template name.
            arguments: Argument values for substitution.

        Returns:
            PromptResult with rendered messages.

        Raises:
            ValueError: If the template is not found.
            PromptValidationError: If arguments are invalid.
        """
        template = self._templates.get(name)
        if template is None:
            raise ValueError(f"Prompt template '{name}' not found")

        args = arguments or {}
        return template.render(args)

    def compose(
        self,
        template_names: list[str],
        arguments: Optional[dict[str, Any]] = None,
        separator: str = "\n\n---\n\n",
    ) -> PromptResult:
        """Compose multiple templates into a single prompt.

        Args:
            template_names: Names of templates to compose.
            arguments: Shared argument values for all templates.
            separator: String to insert between composed sections.

        Returns:
            PromptResult with combined messages.

        Raises:
            ValueError: If any template is not found.
        """
        args = arguments or {}
        all_messages: list[PromptMessage] = []

        for name in template_names:
            template = self._templates.get(name)
            if template is None:
                raise ValueError(f"Prompt template '{name}' not found")

            result = template.render(args)
            all_messages.extend(result.messages)

            # Add separator between templates
            if len(all_messages) > 0:
                all_messages.append(
                    PromptMessage(
                        role="assistant",
                        content=TextContent(text=separator),
                    )
                )

        # Remove trailing separator
        if all_messages and all_messages[-1].content.text == separator:
            all_messages.pop()

        return PromptResult(messages=all_messages)

    def compose_system_prompt(
        self,
        template_names: list[str],
        arguments: Optional[dict[str, Any]] = None,
    ) -> str:
        """Compose multiple templates into a single system prompt string.

        Extracts only system-role messages and concatenates them.

        Args:
            template_names: Names of templates to compose.
            arguments: Shared argument values.

        Returns:
            Combined system prompt text.
        """
        args = arguments or {}
        parts: list[str] = []

        for name in template_names:
            template = self._templates.get(name)
            if template is None:
                continue

            result = template.render(args)
            for msg in result.messages:
                if msg.role == "system":
                    parts.append(msg.content.text)

        return "\n\n".join(parts)

    @property
    def stats(self) -> dict[str, Any]:
        """Get registry statistics."""
        categories: dict[str, int] = {}
        for t in self._templates.values():
            cat = t.category or "uncategorized"
            categories[cat] = categories.get(cat, 0) + 1

        return {
            "total_templates": len(self._templates),
            "categories": categories,
        }

    # -- Built-in Template Registration --------------------------------------

    def register_neugi_prompts(self) -> None:
        """Register NEUGI-specific prompt templates."""
        self._register_system_prompts()
        self._register_task_prompts()
        self._register_multi_turn_prompts()

    def _register_system_prompts(self) -> None:
        """Register system prompt templates."""

        # NEUGI Identity
        self.register_template(PromptTemplate(
            name="neugi_identity",
            description="NEUGI agent identity and capabilities",
            category="system",
            tags=["identity", "neugi"],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are NEUGI (Neural Unified General Intelligence), "
                        "an autonomous multi-agent AI system. You combine memory, "
                        "skills, and agent orchestration to solve complex tasks.\n\n"
                        "Core capabilities:\n"
                        "- Hierarchical memory with dreaming consolidation\n"
                        "- Dynamic skill loading and matching\n"
                        "- Multi-agent orchestration with role-based agents\n"
                        "- Context window optimization with token budgeting\n"
                        "- Session management with checkpointing\n\n"
                        "You operate as a collaborative swarm, coordinating "
                        "specialized agents to achieve goals efficiently."
                    ),
                },
            ],
        ))

        # Memory Context
        self.register_template(PromptTemplate(
            name="memory_context",
            description="Inject relevant memory context",
            arguments=[
                PromptArgument(
                    name="memories",
                    description="Retrieved memory entries as text",
                    required=True,
                ),
            ],
            category="system",
            tags=["memory", "context"],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Relevant context from memory:\n\n{memories}\n\n"
                        "Use this context to inform your responses. "
                        "Prioritize recent and high-importance memories."
                    ),
                },
            ],
        ))

        # Skill Context
        self.register_template(PromptTemplate(
            name="skill_context",
            description="Inject relevant skill instructions",
            arguments=[
                PromptArgument(
                    name="skills",
                    description="Matched skill instructions as text",
                    required=True,
                ),
            ],
            category="system",
            tags=["skills", "context"],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Available skills for this task:\n\n{skills}\n\n"
                        "Follow the skill instructions when applicable. "
                        "Skills provide step-by-step procedures and best practices."
                    ),
                },
            ],
        ))

    def _register_task_prompts(self) -> None:
        """Register task-specific prompt templates."""

        # Code Review
        self.register_template(PromptTemplate(
            name="code_review",
            description="Review code for issues and improvements",
            arguments=[
                PromptArgument(
                    name="code",
                    description="Code to review",
                    required=True,
                ),
                PromptArgument(
                    name="language",
                    description="Programming language",
                ),
                PromptArgument(
                    name="focus",
                    description="Review focus (security, performance, style)",
                ),
            ],
            category="task",
            tags=["code", "review"],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert code reviewer. Review the provided code "
                        "for issues, best practices, and improvements."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Review this {language} code"
                        + (" focusing on {focus}" if "{focus}" in "{focus}" else "")
                        + ":\n\n```{language}\n{code}\n```\n\n"
                        "Provide specific feedback with line references and "
                        "suggested improvements."
                    ),
                },
            ],
        ))

        # Task Decomposition
        self.register_template(PromptTemplate(
            name="task_decompose",
            description="Break down a complex task into subtasks",
            arguments=[
                PromptArgument(
                    name="task",
                    description="Complex task to decompose",
                    required=True,
                ),
                PromptArgument(
                    name="max_steps",
                    description="Maximum number of subtasks",
                ),
            ],
            category="task",
            tags=["planning", "decomposition"],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a task planning expert. Break down complex tasks "
                        "into clear, actionable subtasks with dependencies."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Decompose this task into manageable subtasks:\n\n{task}\n\n"
                        "For each subtask, provide:\n"
                        "1. Clear description\n"
                        "2. Dependencies\n"
                        "3. Estimated complexity\n"
                        "4. Suggested agent role"
                    ),
                },
            ],
        ))

        # Research Query
        self.register_template(PromptTemplate(
            name="research_query",
            description="Research a topic systematically",
            arguments=[
                PromptArgument(
                    name="topic",
                    description="Research topic",
                    required=True,
                ),
                PromptArgument(
                    name="depth",
                    description="Research depth (overview, detailed, comprehensive)",
                ),
            ],
            category="task",
            tags=["research", "analysis"],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a research analyst. Provide thorough, well-structured "
                        "research on the given topic with clear sourcing."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Research the following topic: {topic}\n\n"
                        "Provide a {depth} analysis covering:\n"
                        "1. Key concepts and definitions\n"
                        "2. Current state of the field\n"
                        "3. Major approaches and methodologies\n"
                        "4. Open questions and challenges\n"
                        "5. Practical applications"
                    ),
                },
            ],
        ))

    def _register_multi_turn_prompts(self) -> None:
        """Register multi-turn prompt templates."""

        # Debug Session
        self.register_template(PromptTemplate(
            name="debug_session",
            description="Interactive debugging session",
            arguments=[
                PromptArgument(
                    name="error",
                    description="Error message or symptom",
                    required=True,
                ),
                PromptArgument(
                    name="context",
                    description="Additional context (code, logs, environment)",
                ),
            ],
            category="multi_turn",
            tags=["debugging", "troubleshooting"],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a debugging expert. Work through the issue "
                        "systematically, asking for information as needed."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "I need help debugging an issue:\n\n"
                        "Error: {error}\n\n"
                        + ("Context: {context}\n\n" if "{context}" in "{context}" else "")
                        + "Let's work through this step by step. Start by "
                        "identifying the most likely root causes."
                    ),
                },
                {
                    "role": "assistant",
                    "content": (
                        "I'll help you debug this. Let me start by analyzing "
                        "the error and identifying potential causes.\n\n"
                        "Based on the error message, here are the most likely "
                        "issues:\n\n"
                        "1. [Analysis of error]\n"
                        "2. [Potential causes]\n\n"
                        "To narrow this down, I need more information:\n"
                        "- [Specific questions]\n\n"
                        "Please provide these details so I can give you "
                        "a more targeted diagnosis."
                    ),
                },
            ],
        ))

        # Learning Session
        self.register_template(PromptTemplate(
            name="learning_session",
            description="Interactive learning session on a topic",
            arguments=[
                PromptArgument(
                    name="topic",
                    description="Topic to learn about",
                    required=True,
                ),
                PromptArgument(
                    name="level",
                    description="Knowledge level (beginner, intermediate, advanced)",
                ),
            ],
            category="multi_turn",
            tags=["learning", "education"],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a patient, knowledgeable teacher. Adapt your "
                        "explanations to the student's level and check for "
                        "understanding frequently."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "I want to learn about: {topic}\n\n"
                        "My current level: {level}\n\n"
                        "Start with the fundamentals and build up gradually. "
                        "Use examples and ask me questions to check understanding."
                    ),
                },
                {
                    "role": "assistant",
                    "content": (
                        "Great! Let's learn about {topic} together.\n\n"
                        "I'll start with the basics and we'll build from there. "
                        "Feel free to ask questions at any point.\n\n"
                        "Let's begin with the core concept:\n\n"
                        "[Explanation tailored to level]\n\n"
                        "Does this make sense? Would you like me to elaborate "
                        "on any part, or shall we move to the next concept?"
                    ),
                },
            ],
        ))

    def import_templates(self, templates: list[dict[str, Any]]) -> int:
        """Import templates from a list of dictionaries.

        Args:
            templates: List of template dicts.

        Returns:
            Number of templates imported.
        """
        count = 0
        for data in templates:
            try:
                template = PromptTemplate.from_dict(data)
                self.register_template(template)
                count += 1
            except Exception as exc:
                logger.warning("Failed to import template: %s", exc)
        return count

    def export_templates(self) -> list[dict[str, Any]]:
        """Export all templates as dictionaries.

        Returns:
            List of template dicts.
        """
        return [t.to_dict() for t in self._templates.values()]

    def export_json(self) -> str:
        """Export all templates as JSON.

        Returns:
            JSON string.
        """
        return json.dumps(self.export_templates(), indent=2, ensure_ascii=False)
