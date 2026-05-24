"""
Tool Executor for Autonomous Security Harness Plugin.
Runs security tools in Docker sandbox.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

try:
    import docker
except ImportError:
    docker = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

class ToolExecutor:
    def __init__(self):
        """Initialize the Docker client and load tool registry."""
        try:
            self.docker_client = docker.from_env()
        except (OSError, RuntimeError) as e:
            logger.error("Failed to initialize Docker client: %s", e)
            self.docker_client = None

        self.registry = self._load_tool_registry()
        logger.info(f"ToolExecutor initialized with {len(self.registry)} tools")

    def _load_tool_registry(self) -> dict[str, Any]:
        """Load tool registry from JSON file."""
        registry_path = Path(__file__).parent.parent / "tools" / "registry.json"
        if registry_path.exists():
            try:
                with open(registry_path, encoding='utf-8') as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                logger.error("Failed to load tool registry from %s: %s", registry_path, e)
                return {}
        else:
            logger.warning(f"Tool registry not found at {registry_path}")
            return {}

    def _build_command(self, spec: dict[str, Any], params: dict[str, Any]) -> list[str]:
        """Build command from template and parameters."""
        cmd = spec.get("command", []).copy()
        # Replace placeholders in command
        for i, part in enumerate(cmd):
            if isinstance(part, str) and part.startswith("{") and part.endswith("}"):
                key = part[1:-1]
                if key in params:
                    cmd[i] = str(params[key])
                else:
                    # If required parameter is missing, raise error
                    if spec.get("required_params", []).count(key) > 0:
                        raise ValueError(f"Missing required parameter: {key}")
                    else:
                        # Remove optional placeholder if not provided
                        cmd[i] = ""
        # Remove any empty strings
        cmd = [part for part in cmd if part]
        return cmd

    def _get_container_config(self, tool_name: str) -> dict[str, Any]:
        """Get Docker container configuration for a tool."""
        spec = self.registry.get(tool_name, {})
        # Default container config
        config = {
            "image": f"cybersec/{tool_name}:latest",
            "detach": True,
            "remove": True,
            "network_mode": "bridge",  # Outbound only, no inbound
            "mem_limit": spec.get("memory_limit", "2g"),
            "cpu_period": 100000,
            "cpu_quota": int(spec.get("cpu_limit", 1.0) * 100000),  # 1.0 CPU = 100000 quota
            "read_only": True,
            "security_opt": ["no-new-privileges:true"],
            "cap_drop": ["ALL"],
        }
        # Add necessary capabilities
        cap_add = spec.get("capabilities", [])
        if cap_add:
            config["cap_add"] = cap_add
        # For tools that need network raw (like nmap for SYN scan)
        if tool_name == "nmap" and "NET_RAW" not in cap_add:
            if "cap_add" not in config:
                config["cap_add"] = []
            config["cap_add"].append("NET_RAW")
        return config

    def _parse_output(self, tool_name: str, output: str) -> dict[str, Any]:
        """Parse tool output into structured format.
        In a real implementation, this would be tool-specific.
        For now, we return a simple structure.
        """
        # This is a placeholder. In reality, each tool would have a parser.
        # We'll just return the raw output and a basic structure.
        return {
            "raw": output,
            "lines": output.split('\n'),
            "word_count": len(output.split()),
            # Tool-specific parsing would go here
        }

    async def execute(self, tool_name: str, params: dict[str, Any], timeout: int = 300) -> dict[str, Any]:
        """Run tool in sandbox, return standardized result.

        Args:
            tool_name: Name of the tool to execute (must be in registry)
            params: Parameters for the tool
            timeout: Timeout in seconds

        Returns:
            Dictionary with execution results
        """
        start_time = time.time()

        # 1. Validate tool exists
        if tool_name not in self.registry:
            raise ValueError(f"Unknown tool: {tool_name}")

        # 2. Build command from template in registry
        spec = self.registry[tool_name]
        try:
            cmd = self._build_command(spec, params)
        except ValueError as e:
            raise e

        logger.info(f"Executing {tool_name} with command: {' '.join(cmd)}")

        # 3. Run container
        if not self.docker_client:
            raise RuntimeError("Docker client not available")

        container_config = self._get_container_config(tool_name)

        try:
            container = self.docker_client.containers.run(
                command=cmd,
                **container_config
            )
        except Exception as e:
            logger.error(f"Failed to start container for {tool_name}: {e}")
            raise

        try:
            # Wait for container to finish
            result = container.wait(timeout=timeout)
            logs = container.logs().decode('utf-8', errors='ignore')
        except Exception as e:
            logger.error(f"Error during container execution for {tool_name}: {e}")
            container.kill()
            raise
        finally:
            # Ensure container is removed (though remove=True should handle it)
            try:
                container.remove(force=True)
            except Exception:
                pass

        # 4. Parse output
        parsed = self._parse_output(tool_name, logs)

        # 5. Build result
        exit_code = result.get("StatusCode", -1)
        duration = time.time() - start_time

        result_dict = {
            "tool": tool_name,
            "command": " ".join(cmd),
            "exit_code": exit_code,
            "raw_output": logs[-100000:] if len(logs) > 100000 else logs,  # last 100k chars
            "parsed": parsed,
            "vulnerabilities": parsed.get("vulnerabilities", []),  # Tool-specific parsers should set this
            "duration_seconds": duration,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

        logger.info(f"Tool {tool_name} finished in {duration:.2f}s with exit code {exit_code}")
        return result_dict

# Example usage (for testing)
if __name__ == "__main__":
    import asyncio

    async def test() -> None:
        executor = ToolExecutor()
        try:
            result = await executor.execute("nmap", {"targets": ["127.0.0.1"], "ports": "22,80,443"}, timeout=60)
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(f"Error: {e}")

    asyncio.run(test())
