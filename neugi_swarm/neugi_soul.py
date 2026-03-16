#!/usr/bin/env python3
"""
🤖 NEUGI SOUL SYSTEM
=====================

Based on BrowserOS SOUL.md architecture:
- Defines AI personality, tone, and behavior
- Separated from memory (facts) vs soul (personality)

Version: 1.0
Date: March 15, 2026
"""

import os
import yaml
from typing import Dict, List
from dataclasses import dataclass, field


NEUGI_DIR = os.path.expanduser("~/neugi")
CONFIG_DIR = os.path.join(NEUGI_DIR, "config")
SOUL_FILE = os.path.join(CONFIG_DIR, "SOUL.md")


@dataclass
class Soul:
    """Soul configuration"""

    name: str = "NEUGI"
    version: str = "1.0"
    tone: str = "helpful, direct, technical"
    traits: List[str] = field(default_factory=list)
    boundaries: List[str] = field(default_factory=list)
    response_style: Dict[str, str] = field(default_factory=dict)
    instructions: str = ""


class SoulSystem:
    """
    NEUGI Soul System - Personality Management

    Separates WHAT the AI knows (Memory) from
    HOW the AI behaves (Soul)
    """

    PRESETS = {
        "default": {
            "name": "NEUGI",
            "tone": "helpful, direct, technical",
            "traits": [
                "You provide code examples when helpful",
                "You explain your reasoning step by step",
                "You mention security implications",
                "You are concise but thorough",
            ],
            "boundaries": [
                "Never execute destructive commands without confirmation",
                "Ask before modifying system files",
                "Warn about potential risks",
            ],
            "response_style": {
                "start_with": "summary",
                "code_format": "fenced",
                "end_with": "next_steps",
            },
        },
        "assistant": {
            "name": "Assistant",
            "tone": "friendly, patient, explanatory",
            "traits": [
                "You break down complex topics simply",
                "You ask clarifying questions",
                "You provide examples and analogies",
                "You encourage learning",
            ],
            "boundaries": ["Never make assumptions about user intent", "Respect user privacy"],
            "response_style": {
                "start_with": "acknowledgment",
                "code_format": "inline",
                "end_with": "questions",
            },
        },
        "senior_dev": {
            "name": "Senior Developer",
            "tone": "professional, efficient, pragmatic",
            "traits": [
                "You focus on production-ready solutions",
                "You consider edge cases and error handling",
                "You recommend best practices",
                "You cite documentation when relevant",
            ],
            "boundaries": [
                "Never suggest insecure patterns",
                "Always validate inputs",
                "Consider performance implications",
            ],
            "response_style": {
                "start_with": "approach",
                "code_format": "fenced",
                "end_with": "considerations",
            },
        },
        "debugger": {
            "name": "Bug Hunter",
            "tone": "analytical, thorough, methodical",
            "traits": [
                "You trace issues systematically",
                "You ask for error messages and logs",
                "You propose minimal reproduction steps",
                "You verify fixes",
            ],
            "boundaries": [
                "Never guess without evidence",
                "Always reproduce before declaring fixed",
            ],
            "response_style": {
                "start_with": "question",
                "code_format": "minimal",
                "end_with": "verification",
            },
        },
        "security": {
            "name": "Security Expert",
            "tone": "cautious, thorough, alert",
            "traits": [
                "You flag potential vulnerabilities",
                "You recommend secure defaults",
                "You validate against OWASP",
                "You never log secrets",
            ],
            "boundaries": [
                "Never accept unsafe patterns",
                "Always use parameterized queries",
                "Never hardcode credentials",
            ],
            "response_style": {
                "start_with": "warning",
                "code_format": "fenced",
                "end_with": "security_notes",
            },
        },
    }

    def __init__(self, soul_file: str = None):
        self.soul_file = soul_file or SOUL_FILE
        self.soul = self._load_soul()

    def _ensure_config_dir(self):
        """Ensure config directory exists"""
        os.makedirs(CONFIG_DIR, exist_ok=True)

    def _load_soul(self) -> Soul:
        """Load soul from file or create default"""
        if os.path.exists(self.soul_file):
            try:
                with open(self.soul_file, "r") as f:
                    content = f.read()

                # Parse YAML frontmatter
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        frontmatter = yaml.safe_load(parts[1])
                        instructions = parts[2].strip()

                        return Soul(
                            name=frontmatter.get("name", "NEUGI"),
                            version=frontmatter.get("version", "1.0"),
                            tone=frontmatter.get("tone", "helpful"),
                            traits=frontmatter.get("traits", []),
                            boundaries=frontmatter.get("boundaries", []),
                            response_style=frontmatter.get("response_style", {}),
                            instructions=instructions,
                        )
            except Exception as e:
                print(f"Warning: Failed to load SOUL.md: {e}")

        # Return default soul
        return self._create_default_soul()

    def _create_default_soul(self) -> Soul:
        """Create default soul"""
        default = self.PRESETS["default"]
        return Soul(
            name=default["name"],
            tone=default["tone"],
            traits=default["traits"],
            boundaries=default["boundaries"],
            response_style=default["response_style"],
        )

    def save_soul(self, soul: Soul = None):
        """Save soul to file"""
        soul = soul or self.soul
        self._ensure_config_dir()

        frontmatter = {
            "name": soul.name,
            "version": soul.version,
            "tone": soul.tone,
            "traits": soul.traits,
            "boundaries": soul.boundaries,
            "response_style": soul.response_style,
        }

        content = "---\n"
        content += yaml.dump(frontmatter, default_flow_style=False)
        content += "---\n\n"
        content += soul.instructions

        with open(self.soul_file, "w") as f:
            f.write(content)

    def get_system_prompt(self) -> str:
        """
        Generate system prompt for LLM

        This is injected into the AI's context
        """
        parts = []

        # Identity
        parts.append(f"You are {self.soul.name}.")
        parts.append(f"Tone: {self.soul.tone}")

        # Traits
        if self.soul.traits:
            parts.append("\n# Your Traits")
            for trait in self.soul.traits:
                parts.append(f"- {trait}")

        # Boundaries
        if self.soul.boundaries:
            parts.append("\n# Boundaries")
            for boundary in self.soul.boundaries:
                parts.append(f"- {boundary}")

        # Response style
        style = self.soul.response_style
        if style:
            parts.append("\n# Response Style")
            if style.get("start_with"):
                parts.append(f"- Start responses with: {style['start_with']}")
            if style.get("code_format"):
                parts.append(f"- Code format: {style['code_format']}")
            if style.get("end_with"):
                parts.append(f"- End with: {style['end_with']}")

        # Custom instructions
        if self.soul.instructions:
            parts.append("\n" + self.soul.instructions)

        return "\n".join(parts)

    # ========== PRESET MANAGEMENT ==========

    def list_presets(self) -> List[str]:
        """List available soul presets"""
        return list(self.PRESETS.keys())

    def load_preset(self, preset_name: str) -> bool:
        """Load a preset soul"""
        if preset_name not in self.PRESETS:
            return False

        preset = self.PRESETS[preset_name]
        self.soul = Soul(
            name=preset["name"],
            tone=preset["tone"],
            traits=preset["traits"],
            boundaries=preset["boundaries"],
            response_style=preset["response_style"],
        )
        self.save_soul()
        return True

    def create_custom_soul(
        self,
        name: str,
        tone: str,
        traits: List[str],
        boundaries: List[str] = None,
        instructions: str = "",
    ) -> Soul:
        """Create and save a custom soul"""
        soul = Soul(
            name=name,
            tone=tone,
            traits=traits,
            boundaries=boundaries or [],
            instructions=instructions,
        )
        self.soul = soul
        self.save_soul()
        return soul

    # ========== INTERACTIVE EDITING ==========

    def edit_trait(self, index: int, new_trait: str = None, delete: bool = False):
        """Edit a trait"""
        if delete:
            if 0 <= index < len(self.soul.traits):
                self.soul.traits.pop(index)
        elif new_trait:
            if 0 <= index < len(self.soul.traits):
                self.soul.traits[index] = new_trait
            elif index == len(self.soul.traits):
                self.soul.traits.append(new_trait)

        self.save_soul()

    def edit_boundary(self, index: int, new_boundary: str = None, delete: bool = False):
        """Edit a boundary"""
        if delete:
            if 0 <= index < len(self.soul.boundaries):
                self.soul.boundaries.pop(index)
        elif new_boundary:
            if 0 <= index < len(self.soul.boundaries):
                self.soul.boundaries[index] = new_boundary
            elif index == len(self.soul.boundaries):
                self.soul.boundaries.append(new_boundary)

        self.save_soul()

    # ========== STATUS ==========

    def get_info(self) -> Dict:
        """Get current soul info"""
        return {
            "name": self.soul.name,
            "tone": self.soul.tone,
            "traits_count": len(self.soul.traits),
            "boundaries_count": len(self.soul.boundaries),
            "file": self.soul_file,
            "presets_available": self.list_presets(),
        }

    def display(self):
        """Display current soul configuration"""
        print(f"\n{'=' * 50}")
        print(f"🎭 NEUGI SOUL: {self.soul.name}")
        print(f"{'=' * 50}")
        print(f"\n📝 Tone: {self.soul.tone}")

        print(f"\n✨ Traits ({len(self.soul.traits)}):")
        for i, trait in enumerate(self.soul.traits, 1):
            print(f"   {i}. {trait}")

        print(f"\n⚠️  Boundaries ({len(self.soul.boundaries)}):")
        for i, boundary in enumerate(self.soul.boundaries, 1):
            print(f"   {i}. {boundary}")

        if self.soul.instructions:
            print("\n📋 Custom Instructions:")
            print(f"   {self.soul.instructions[:200]}...")

        print(f"\n📁 File: {self.soul_file}")


