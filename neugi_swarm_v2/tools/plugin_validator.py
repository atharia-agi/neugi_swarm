"""
Plugin Validator for NEUGI Swarm.

Utility to validate plugin structure, manifest JSON, and entry points
before installation into the NEUGI plugin system.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class PluginValidationError(Exception):
    """Raised when plugin validation fails."""


PLUGIN_HOOKS = {
    "pre_init", "post_init", "pre_command", "post_command",
    "pre_llm", "post_llm", "pre_tool", "post_tool",
}


def validate_plugin(path: str) -> Tuple[bool, List[str]]:
    """
    Validate a plugin directory or manifest file.
    
    Args:
        path: Path to plugin directory or plugin.json file.
        
    Returns:
        Tuple of (is_valid, list of warning/error messages).
    """
    messages = []
    plugin_path = Path(path)

    if not plugin_path.exists():
        return False, [f"Path does not exist: {path}"]

    # Find manifest
    manifest_path = plugin_path / "plugin.json" if plugin_path.is_dir() else plugin_path
    if not manifest_path.exists():
        return False, [f"Manifest file not found: {manifest_path}"]

    # Validate manifest JSON
    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON in manifest: {e}"]

    if not isinstance(manifest, dict):
        return False, ["Manifest must be a JSON object"]

    # Required fields
    required_fields = ["name", "version", "entry_point"]
    for field in required_fields:
        if field not in manifest:
            messages.append(f"Missing required field: {field}")

    name = manifest.get("name", "unknown")

    # Validate version format
    version = manifest.get("version", "0.0.0")
    parts = version.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        messages.append(f"Invalid version format: '{version}' (expected X.Y.Z)")

    # Validate hooks
    hooks = manifest.get("hooks", [])
    if not isinstance(hooks, list):
        messages.append("'hooks' must be a list")
    else:
        for hook in hooks:
            if hook not in PLUGIN_HOOKS:
                messages.append(f"Unknown hook: '{hook}'. Valid hooks: {sorted(PLUGIN_HOOKS)}")

    # Validate entry point
    entry_point = manifest.get("entry_point", "")
    if entry_point:
        parts = entry_point.split(":")
        if len(parts) != 2:
            messages.append(f"Invalid entry_point format: '{entry_point}' (expected module:function)")
        else:
            module_path, func_name = parts
            # Try to validate the entry point module exists
            plugin_dir = manifest_path.parent
            module_file = plugin_dir / f"{module_path.replace('.', os.sep)}.py"
            module_dir = plugin_dir / module_path.replace(".", os.sep)
            # Entry point can be:
            # 1. A .py file inside or relative to plugin dir
            # 2. A package (__init__.py) with matching name inside plugin dir
            # 3. The plugin dir itself (if module_path == plugin_dir.name, __init__ resolves)
            found = False
            if module_file.exists():
                messages.append(f"Found entry point: {module_file.name}")
                found = True
            elif (module_dir / "__init__.py").exists():
                messages.append(f"Found entry point: {module_path}/__init__.py")
                found = True
            elif module_path == plugin_dir.name and (plugin_dir / "__init__.py").exists():
                messages.append(f"Found entry point: {plugin_dir.name}/__init__.py")
                found = True
            else:
                messages.append(f"Entry point module not found: {module_file}")

    # Validate requires
    requires = manifest.get("requires", {})
    if not isinstance(requires, dict):
        messages.append("'requires' must be an object")

    # Validate requires.neugi version
    if isinstance(requires, dict):
        neugi_ver = requires.get("neugi", "")
        if neugi_ver and not neugi_ver.startswith(">="):
            messages.append(f"neugi version constraint should use '>=' format, got: '{neugi_ver}'")

    # Validate dependencies
    plugin_deps = requires.get("plugins", []) if isinstance(requires, dict) else []
    if not isinstance(plugin_deps, list):
        messages.append("'requires.plugins' must be a list")

    is_valid = len([m for m in messages if "Missing" in m or "Invalid" in m or "Unknown" in m or "not found" in m]) == 0
    return is_valid, messages


def validate_plugin_structure(path: str) -> Tuple[bool, List[str]]:
    """
    Validate the file structure of a plugin directory.
    
    Args:
        path: Path to plugin directory.
        
    Returns:
        Tuple of (is_valid, list of messages).
    """
    messages = []
    plugin_path = Path(path)

    if not plugin_path.is_dir():
        return False, [f"Not a directory: {path}"]

    # Check for required files
    has_init = (plugin_path / "__init__.py").exists()
    has_manifest = (plugin_path / "plugin.json").exists()

    if not has_init and not has_manifest:
        messages.append("Plugin must have at least __init__.py or plugin.json")

    if has_init:
        messages.append("Found __init__.py (entry point)")
    if has_manifest:
        messages.append("Found plugin.json (manifest)")

    return bool(has_init or has_manifest), messages


def main():
    """CLI entry point for plugin validation."""
    import argparse
    parser = argparse.ArgumentParser(description="Validate NEUGI plugin")
    parser.add_argument("path", help="Path to plugin directory or plugin.json")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed messages")
    args = parser.parse_args()

    is_valid, messages = validate_plugin(args.path)
    struct_valid, struct_msgs = validate_plugin_structure(args.path)

    print(f"\nPlugin: {Path(args.path).resolve()}")
    print(f"Structure: {'PASS' if struct_valid else 'FAIL'}")
    print(f"Manifest:  {'PASS' if is_valid else 'FAIL'}")
    print()

    all_msgs = struct_msgs + messages
    if all_msgs:
        for msg in all_msgs:
            label = "INFO" if "Found" in msg or "Valid" in msg else ("WARN" if "should" in msg else "ERROR")
            print(f"  [{label}] {msg}")
        print()

    result = is_valid and struct_valid
    print(f"Result: {'VALID' if result else 'INVALID'}")
    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(main())