#!/usr/bin/env python3
"""
🤖 NEUGI AUTOMATION ENGINE
=============================

Advanced automation features:
- Rule-based automation
- Event triggers
- Action chains
- Conditional logic
- Webhooks

Version: 1.0
Date: March 16, 2026
"""

import os
import re
import time
import json
import uuid
import hmac
import hashlib
import threading
import subprocess
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime

NEUGI_DIR = os.path.expanduser("~/neugi")
AUTOMATION_DIR = os.path.join(NEUGI_DIR, "automation")
os.makedirs(AUTOMATION_DIR, exist_ok=True)


class AutomationRule:
    """Automation rule definition"""

    TRIGGER_TYPES = {
        "schedule": {"label": "Schedule", "icon": "⏰"},
        "webhook": {"label": "Webhook", "icon": "🪝"},
        "file_change": {"label": "File Change", "icon": "📁"},
        "http_request": {"label": "HTTP Request", "icon": "🌐"},
        "keyword": {"label": "Keyword", "icon": "🔑"},
        "time_of_day": {"label": "Time of Day", "icon": "🕐"},
        "system_event": {"label": "System Event", "icon": "⚡"},
    }

    ACTION_TYPES = {
        "run_command": {"label": "Run Command", "icon": "⚡"},
        "send_notification": {"label": "Send Notification", "icon": "🔔"},
        "http_request": {"label": "HTTP Request", "icon": "🌐"},
        "execute_skill": {"label": "Execute Skill", "icon": "🎯"},
        "log": {"label": "Log", "icon": "📝"},
        "store_memory": {"label": "Store Memory", "icon": "🧠"},
        "trigger_workflow": {"label": "Trigger Workflow", "icon": "🔀"},
        "send_email": {"label": "Send Email", "icon": "📧"},
        "telegram_message": {"label": "Telegram Message", "icon": "💬"},
    }

    def __init__(
        self, id: str = None, name: str = "New Rule", description: str = "", enabled: bool = True
    ):
        self.id = id or str(uuid.uuid4())[:8]
        self.name = name
        self.description = description
        self.enabled = enabled
        self.trigger_type = "schedule"
        self.trigger_config = {}
        self.conditions = []
        self.actions = []
        self.schedule = None
        self.created_at = datetime.now().isoformat()
        self.last_triggered = None
        self.trigger_count = 0

    def set_trigger(self, trigger_type: str, config: Dict):
        """Set trigger"""
        self.trigger_type = trigger_type
        self.trigger_config = config

    def add_condition(self, field: str, operator: str, value: Any):
        """Add condition"""
        self.conditions.append({"field": field, "operator": operator, "value": value})

    def add_action(self, action_type: str, config: Dict):
        """Add action"""
        self.actions.append({"type": action_type, "config": config})

    def check_conditions(self, context: Dict) -> bool:
        """Check if conditions are met"""
        if not self.conditions:
            return True

        for cond in self.conditions:
            field = cond["field"]
            operator = cond["operator"]
            expected = cond["value"]
            actual = context.get(field)

            if operator == "equals":
                if actual != expected:
                    return False
            elif operator == "contains":
                if expected not in str(actual):
                    return False
            elif operator == "starts_with":
                if not str(actual).startswith(expected):
                    return False
            elif operator == "ends_with":
                if not str(actual).endswith(expected):
                    return False
            elif operator == "greater_than":
                if not (actual and float(actual) > float(expected)):
                    return False
            elif operator == "less_than":
                if not (actual and float(actual) < float(expected)):
                    return False
            elif operator == "regex":
                if not re.search(expected, str(actual)):
                    return False
            elif operator == "exists":
                if (actual is None) != expected:
                    return False

        return True

    def execute_actions(self, context: Dict) -> List[Dict]:
        """Execute actions"""
        results = []

        for action in self.actions:
            try:
                result = self._execute_action(action, context)
                results.append({"action": action["type"], "success": True, "result": result})
            except Exception as e:
                results.append({"action": action["type"], "success": False, "error": str(e)})

        return results

    def _execute_action(self, action: Dict, context: Dict) -> Any:
        """Execute single action"""
        action_type = action["type"]
        config = action["config"]

        if action_type == "run_command":
            cmd = config.get("command", "")
            for key, value in context.items():
                cmd = cmd.replace(f"{{{key}}}", str(value))
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return {"stdout": result.stdout, "returncode": result.returncode}

        elif action_type == "log":
            message = config.get("message", "")
            for key, value in context.items():
                message = message.replace(f"{{{key}}}", str(value))
            print(f"[AUTOMATION] {message}")
            return {"logged": True}

        elif action_type == "http_request":
            import requests

            method = config.get("method", "GET")
            url = config.get("url", "")
            headers = config.get("headers", {})
            body = config.get("body", "")

            for key, value in context.items():
                url = url.replace(f"{{{key}}}", str(value))
                body = body.replace(f"{{{key}}}", str(value))

            response = requests.request(
                method, url, headers=headers, json=json.loads(body) if body else None
            )
            return {"status": response.status_code, "body": response.text[:200]}

        elif action_type == "store_memory":
            from neugi_memory_v2 import MemorySystem

            memory = MemorySystem()
            key = config.get("key", "automation")
            value = config.get("value", "")
            for key, value in context.items():
                value = value.replace(f"{{{key}}}", str(value))
            memory.remember(key, value)
            return {"stored": True}

        elif action_type == "send_notification":
            return {"notification_sent": True, "message": config.get("message", "")}

        elif action_type == "trigger_workflow":
            from neugi_workflows import WorkflowRunner

            runner = WorkflowRunner()
            workflow_id = config.get("workflow_id", "")
            return runner.run(workflow_id, context)

        return {"noop": True}

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "trigger_type": self.trigger_type,
            "trigger_config": self.trigger_config,
            "conditions": self.conditions,
            "actions": self.actions,
            "schedule": self.schedule,
            "created_at": self.created_at,
            "last_triggered": self.last_triggered,
            "trigger_count": self.trigger_count,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "AutomationRule":
        rule = cls(data["id"], data["name"], data["description"], data.get("enabled", True))
        rule.trigger_type = data.get("trigger_type", "schedule")
        rule.trigger_config = data.get("trigger_config", {})
        rule.conditions = data.get("conditions", [])
        rule.actions = data.get("actions", [])
        rule.schedule = data.get("schedule")
        rule.created_at = data.get("created_at", datetime.now().isoformat())
        rule.last_triggered = data.get("last_triggered")
        rule.trigger_count = data.get("trigger_count", 0)
        return rule

    def save(self):
        """Save rule"""
        path = os.path.join(AUTOMATION_DIR, f"{self.id}.json")
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, rule_id: str) -> Optional["AutomationRule"]:
        """Load rule"""
        path = os.path.join(AUTOMATION_DIR, f"{rule_id}.json")
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return cls.from_dict(json.load(f))

    @classmethod
    def delete(cls, rule_id: str):
        """Delete rule"""
        path = os.path.join(AUTOMATION_DIR, f"{rule_id}.json")
        if os.path.exists(path):
            os.remove(path)

    @classmethod
    def list_all(cls) -> List[Dict]:
        """List all rules"""
        rules = []
        for f in os.listdir(AUTOMATION_DIR):
            if f.endswith(".json"):
                path = os.path.join(AUTOMATION_DIR, f)
                with open(path) as fp:
                    data = json.load(fp)
                    rules.append(
                        {
                            "id": data["id"],
                            "name": data["name"],
                            "description": data["description"],
                            "enabled": data["enabled"],
                            "trigger_type": data["trigger_type"],
                            "action_count": len(data.get("actions", [])),
                            "trigger_count": data.get("trigger_count", 0),
                            "last_triggered": data.get("last_triggered"),
                        }
                    )
        return sorted(rules, key=lambda x: x["name"])