# ========== STANDALONE CLI ==========


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Soul System")
    parser.add_argument("action", choices=["show", "list", "load", "create", "edit"])
    parser.add_argument("--name", help="Name for custom soul")
    parser.add_argument("--tone", help="Tone description")
    parser.add_argument("--preset", help="Preset name to load")

    args = parser.parse_args()

    soul_system = SoulSystem()

    if args.action == "show":
        soul_system.display()

    elif args.action == "list":
        print("\n📋 Available Presets:")
        for preset in soul_system.list_presets():
            print(f"   - {preset}")

    elif args.action == "load":
        if args.preset:
            if soul_system.load_preset(args.preset):
                print(f"✓ Loaded preset: {args.preset}")
                soul_system.display()
            else:
                print(f"✗ Unknown preset: {args.preset}")
        else:
            print("Available presets:", ", ".join(soul_system.list_presets()))

    elif args.action == "create":
        print("\n🎨 Create Custom Soul")
        name = args.name or input("Name: ")
        tone = args.tone or input("Tone: ")

        print("Traits (one per line, empty to finish):")
        traits = []
        while True:
            t = input("  > ")
            if not t:
                break
            traits.append(t)

        print("Boundaries (one per line, empty to finish):")
        boundaries = []
        while True:
            b = input("  > ")
            if not b:
                break
            boundaries.append(b)

        soul_system.create_custom_soul(name, tone, traits, boundaries)
        print(f"\n✓ Created soul: {name}")
        soul_system.display()

    elif args.action == "edit":
        print("\n✏️  Edit Soul")
        print("1. Add trait")
        print("2. Remove trait")
        print("3. Add boundary")
        print("4. Remove boundary")

        choice = input("Choice: ")

        if choice == "1":
            trait = input("New trait: ")
            soul_system.edit_trait(len(soul_system.soul.traits), trait)
        elif choice == "2":
            for i, t in enumerate(soul_system.soul.traits):
                print(f"{i + 1}. {t}")
            idx = int(input("Index to remove: ")) - 1
            soul_system.edit_trait(idx, delete=True)
        elif choice == "3":
            boundary = input("New boundary: ")
            soul_system.edit_boundary(len(soul_system.soul.boundaries), boundary)
        elif choice == "4":
            for i, b in enumerate(soul_system.soul.boundaries):
                print(f"{i + 1}. {b}")
            idx = int(input("Index to remove: ")) - 1
            soul_system.edit_boundary(idx, delete=True)

        print("✓ Updated")
        soul_system.display()


if __name__ == "__main__":
    main()
