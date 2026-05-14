# NEUGI v2 Skills System

## Overview

NEUGI v2 implements a **6-tier hierarchical skill system** with gating, token budgets, and auto-generation. Skills are defined in SKILL.md files with YAML frontmatter.

## Skill Tiers (Resolution Order)

```
1. Global       (~/.neugi/skills/)
2. Project      (./.neugi/skills/)
3. Agent        (per-agent skills/)
4. Session      (runtime session skills)
5. User         (per-user skills)
6. Ephemeral    (single-turn, auto-discard)
```

Lower tiers override higher tiers. Name collisions are resolved by tier precedence.

## SKILL.md v3 Specification

```markdown
---
name: code_review
description: Review code for bugs and style issues
tier: project
tags: [code, review, quality]
triggers: ["review this code", "check for bugs"]
agents: [builder, evaluator]
token_budget: 500
risk: low
---

# Code Review Skill

## Context
When the user shares code, analyze it for:
- Syntax errors
- Logic bugs
- Performance issues
- Style violations

## Procedure
1. Parse the code language
2. Check for common anti-patterns
3. Suggest improvements
4. Provide corrected version if needed

## Tools
- file_read
- syntax_check
- lint

## Examples

### Example 1: Python
User: "Review this function"
```python
def add(a, b):
    return a + b
```
Response: "Function is correct but lacks type hints and docstring."
```

## Required Frontmatter Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique skill identifier |
| `description` | string | Yes | What the skill does |
| `tier` | enum | Yes | global/project/agent/session/user/ephemeral |
| `tags` | list | No | Searchable tags |
| `triggers` | list | No | NL phrases that activate this skill |
| `agents` | list | No | Which agents can use this skill |
| `token_budget` | int | No | Max tokens this skill can inject |
| `risk` | enum | No | low/medium/high/critical |

## Gating

Skills are gated at load time based on:
- Agent allowlist
- Risk level vs. policy
- Token budget availability
- Dependency satisfaction

```python
from neugi_swarm_v2.skills import SkillManager

mgr = SkillManager()
mgr.load_all()  # Only gated-in skills are loaded
```

## Prompt Compaction Tiers

| Tier | Description | Token Budget |
|------|-------------|--------------|
| FULL | Complete skill text | As specified |
| COMPACT | Summarized procedure | 60% of full |
| TRUNCATED | Trigger + name only | 20% of full |

Compaction happens automatically when context window is constrained.

## Auto-Generation (Workshop)

NEUGI can automatically generate skills from observed successful procedures:

```bash
neugi skill workshop --observe "docker_deploy"
```

This creates a SKILL.md scaffold from the observed procedure.

## Import/Export

```bash
# Export all skills to a directory
neugi skill export --format markdown --dir ./skills-backup

# Import skills from a directory
neugi skill import --dir ./my-skills

# Export as JSON for programmatic use
neugi skill export --format json --out skills.json
```

## Best Practices

1. **Keep skills focused** — One skill per task type
2. **Use triggers** — Helps NL matcher find the right skill
3. **Set token budgets** — Prevents context window overflow
4. **Tag generously** — Improves discoverability
5. **Version skills** — Increment version when behavior changes
6. **Test skills** — Use `neugi skill test <name>` to validate