class AutomationEngine:
    """Automation engine"""

    _instance = None
    _running = False
    _thread = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.rules = {}
        self.webhook_secret = None
        self._callbacks = {}
        self.load_rules()

    def load_rules(self):
        """Load all rules"""
        self.rules = {}
        for f in os.listdir(AUTOMATION_DIR):
            if f.endswith(".json"):
                rule = AutomationRule.load(f[:-5])
                if rule:
                    self.rules[rule.id] = rule

    def add_rule(self, rule: AutomationRule):
        """Add rule"""
        self.rules[rule.id] = rule
        rule.save()

    def remove_rule(self, rule_id: str):
        """Remove rule"""
        if rule_id in self.rules:
            del self.rules[rule_id]
            AutomationRule.delete(rule_id)

    def enable_rule(self, rule_id: str):
        """Enable rule"""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True
            self.rules[rule_id].save()

    def disable_rule(self, rule_id: str):
        """Disable rule"""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False
            self.rules[rule_id].save()

    def trigger(self, trigger_type: str, context: Dict, source: str = "manual") -> List[Dict]:
        """Trigger rules"""
        results = []

        for rule in self.rules.values():
            if not rule.enabled:
                continue

            if rule.trigger_type != trigger_type:
                continue

            if not rule.check_conditions(context):
                continue

            rule.last_triggered = datetime.now().isoformat()
            rule.trigger_count += 1
            rule.save()

            action_results = rule.execute_actions(context)
            results.append(
                {
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "triggered_by": source,
                    "results": action_results,
                }
            )

        return results

    def set_webhook_secret(self, secret: str):
        """Set webhook secret for verification"""
        self.webhook_secret = secret

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """Verify webhook signature"""
        if not self.webhook_secret:
            return True
        expected = hmac.new(self.webhook_secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def register_callback(self, trigger_type: str, callback: Callable):
        """Register callback for trigger type"""
        if trigger_type not in self._callbacks:
            self._callbacks[trigger_type] = []
        self._callbacks[trigger_type].append(callback)

    def start(self):
        """Start automation engine"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self._thread.start()
        print("Automation engine started")

    def stop(self):
        """Stop automation engine"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("Automation engine stopped")

    def _run_scheduler(self):
        """Run scheduler"""
        while self._running:
            now = datetime.now()

            for rule in self.rules.values():
                if not rule.enabled or rule.trigger_type != "schedule":
                    continue

                schedule = rule.schedule
                if not schedule:
                    continue

                should_trigger = False

                if schedule.get("type") == "interval":
                    interval = schedule.get("minutes", 60)
                    if rule.last_triggered:
                        last = datetime.fromisoformat(rule.last_triggered)
                        if (now - last).total_seconds() >= interval * 60:
                            should_trigger = True

                elif schedule.get("type") == "daily":
                    time_str = schedule.get("time", "00:00")
                    target_time = datetime.strptime(time_str, "%H:%M").time()
                    if (
                        now.time().hour == target_time.hour
                        and now.time().minute == target_time.minute
                    ):
                        if (
                            not rule.last_triggered
                            or rule.last_triggered[:10] != now.date().isoformat()
                        ):
                            should_trigger = True

                elif schedule.get("type") == "hourly":
                    minute = schedule.get("minute", 0)
                    if now.minute == minute:
                        if (
                            not rule.last_triggered
                            or rule.last_triggered[:13] != now.isoformat()[:13]
                        ):
                            should_trigger = True

                if should_trigger:
                    self.trigger("schedule", {"rule_id": rule.id, "source": "scheduler"})

            time.sleep(30)

    def get_status(self) -> Dict:
        """Get engine status"""
        enabled_count = sum(1 for r in self.rules.values() if r.enabled)
        return {
            "running": self._running,
            "total_rules": len(self.rules),
            "enabled_rules": enabled_count,
            "disabled_rules": len(self.rules) - enabled_count,
            "triggers": {
                "schedule": sum(1 for r in self.rules.values() if r.trigger_type == "schedule"),
                "webhook": sum(1 for r in self.rules.values() if r.trigger_type == "webhook"),
                "keyword": sum(1 for r in self.rules.values() if r.trigger_type == "keyword"),
            },
        }


class WebhookServer:
    """Webhook receiver server"""

    def __init__(self, port: int = 19910):
        self.port = port
        self.engine = AutomationEngine()

    def handle_webhook(self, rule_id: str, payload: Dict, headers: Dict = None) -> Dict:
        """Handle incoming webhook"""
        rule = AutomationRule.load(rule_id)
        if not rule:
            return {"error": "Rule not found"}

        if not rule.enabled:
            return {"error": "Rule disabled"}

        context = {
            "payload": payload,
            "headers": headers or {},
            "timestamp": datetime.now().isoformat(),
        }

        if rule.check_conditions(context):
            results = rule.execute_actions(context)
            rule.last_triggered = datetime.now().isoformat()
            rule.trigger_count += 1
            rule.save()
            return {"success": True, "results": results}

        return {"success": False, "reason": "Conditions not met"}

    def generate_webhook_url(self, rule_id: str) -> str:
        """Generate webhook URL"""
        return f"http://localhost:{self.port}/webhook/{rule_id}"


def create_example_rules():
    """Create example automation rules"""

    rule1 = AutomationRule(name="Daily Report", description="Send daily report at 8 AM")
    rule1.set_trigger("schedule", {"type": "daily", "time": "08:00"})
    rule1.add_action("send_notification", {"message": "Daily report: System running normally"})
    rule1.schedule = {"type": "daily", "time": "08:00"}
    rule1.save()

    rule2 = AutomationRule(name="Keyword Alert", description="Alert on specific keywords")
    rule2.set_trigger("keyword", {"keywords": ["error", "fail", "critical"]})
    rule2.add_action("send_notification", {"message": "Alert: {keyword} detected in {source}"})
    rule2.save()

    print("Example rules created")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Automation Engine")
    parser.add_argument("--start", action="store_true", help="Start automation engine")
    parser.add_argument("--stop", action="store_true", help="Stop automation engine")
    parser.add_argument("--list", action="store_true", help="List rules")
    parser.add_argument("--examples", action="store_true", help="Create example rules")
    parser.add_argument("--status", action="store_true", help="Show status")

    args = parser.parse_args()

    engine = AutomationEngine()

    if args.start:
        engine.start()

    if args.stop:
        engine.stop()

    if args.list:
        rules = AutomationRule.list_all()
        print(f"\n📋 Automation Rules ({len(rules)} total)\n")
        for r in rules:
            status = "✅" if r["enabled"] else "❌"
            print(f"  {status} {r['name']}")
            print(
                f"      Trigger: {r['trigger_type']} | Actions: {r['action_count']} | Runs: {r['trigger_count']}"
            )
            print()

    if args.examples:
        create_example_rules()

    if args.status:
        status = engine.get_status()
        print("\n⚙️  Automation Engine Status")
        print(f"   Running: {status['running']}")
        print(f"   Total Rules: {status['total_rules']}")
        print(f"   Enabled: {status['enabled_rules']}")


if __name__ == "__main__":
    main()
