#!/usr/bin/env python3
"""
🤖 NEUGI SKILLS V2
===================

Based on BrowserOS Agent Skills specification:
- SKILL.md format with YAML frontmatter
- Support for scripts/, references/, assets/
- Natural language trigger matching

Version: 2.0
Date: March 15, 2026
"""

import os
import re
import json
import yaml
import importlib.util
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum


NEUGI_DIR = os.path.expanduser("~/neugi")
SKILLS_DIR = os.path.join(NEUGI_DIR, "skills_v2")


class SkillStatus(Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"


@dataclass
class SkillMetadata:
    """Skill metadata from frontmatter"""

    display_name: str = ""
    enabled: str = "true"
    version: str = "1.0"
    author: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    allowed_tools: List[str] = field(default_factory=list)


@dataclass
class Skill:
    """
    NEUGI Skill V2

    Full BrowserOS-style skill with:
    - YAML frontmatter metadata
    - Markdown instructions
    - Optional scripts/ directory
    - Optional references/ directory
    - Optional assets/ directory
    """

    name: str
    description: str
    instructions: str
    metadata: SkillMetadata = field(default_factory=SkillMetadata)
    path: str = ""
    scripts: Dict[str, Callable] = field(default_factory=dict)
    references: Dict[str, str] = field(default_factory=dict)
    status: SkillStatus = SkillStatus.ENABLED

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "instructions": self.instructions[:200] + "...",
            "metadata": {
                "display_name": self.metadata.display_name,
                "enabled": self.metadata.enabled,
                "version": self.metadata.version,
                "author": self.metadata.author,
                "tags": self.metadata.tags,
            },
            "path": self.path,
            "has_scripts": len(self.scripts) > 0,
            "has_references": len(self.references) > 0,
            "status": self.status.value,
        }


