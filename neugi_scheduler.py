#!/usr/bin/env python3
"""
🤖 NEUGI SCHEDULER
===================

Based on BrowserOS Scheduled Tasks:
- Daily, hourly, minute schedules
- Background execution
- Task history (last 15 runs)

Version: 1.0
Date: March 15, 2026
"""

import os
import json
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum


NEUGI_DIR = os.path.expanduser("~/neugi")
SCHEDULER_DIR = os.path.join(NEUGI_DIR, "scheduler")
TASKS_FILE = os.path.join(SCHEDULER_DIR, "tasks.json")


class ScheduleType(Enum):
    DAILY = "daily"
    HOURLY = "hourly"
    MINUTES = "minutes"


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ScheduledTask:
    """Scheduled task definition"""

    name: str
    prompt: str
    schedule_type: str
    time: str = ""  # For daily: "08:00"
    interval: int = 1  # For hourly/minutes
    enabled: bool = True
    created_at: str = ""
    last_run: str = ""
    next_run: str = ""
    history: List[Dict] = field(default_factory=list)


class NEUGIScheduler:
    """
    NEUGI Native Scheduler

    Supports:
    - Daily tasks at specific time
    - Hourly tasks at interval
    - Minute tasks at interval
    - Background execution
    - Task history
    """

    MAX_HISTORY = 15

    def __init__(self, scheduler_dir: str = None):
        self.scheduler_dir = scheduler_dir or SCHEDULER_DIR
        self.tasks_file = os.path.join(self.scheduler_dir, "tasks.json")
        self.tasks: Dict[str, ScheduledTask] = {}
        self._ensure_directory()
        self._load_tasks()
        self._running = False
        self._thread = None

    def _ensure_directory(self):
        """Create scheduler directory"""
        os.makedirs(self.scheduler_dir, exist_ok=True)

    def _load_tasks(self):
        """Load tasks from file"""
        if os.path.exists(self.tasks_file):
            try:
                with open(self.tasks_file, "r") as f:
                    data = json.load(f)
                    for name, task_data in data.items():
                        self.tasks[name] = ScheduledTask(**task_data)
            except Exception as e:
                print(f"Error loading tasks: {e}")

    def _save_tasks(self):
        """Save tasks to file"""
        data = {
            name: {
                "name": task.name,
                "prompt": task.prompt,
                "schedule_type": task.schedule_type,
                "time": task.time,
                "interval": task.interval,
                "enabled": task.enabled,
                "created_at": task.created_at,
                "last_run": task.last_run,
                "next_run": task.next_run,
                "history": task.history,
            }
            for name, task in self.tasks.items()
        }

        with open(self.tasks_file, "w") as f:
            json.dump(data, f, indent=2)

    def _calculate_next_run(self, task: ScheduledTask) -> str:
        """Calculate next run time"""
        now = datetime.now()

        if task.schedule_type == "daily":
            # Daily at specific time
            hour, minute = map(int, task.time.split(":"))
            next_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            if next_time <= now:
                next_time += timedelta(days=1)

        elif task.schedule_type == "hourly":
            # Every N hours
            next_time = now + timedelta(hours=task.interval)

        else:  # minutes
            # Every N minutes
            next_time = now + timedelta(minutes=task.interval)

        return next_time.isoformat()

    def add_task(
        self, name: str, prompt: str, schedule_type: str, time: str = None, interval: int = None
    ) -> bool:
        """Add a scheduled task"""

        if name in self.tasks:
            return False

        task = ScheduledTask(
            name=name,
            prompt=prompt,
            schedule_type=schedule_type,
            time=time or "",
            interval=interval or 1,
            created_at=datetime.now().isoformat(),
            next_run=self._calculate_next_run(
                ScheduledTask(
                    name=name,
                    prompt=prompt,
                    schedule_type=schedule_type,
                    time=time or "",
                    interval=interval or 1,
                )
            ),
        )

        self.tasks[name] = task
        self._save_tasks()
        return True

    def remove_task(self, name: str) -> bool:
        """Remove a task"""
        if name in self.tasks:
            del self.tasks[name]
            self._save_tasks()
            return True
        return False

    def enable_task(self, name: str) -> bool:
        """Enable a task"""
        if name in self.tasks:
            self.tasks[name].enabled = True
            self.tasks[name].next_run = self._calculate_next_run(self.tasks[name])
            self._save_tasks()
            return True
        return False

    def disable_task(self, name: str) -> bool:
        """Disable a task"""
        if name in self.tasks:
            self.tasks[name].enabled = False
            self._save_tasks()
            return True
        return False

    def run_task(self, name: str) -> Dict:
        """Run a task immediately"""
        if name not in self.tasks:
            return {"error": f"Task {name} not found"}

        task = self.tasks[name]

        # Record start
        task.last_run = datetime.now().isoformat()
        task.history.append({"timestamp": task.last_run, "status": "running"})

        # Keep only last MAX_HISTORY
        task.history = task.history[-self.MAX_HISTORY :]

        self._save_tasks()

        # Execute task
        try:
            # Here you would call NEUGI agents
            # For now, just log it
            result = {
                "status": "completed",
                "output": f"Task '{name}' executed: {task.prompt[:100]}...",
                "timestamp": datetime.now().isoformat(),
            }

            # Update history
            task.history[-1]["status"] = "completed"
            task.history[-1]["output"] = result["output"]
            self._save_tasks()

            return result

        except Exception as e:
            task.history[-1]["status"] = "failed"
            task.history[-1]["error"] = str(e)
            self._save_tasks()
            return {"error": str(e)}

    def get_task_status(self, name: str) -> Optional[Dict]:
        """Get task status"""
        if name not in self.tasks:
            return None

        task = self.tasks[name]

        return {
            "name": task.name,
            "enabled": task.enabled,
            "schedule": f"{task.schedule_type} at {task.time or 'every ' + str(task.interval)}",
            "last_run": task.last_run,
            "next_run": task.next_run,
            "history": task.history[-5:] if task.history else [],
        }

    def list_tasks(self) -> List[Dict]:
        """List all tasks"""
        return [
            {
                "name": task.name,
                "enabled": task.enabled,
                "schedule": f"{task.schedule_type} at {task.time or 'every ' + str(task.interval)}",
                "last_run": task.last_run[:19] if task.last_run else "Never",
                "next_run": task.next_run[:19] if task.next_run else "N/A",
            }
            for task in self.tasks.values()
        ]

    def start(self):
        """Start the scheduler"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        print("Scheduler started")

    def stop(self):
        """Stop the scheduler"""
        self._running = False
        print("Scheduler stopped")

    def _run_loop(self):
        """Main scheduler loop"""
        while self._running:
            now = datetime.now()

            for name, task in self.tasks.items():
                if not task.enabled:
                    continue

                if task.next_run:
                    try:
                        next_run = datetime.fromisoformat(task.next_run)
                        if now >= next_run:
                            # Time to run
                            print(f"Running task: {name}")
                            self.run_task(name)

                            # Calculate next run
                            task.next_run = self._calculate_next_run(task)
                            self._save_tasks()
                    except Exception as e:
                        print(f"Error in task {name}: {e}")

            time.sleep(60)  # Check every minute


# ========== STANDALONE CLI ==========


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Scheduler")
    parser.add_argument(
        "action", choices=["list", "add", "remove", "enable", "disable", "run", "start", "stop"]
    )
    parser.add_argument("--name", help="Task name")
    parser.add_argument("--prompt", help="Task prompt")
    parser.add_argument("--type", choices=["daily", "hourly", "minutes"], help="Schedule type")
    parser.add_argument("--time", help="Time (e.g., 08:00)")
    parser.add_argument("--interval", type=int, help="Interval (hours or minutes)")

    args = parser.parse_args()

    scheduler = NEUGIScheduler()

    if args.action == "list":
        print("\n📅 SCHEDULED TASKS")
        print("=" * 60)

        for task in scheduler.list_tasks():
            status = "✅" if task["enabled"] else "❌"
            print(f"{status} {task['name']}")
            print(f"   Schedule: {task['schedule']}")
            print(f"   Last run: {task['last_run']}")
            print(f"   Next run: {task['next_run']}")
            print()

    elif args.action == "add":
        if not all([args.name, args.prompt, args.type]):
            print("Error: --name, --prompt, and --type required")
            return

        if scheduler.add_task(args.name, args.prompt, args.type, args.time, args.interval):
            print(f"✓ Added task: {args.name}")
        else:
            print("✗ Failed to add task")

    elif args.action == "remove":
        if scheduler.remove_task(args.name):
            print(f"✓ Removed task: {args.name}")
        else:
            print("✗ Task not found")

    elif args.action == "enable":
        if scheduler.enable_task(args.name):
            print(f"✓ Enabled task: {args.name}")

    elif args.action == "disable":
        if scheduler.disable_task(args.name):
            print(f"✓ Disabled task: {args.name}")

    elif args.action == "run":
        result = scheduler.run_task(args.name)
        print(json.dumps(result, indent=2))

    elif args.action == "start":
        scheduler.start()

    elif args.action == "stop":
        scheduler.stop()


if __name__ == "__main__":
    main()
