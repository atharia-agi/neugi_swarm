"""Test that _generate_skill_code produces valid, exec-able Python."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "repo"))

from dataclasses import dataclass, field
from typing import Any


# Minimal stubs matching neugi_swarm_v2.skills
@dataclass
class SkillAction:
    name: str = ""
    description: str = ""
    parameters: list = field(default_factory=list)
    returns: str | None = None
    side_effects: list = field(default_factory=list)

@dataclass
class SkillContract:
    name: str
    description: str
    tier: str = "BUNDLED"
    confidence_threshold: float = 0.0
    state: str = "loading"
    path: str = ""
    scripts: list = field(default_factory=list)
    references: list = field(default_factory=list)
    assets: list = field(default_factory=list)
    actions: list = field(default_factory=list)
    load_error: str = ""

class SkillTier:
    BUNDLED = "bundled"
    EXTRA = "extra"
    MANAGED = "managed"
    PERSONAL = "personal"
    PROJECT = "project"
    WORKSPACE = "workspace"


def main() -> None:
    """Run the skill code generation tests."""
    # Import the real method
    from neugi_swarm_v2.skills.improver import SkillImprovement, SkillImprover

    # Create a test improvement
    improvement = SkillImprovement(
        skill_name="test_auto_skill",
        improvement_type="new",
        confidence=0.87,
        source_interactions=["sess_001_task_create_batch", "sess_002_task_create_batch", "sess_003_task_process_items"],
        suggested_change="Create new skill for repeated task: process batch items from session data",
    )

    # Generate the code
    code = SkillImprover._generate_skill_code(None, improvement)
    print("=== Generated Code ===")
    print(code)
    print("=== End Generated Code ===\n")

    # Test compilation
    print("=== Compilation Test ===")
    try:
        compiled = compile(code, "<generated_skill>", "exec")
        print("Compilation: PASS")
    except SyntaxError as e:
        print(f"Compilation FAILED: {e}")
        sys.exit(1)

    # Test execution
    print("\n=== Execution Test ===")
    globs: dict[str, Any] = {"SkillAction": SkillAction, "SkillContract": SkillContract, "SkillTier": SkillTier}
    try:
        exec(compiled, globs)  # nosec B102
        print("Execution: PASS")
    except Exception as e:
        print(f"Execution FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Verify SKILL_CONTRACT was created
    print("\n=== SkillContract Test ===")
    contract = globs["SKILL_CONTRACT"]
    print(f"  name: {contract.name}")
    print(f"  description: {contract.description}")
    print(f"  tier: {contract.tier}")
    print(f"  confidence_threshold: {contract.confidence_threshold}")
    assert contract.name == "test_auto_skill"
    assert "process batch items" in contract.description
    assert contract.tier == "workspace"
    assert contract.confidence_threshold == 0.87
    print("SKILL_CONTRACT: PASS")

    # Test skill_function with various inputs
    skill_fn = globs["skill_function"]

    print("\n=== Functional Tests ===")

    # Test 1: Empty interactions / no source patterns
    @dataclass
    class SkillImprovement2:
        skill_name: str
        confidence: float
        source_interactions: list[str]
        suggested_change: str

    imp2 = SkillImprovement2(
        skill_name="empty_test",
        confidence=0.5,
        source_interactions=[],
        suggested_change="Create new skill for repeated task: simple action",
    )
    code2 = SkillImprover._generate_skill_code(None, imp2)
    globs2: dict[str, Any] = {"SkillAction": SkillAction, "SkillContract": SkillContract, "SkillTier": SkillTier}
    exec(compile(code2, "<test2>", "exec"), globs2)  # nosec B102
    fn2 = globs2["skill_function"]

    result = fn2(context=None)
    print(f"Test 2a (no context, no interactions): {result.description}")
    assert "no context" in result.description.lower() or "no prior" in result.description.lower()

    result = fn2(context=["item1"])
    print(f"Test 2b (context, no interactions): {result.description}")
    assert "no prior patterns" in result.description.lower() or "context items (no prior" in result.description

    print("Edge case tests: PASS")

    # Test 3: Multiple matches
    result = skill_fn(context=["sess_001_task_create_batch", "unknown_thing"])
    print(f"Test 3 (partial match): {result.description}")
    assert "Matched" in result.description
    assert result.name == "test_auto_skill"
    assert "skill_generated" in result.side_effects

    # Test 4: All match
    result = skill_fn(context=["sess_001_task_create_batch", "sess_002_task_create_batch"])
    print(f"Test 4 (multiple matches): {result.description}")
    assert "Matched 2" in result.description

    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()