class SkillManagerV2:
    """
    NEUGI Skills V2 Manager

    Supports:
    - BrowserOS SKILL.md format
    - Script execution
    - Reference loading
    - Natural language matching
    """

    # Default skills directory
    DEFAULT_SKILLS_DIR = SKILLS_DIR

    def __init__(self, skills_dir: str = None):
        self.skills_dir = skills_dir or self.DEFAULT_SKILLS_DIR
        self.skills: Dict[str, Skill] = {}
        self._ensure_directory()
        self._discover_skills()

    def _ensure_directory(self):
        """Ensure skills directory exists"""
        os.makedirs(self.skills_dir, exist_ok=True)

        # Create example skill if none exist
        example_dir = os.path.join(self.skills_dir, "example-skill")
        if not os.path.exists(example_dir):
            self._create_example_skill(example_dir)

    def _create_example_skill(self, path: str):
        """Create example skill for users"""
        os.makedirs(path, exist_ok=True)

        example_skill = """---
name: example-skill
description: When the user asks for an example skill
metadata:
  display-name: Example Skill
  enabled: "true"
  version: "1.0"
  author: NEUGI
  tags: [example, tutorial]
---

# Example Skill

This is an example skill showing the SKILL.md format.

## When to Use

Use this skill when you want to see how skills work in NEUGI.

## Instructions

1. Greet the user
2. Explain what this skill does
3. Offer to create a custom skill

## Example Output

```
Hello! I'm an example skill.
I demonstrate how NEUGI Skills V2 work.
```
"""

        with open(os.path.join(path, "SKILL.md"), "w") as f:
            f.write(example_skill)

    def _discover_skills(self):
        """Discover all skills in skills directory"""
        if not os.path.exists(self.skills_dir):
            return

        for item in os.listdir(self.skills_dir):
            skill_path = os.path.join(self.skills_dir, item)

            if not os.path.isdir(skill_path):
                continue

            skill_file = os.path.join(skill_path, "SKILL.md")
            if os.path.exists(skill_file):
                try:
                    skill = self._load_skill(item, skill_path)
                    if skill:
                        self.skills[skill.name] = skill
                except Exception as e:
                    print(f"Error loading skill {item}: {e}")

    def _load_skill(self, skill_id: str, skill_path: str) -> Optional[Skill]:
        """Load a skill from directory"""
        skill_file = os.path.join(skill_path, "SKILL.md")

        if not os.path.exists(skill_file):
            return None

        # Parse SKILL.md
        with open(skill_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract frontmatter and instructions
        frontmatter = {}
        instructions = content

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    instructions = parts[2].strip()
                except yaml.YAMLError:
                    pass

        # Parse metadata
        metadata = SkillMetadata(
            display_name=frontmatter.get("metadata", {}).get("display-name", skill_id),
            enabled=frontmatter.get("metadata", {}).get("enabled", "true"),
            version=frontmatter.get("metadata", {}).get("version", "1.0"),
            author=frontmatter.get("metadata", {}).get("author", ""),
            description=frontmatter.get("description", ""),
            tags=frontmatter.get("metadata", {}).get("tags", []),
            allowed_tools=frontmatter.get("metadata", {}).get("allowed-tools", []),
        )

        # Load scripts
        scripts = self._load_scripts(skill_path)

        # Load references
        references = self._load_references(skill_path)

        # Determine status
        status = SkillStatus.ENABLED if metadata.enabled == "true" else SkillStatus.DISABLED

        return Skill(
            name=frontmatter.get("name", skill_id),
            description=frontmatter.get("description", ""),
            instructions=instructions,
            metadata=metadata,
            path=skill_path,
            scripts=scripts,
            references=references,
            status=status,
        )

    def _load_scripts(self, skill_path: str) -> Dict[str, Callable]:
        """Load Python scripts from skill's scripts/ directory"""
        scripts = {}
        scripts_dir = os.path.join(skill_path, "scripts")

        if not os.path.exists(scripts_dir):
            return scripts

        for filename in os.listdir(scripts_dir):
            if filename.endswith(".py"):
                script_name = filename[:-3]
                script_path = os.path.join(scripts_dir, filename)

                try:
                    spec = importlib.util.spec_from_file_location(script_name, script_path)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)

                        # Look for execute or run function
                        if hasattr(module, "execute"):
                            scripts[script_name] = module.execute
                        elif hasattr(module, "run"):
                            scripts[script_name] = module.run
                except Exception as e:
                    print(f"Error loading script {filename}: {e}")

        return scripts

    def _load_references(self, skill_path: str) -> Dict[str, str]:
        """Load reference files from skill's references/ directory"""
        references = {}
        refs_dir = os.path.join(skill_path, "references")

        if not os.path.exists(refs_dir):
            return references

        for filename in os.listdir(refs_dir):
            filepath = os.path.join(refs_dir, filename)

            if os.path.isfile(filepath):
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        references[filename] = f.read()
                except Exception:
                    pass

        return references

    # ========== SKILL MANAGEMENT ==========

    def list_skills(self, include_disabled: bool = False) -> List[Skill]:
        """List all skills"""
        skills = list(self.skills.values())

        if not include_disabled:
            skills = [s for s in skills if s.status == SkillStatus.ENABLED]

        return skills

    def get_skill(self, name: str) -> Optional[Skill]:
        """Get a skill by name"""
        return self.skills.get(name)

    def enable_skill(self, name: str) -> bool:
        """Enable a skill"""
        skill = self.skills.get(name)
        if skill:
            skill.status = SkillStatus.ENABLED
            skill.metadata.enabled = "true"
            self._save_skill(skill)
            return True
        return False

    def disable_skill(self, name: str) -> bool:
        """Disable a skill"""
        skill = self.skills.get(name)
        if skill:
            skill.status = SkillStatus.DISABLED
            skill.metadata.enabled = "false"
            self._save_skill(skill)
            return True
        return False

    def _save_skill(self, skill: Skill):
        """Save skill metadata back to file"""
        skill_file = os.path.join(skill.path, "SKILL.md")

        frontmatter = {
            "name": skill.name,
            "description": skill.description,
            "metadata": {
                "display-name": skill.metadata.display_name,
                "enabled": skill.metadata.enabled,
                "version": skill.metadata.version,
                "author": skill.metadata.author,
                "tags": skill.metadata.tags,
            },
        }

        content = "---\n"
        content += yaml.dump(frontmatter, default_flow_style=False)
        content += "---\n\n"
        content += skill.instructions

        with open(skill_file, "w", encoding="utf-8") as f:
            f.write(content)

    # ========== SKILL MATCHING ==========

    def match_skill(self, user_request: str) -> Optional[Skill]:
        """
        Find the best matching skill based on description

        Uses keyword matching and description similarity
        """
        request_lower = user_request.lower()
        best_match = None
        best_score = 0

        for skill in self.list_skills():
            if skill.status != SkillStatus.ENABLED:
                continue

            score = 0

            # Check description keywords
            desc_words = skill.description.lower().split()
            for word in desc_words:
                if word in request_lower:
                    score += 2

            # Check metadata tags
            for tag in skill.metadata.tags:
                if tag.lower() in request_lower:
                    score += 3

            # Check name
            if skill.name.lower().replace("-", " ") in request_lower:
                score += 5

            if score > best_score:
                best_score = score
                best_match = skill

        return best_match if best_score > 0 else None

    # ========== SKILL EXECUTION ==========

    def execute_skill(self, name: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute a skill with context"""
        skill = self.get_skill(name)

        if not skill:
            return {"error": f"Skill {name} not found"}

        if skill.status != SkillStatus.ENABLED:
            return {"error": f"Skill {name} is disabled"}

        return {
            "skill": skill.name,
            "description": skill.description,
            "instructions": skill.instructions,
            "scripts": list(skill.scripts.keys()),
            "references": list(skill.references.keys()),
            "metadata": skill.metadata.__dict__,
        }

    def run_script(self, skill_name: str, script_name: str, **kwargs) -> Any:
        """Run a script within a skill"""
        skill = self.get_skill(skill_name)

        if not skill:
            return {"error": f"Skill {skill_name} not found"}

        if script_name not in skill.scripts:
            return {"error": f"Script {script_name} not found in skill {skill_name}"}

        try:
            return skill.scripts[script_name](**kwargs)
        except Exception as e:
            return {"error": str(e)}

    def get_reference(self, skill_name: str, ref_name: str) -> Optional[str]:
        """Get a reference file from a skill"""
        skill = self.get_skill(skill_name)

        if not skill:
            return None

        return skill.references.get(ref_name)

    # ========== CREATE/DELETE ==========

    def create_skill(
        self,
        name: str,
        description: str,
        instructions: str,
        tags: List[str] = None,
        author: str = "User",
    ) -> Skill:
        """Create a new skill"""
        # Create directory
        skill_dir = os.path.join(self.skills_dir, name)
        os.makedirs(skill_dir, exist_ok=True)

        # Create SKILL.md
        metadata = SkillMetadata(
            display_name=name.replace("-", " ").title(),
            enabled="true",
            version="1.0",
            author=author,
            tags=tags or [],
        )

        skill = Skill(
            name=name,
            description=description,
            instructions=instructions,
            metadata=metadata,
            path=skill_dir,
            status=SkillStatus.ENABLED,
        )

        self._save_skill(skill)
        self.skills[name] = skill

        return skill

    def delete_skill(self, name: str) -> bool:
        """Delete a skill"""
        skill = self.get_skill(name)

        if not skill:
            return False

        # Remove directory
        import shutil

        shutil.rmtree(skill.path)

        del self.skills[name]
        return True

    # ========== EXPORT ==========

    def export_skill(self, name: str, format: str = "markdown") -> Optional[str]:
        """Export skill in different formats"""
        skill = self.get_skill(name)

        if not skill:
            return None

        if format == "markdown":
            return f"# {skill.metadata.display_name}\n\n{skill.instructions}"

        elif format == "json":
            return json.dumps(skill.to_dict(), indent=2)

        return None


# ========== STANDALONE CLI ==========


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Skills V2")
    parser.add_argument(
        "action", choices=["list", "show", "create", "enable", "disable", "match", "execute"]
    )
    parser.add_argument("--name", help="Skill name")
    parser.add_argument("--request", help="User request for matching")

    args = parser.parse_args()

    manager = SkillManagerV2()

    if args.action == "list":
        print("\n📦 NEUGI SKILLS V2")
        print("=" * 50)

        for skill in manager.list_skills():
            status = "✅" if skill.status == SkillStatus.ENABLED else "❌"
            print(f"{status} {skill.name}")
            print(f"   {skill.description}")
            print(f"   Tags: {', '.join(skill.metadata.tags)}")
            print()

        print(f"Total: {len(manager.list_skills())} skills")

    elif args.action == "show":
        if not args.name:
            print("Specify --name")
            return

        skill = manager.get_skill(args.name)
        if skill:
            print(f"\n📦 Skill: {skill.name}")
            print(f"Description: {skill.description}")
            print(f"Status: {skill.status.value}")
            print(f"\nInstructions:\n{skill.instructions}")
        else:
            print(f"Skill not found: {args.name}")

    elif args.action == "match":
        if not args.request:
            args.request = input("Enter request: ")

        match = manager.match_skill(args.request)
        if match:
            print(f"\n✓ Matched: {match.name}")
            print(f"   {match.description}")
        else:
            print("\n✗ No matching skill found")

    elif args.action == "execute":
        if not args.name:
            print("Specify --name")
            return

        result = manager.execute_skill(args.name)
        print(json.dumps(result, indent=2))

    elif args.action == "enable":
        if manager.enable_skill(args.name):
            print(f"✓ Enabled: {args.name}")
        else:
            print(f"✗ Failed: {args.name}")

    elif args.action == "disable":
        if manager.disable_skill(args.name):
            print(f"✓ Disabled: {args.name}")
        else:
            print(f"✗ Failed: {args.name}")


if __name__ == "__main__":
    main()
