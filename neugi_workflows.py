#!/usr/bin/env python3
"""
🤖 NEUGI WORKFLOW ENGINE
=========================

BrowserOS-style visual workflow automation:
- JSON-based workflow definition
- Step execution with dependencies
- Parallel execution support
- Conditional logic

Version: 1.0
Date: March 15, 2026
"""

import os
import json
import time
import uuid
import asyncio
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed


NEUGI_DIR = os.path.expanduser("~/neugi")
WORKFLOWS_DIR = os.path.join(NEUGI_DIR, "workflows")


class StepType(Enum):
    """Workflow step types"""

    ACTION = "action"
    CONDITION = "condition"
    LOOP = "loop"
    WAIT = "wait"
    TRANSFORM = "transform"


class StepStatus(Enum):
    """Step execution status"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowStep:
    """Single workflow step"""

    id: str
    type: str
    name: str
    params: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    condition: str = ""  # For conditional steps
    retry: int = 0
    timeout: int = 60


@dataclass
class Workflow:
    """Workflow definition"""

    id: str
    name: str
    description: str
    steps: List[WorkflowStep]
    created_at: str = ""
    updated_at: str = ""
    version: str = "1.0"


@dataclass
class WorkflowRun:
    """Workflow execution"""

    id: str
    workflow_id: str
    status: str
    started_at: str = ""
    completed_at: str = ""
    step_results: Dict[str, Dict] = field(default_factory=dict)
    error: str = ""


class WorkflowEngine:
    """
    NEUGI Workflow Engine

    Features:
    - JSON workflow definition
    - Step dependencies
    - Parallel execution
    - Conditional logic
    - Retry logic
    """

    # Built-in actions
    ACTIONS: Dict[str, Callable] = {}

    def __init__(self, workflows_dir: str = None):
        self.workflows_dir = workflows_dir or WORKFLOWS_DIR
        self.workflows: Dict[str, Workflow] = {}
        self._ensure_directory()
        self._discover_workflows()
        self._register_default_actions()

    def _ensure_directory(self):
        """Create workflows directory"""
        os.makedirs(self.workflows_dir, exist_ok=True)

    def _discover_workflows(self):
        """Load saved workflows"""
        if not os.path.exists(self.workflows_dir):
            return

        for filename in os.listdir(self.workflows_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(self.workflows_dir, filename)
                try:
                    with open(filepath, "r") as f:
                        data = json.load(f)
                        workflow = self._deserialize_workflow(data)
                        self.workflows[workflow.id] = workflow
                except Exception as e:
                    print(f"Error loading {filename}: {e}")

    def _register_default_actions(self):
        """Register built-in actions"""
        self.ACTIONS = {
            "log": self._action_log,
            "delay": self._action_delay,
            "http_request": self._action_http,
            "run_command": self._action_command,
            "transform": self._action_transform,
            "notify": self._action_notify,
        }

    # ========== ACTION HANDLERS ==========

    def _action_log(self, params: Dict) -> Dict:
        """Log action"""
        message = params.get("message", "")
        level = params.get("level", "info")
        print(f"[{level.upper()}] {message}")
        return {"logged": True, "message": message}

    def _action_delay(self, params: Dict) -> Dict:
        """Delay action"""
        seconds = params.get("seconds", 1)
        time.sleep(seconds)
        return {"delayed": seconds}

    def _action_http(self, params: Dict) -> Dict:
        """HTTP request action"""
        import urllib.request
        import urllib.parse

        url = params.get("url", "")
        method = params.get("method", "GET")
        headers = params.get("headers", {})

        try:
            req = urllib.request.Request(url, method=method)
            for k, v in headers.items():
                req.add_header(k, v)

            with urllib.request.urlopen(req, timeout=30) as response:
                return {"status": response.status, "body": response.read().decode()[:1000]}
        except Exception as e:
            return {"error": str(e)}

    def _action_command(self, params: Dict) -> Dict:
        """Run shell command"""
        import subprocess

        command = params.get("command", "")
        timeout = params.get("timeout", 60)

        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=timeout
            )
            return {
                "returncode": result.returncode,
                "stdout": result.stdout[:1000],
                "stderr": result.stderr[:500],
            }
        except Exception as e:
            return {"error": str(e)}

    def _action_transform(self, params: Dict) -> Dict:
        """Data transformation"""
        data = params.get("data", {})
        transform_type = params.get("type", "identity")

        if transform_type == "uppercase":
            return {"result": str(data).upper()}
        elif transform_type == "lowercase":
            return {"result": str(data).lower()}
        elif transform_type == "json_parse":
            try:
                return {"result": json.loads(data)}
            except:
                return {"result": data}
        elif transform_type == "json_stringify":
            return {"result": json.dumps(data)}

        return {"result": data}

    def _action_notify(self, params: Dict) -> Dict:
        """Send notification"""
        message = params.get("message", "")
        channel = params.get("channel", "console")

        if channel == "console":
            print(f"📢 NOTIFICATION: {message}")

        return {"notified": True, "message": message}

    # ========== WORKFLOW MANAGEMENT ==========

    def create_workflow(self, name: str, description: str, steps: List[Dict]) -> Workflow:
        """Create a new workflow"""
        workflow_id = name.lower().replace(" ", "-")

        step_objects = []
        for i, step_data in enumerate(steps):
            step = WorkflowStep(
                id=step_data.get("id", f"step_{i}"),
                type=step_data.get("type", "action"),
                name=step_data.get("name", f"Step {i}"),
                params=step_data.get("params", {}),
                depends_on=step_data.get("depends_on", []),
                condition=step_data.get("condition", ""),
                retry=step_data.get("retry", 0),
                timeout=step_data.get("timeout", 60),
            )
            step_objects.append(step)

        workflow = Workflow(
            id=workflow_id,
            name=name,
            description=description,
            steps=step_objects,
            created_at=datetime.now().isoformat(),
            version="1.0",
        )

        self.workflows[workflow_id] = workflow
        self._save_workflow(workflow)

        return workflow

    def _save_workflow(self, workflow: Workflow):
        """Save workflow to file"""
        filepath = os.path.join(self.workflows_dir, f"{workflow.id}.json")

        data = {
            "id": workflow.id,
            "name": workflow.name,
            "description": workflow.description,
            "version": workflow.version,
            "created_at": workflow.created_at,
            "steps": [
                {
                    "id": s.id,
                    "type": s.type,
                    "name": s.name,
                    "params": s.params,
                    "depends_on": s.depends_on,
                    "condition": s.condition,
                    "retry": s.retry,
                    "timeout": s.timeout,
                }
                for s in workflow.steps
            ],
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    def _deserialize_workflow(self, data: Dict) -> Workflow:
        """Deserialize workflow"""
        steps = [
            WorkflowStep(
                id=s["id"],
                type=s.get("type", "action"),
                name=s.get("name", ""),
                params=s.get("params", {}),
                depends_on=s.get("depends_on", []),
                condition=s.get("condition", ""),
                retry=s.get("retry", 0),
                timeout=s.get("timeout", 60),
            )
            for s in data.get("steps", [])
        ]

        return Workflow(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            steps=steps,
            created_at=data.get("created_at", ""),
            version=data.get("version", "1.0"),
        )

    def list_workflows(self) -> List[Dict]:
        """List all workflows"""
        return [
            {
                "id": w.id,
                "name": w.name,
                "description": w.description,
                "steps": len(w.steps),
                "created": w.created_at[:10],
            }
            for w in self.workflows.values()
        ]

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Get workflow by ID"""
        return self.workflows.get(workflow_id)

    def delete_workflow(self, workflow_id: str) -> bool:
        """Delete workflow"""
        if workflow_id in self.workflows:
            del self.workflows[workflow_id]

            filepath = os.path.join(self.workflows_dir, f"{workflow_id}.json")
            if os.path.exists(filepath):
                os.remove(filepath)

            return True
        return False

    # ========== WORKFLOW EXECUTION ==========

    def run_workflow(self, workflow_id: str, context: Dict = None) -> WorkflowRun:
        """Execute a workflow"""
        workflow = self.get_workflow(workflow_id)
        if not workflow:
            return None

        context = context or {}
        run = WorkflowRun(
            id=str(uuid.uuid4())[:8],
            workflow_id=workflow_id,
            status="running",
            started_at=datetime.now().isoformat(),
        )

        # Build dependency graph
        step_map = {s.id: s for s in workflow.steps}
        completed = set()
        failed = False

        # Execute steps in order respecting dependencies
        for step in workflow.steps:
            if failed:
                run.step_results[step.id] = {"status": "skipped"}
                continue

            # Check dependencies
            deps_met = all(dep in completed for dep in step.depends_on)
            if not deps_met:
                run.step_results[step.id] = {"status": "skipped"}
                continue

            # Execute step
            result = self._execute_step(step, context, run)
            run.step_results[step.id] = result

            if result.get("status") == "failed":
                failed = True

        run.completed_at = datetime.now().isoformat()
        run.status = "completed" if not failed else "failed"

        return run

    def _execute_step(self, step: WorkflowStep, context: Dict, run: WorkflowRun) -> Dict:
        """Execute a single step"""

        # Handle different step types
        if step.type == "condition":
            return self._execute_condition(step, context, run)

        elif step.type == "loop":
            return self._execute_loop(step, context, run)

        elif step.type == "wait":
            return self._execute_wait(step, context)

        # Default: action step
        action_name = step.params.get("action", "")

        # Get action from params or use step name
        if not action_name:
            action_name = step.name.lower().replace(" ", "_")

        # Look up action
        action = self.ACTIONS.get(action_name)

        if not action:
            return {"status": "failed", "error": f"Unknown action: {action_name}"}

        # Execute with retry
        for attempt in range(step.retry + 1):
            try:
                # Prepare params
                params = self._prepare_params(step.params, context, run)

                # Execute
                result = action(params)

                # Store result in context
                context[step.id] = result

                return {"status": "completed", "result": result}

            except Exception as e:
                if attempt == step.retry:
                    return {"status": "failed", "error": str(e)}
                time.sleep(1)

        return {"status": "failed", "error": "Max retries exceeded"}

    def _prepare_params(self, params: Dict, context: Dict, run: WorkflowRun) -> Dict:
        """Prepare params with variable substitution"""
        prepared = {}

        for key, value in params.items():
            if isinstance(value, str) and "{{" in value:
                # Variable substitution
                for var, var_value in context.items():
                    value = value.replace(f"{{{{{var}}}}}", str(var_value))

            prepared[key] = value

        return prepared

    def _execute_condition(self, step: WorkflowStep, context: Dict, run: WorkflowRun) -> Dict:
        """Execute conditional step"""
        condition = step.params.get("condition", "")

        # Simple condition evaluation
        try:
            # Check if condition is in context as truthy
            result = context.get(condition, False)

            return {
                "status": "completed",
                "result": {"condition_met": bool(result)},
                "branch": "then" if result else "else",
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    def _execute_loop(self, step: WorkflowStep, context: Dict, run: WorkflowRun) -> Dict:
        """Execute loop step"""
        iterations = step.params.get("iterations", 1)
        action_name = step.params.get("action", "")

        results = []

        for i in range(iterations):
            if action_name in self.ACTIONS:
                result = self.ACTIONS[action_name](step.params)
                results.append(result)

        return {"status": "completed", "result": {"iterations": iterations, "results": results}}

    def _execute_wait(self, step: WorkflowStep, context: Dict) -> Dict:
        """Execute wait step"""
        seconds = step.params.get("seconds", 1)
        time.sleep(seconds)

        return {"status": "completed", "waited": seconds}


# ========== EXAMPLE WORKFLOWS ==========

EXAMPLE_WORKFLOWS = {
    "daily-standup": {
        "name": "Daily Standup",
        "description": "Morning standup notification",
        "steps": [
            {
                "id": "check_calendar",
                "name": "Check Calendar",
                "params": {"action": "http_request", "url": "https://api.example.com/calendar"},
            },
            {
                "id": "format_message",
                "name": "Format Message",
                "params": {
                    "action": "transform",
                    "type": "json_stringify",
                    "data": "{{check_calendar}}",
                },
            },
            {
                "id": "send_notification",
                "name": "Notify",
                "params": {"action": "notify", "message": "{{format_message}}"},
            },
        ],
    },
    "git-backup": {
        "name": "Git Backup",
        "description": "Backup repo to remote",
        "steps": [
            {
                "id": "add_all",
                "name": "Git Add",
                "params": {"action": "run_command", "command": "git add -A"},
            },
            {
                "id": "commit",
                "name": "Git Commit",
                "params": {"action": "run_command", "command": "git commit -m 'Auto backup'"},
            },
            {
                "id": "push",
                "name": "Git Push",
                "params": {"action": "run_command", "command": "git push"},
            },
        ],
    },
    "health-check": {
        "name": "System Health Check",
        "description": "Check system health",
        "steps": [
            {
                "id": "check_cpu",
                "name": "CPU Check",
                "params": {"action": "run_command", "command": "uptime"},
            },
            {
                "id": "check_disk",
                "name": "Disk Check",
                "params": {"action": "run_command", "command": "df -h"},
            },
            {
                "id": "notify",
                "name": "Notify",
                "params": {"action": "notify", "message": "Health check complete"},
            },
        ],
    },
}


# ========== STANDALONE CLI ==========


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Workflow Engine")
    parser.add_argument("action", choices=["list", "create", "run", "delete"])
    parser.add_argument("--name", help="Workflow name")
    parser.add_argument("--id", help="Workflow ID")
    parser.add_argument("--example", help="Load example workflow")

    args = parser.parse_args()

    engine = WorkflowEngine()

    if args.action == "list":
        print("\n📋 NEUGI WORKFLOWS")
        print("=" * 50)

        workflows = engine.list_workflows()
        if not workflows:
            print("No workflows found.")
            print("\nLoad example: python neugi_workflows.py create --example daily-standup")
        else:
            for wf in workflows:
                print(f"\n📦 {wf['name']}")
                print(f"   {wf['description']}")
                print(f"   Steps: {wf['steps']}")

    elif args.action == "create":
        if args.example and args.example in EXAMPLE_WORKFLOWS:
            example = EXAMPLE_WORKFLOWS[args.example]
            wf = engine.create_workflow(example["name"], example["description"], example["steps"])
            print(f"✓ Created: {wf.name}")
        else:
            print("Available examples:")
            for name in EXAMPLE_WORKFLOWS:
                print(f"  - {name}")

    elif args.action == "run":
        if not args.id:
            print("Specify --id")
            return

        print(f"\n🚀 Running workflow: {args.id}")
        run = engine.run_workflow(args.id)

        if run:
            print(f"Status: {run.status}")
            print(f"Steps:")
            for step_id, result in run.step_results.items():
                status = result.get("status", "unknown")
                print(f"  {step_id}: {status}")
        else:
            print(f"Workflow not found: {args.id}")

    elif args.action == "delete":
        if engine.delete_workflow(args.id):
            print(f"✓ Deleted: {args.id}")
        else:
            print(f"Workflow not found: {args.id}")


if __name__ == "__main__":
    main()
