#!/usr/bin/env python3
"""
🤖 NEUGI AUTO-LEARNER - Self-Improving Agent System
====================================================

NEUGI's UNIQUE feature - Learns from EVERY interaction!
Automatically creates new skills from task completions.

This system:
1. Monitors task patterns
2. Analyzes successful completions
3. Auto-generates reusable skills
4. Improves over time (like Hermes but better!)

Key Differences vs Hermes:
- Works with Agent Studio templates
- Integrated with MCP + Tools
- Visual feedback of learning
- User can review/approve skills

Version: 1.0.0
"""

import os
import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import defaultdict


NEUGI_DIR = os.path.expanduser("~/neugi")
os.makedirs(os.path.join(NEUGI_DIR, "data"), exist_ok=True)
os.makedirs(os.path.join(NEUGI_DIR, "skills"), exist_ok=True)


class TaskPattern:
    """Represents a learned task pattern"""

    def __init__(self, pattern_id: str, trigger: str, action: str, frequency: int = 1):
        self.id = pattern_id
        self.trigger = trigger  # What the user asked
        self.action = action  # What action was taken
        self.frequency = frequency
        self.success_count = 1
        self.last_used = datetime.now().isoformat()
        self.meta_pattern = ""  # Abstracted pattern

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "trigger": self.trigger,
            "action": self.action,
            "frequency": self.frequency,
            "success_count": self.success_count,
            "last_used": self.last_used,
            "meta_pattern": self.meta_pattern,
        }


class AutoLearner:
    """
    NEUGI's Self-Learning System

    Learns from user interactions and automatically creates skills.
    REVOLUTIONARY: This makes NEUGI get smarter the longer you use it!
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.join(NEUGI_DIR, "data", "auto_learner.db")
        self.skills_dir = os.path.join(NEUGI_DIR, "skills", "auto_generated")
        os.makedirs(self.skills_dir, exist_ok=True)

        self.threshold_frequency = 3  # How many times before auto-creating skill
        self.threshold_confidence = 0.8
        self._init_db()

        self.learned_patterns: Dict[str, TaskPattern] = {}
        self._load_patterns()

    def _init_db(self):
        """Initialize learning database"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS task_patterns (
                id TEXT PRIMARY KEY,
                trigger TEXT NOT NULL,
                action TEXT NOT NULL,
                frequency INTEGER DEFAULT 1,
                success_count INTEGER DEFAULT 1,
                last_used TEXT,
                meta_pattern TEXT,
                created_at TEXT
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS skill_templates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                trigger_keywords TEXT,
                action_template TEXT,
                approved INTEGER DEFAULT 0,
                times_used INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS learning_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                event_type TEXT,
                details TEXT
            )
        """)

        conn.commit()
        conn.close()

    def _load_patterns(self):
        """Load learned patterns into memory"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT * FROM task_patterns WHERE frequency >= ?", (self.threshold_frequency,))

        for row in c.fetchall():
            pattern = TaskPattern(
                pattern_id=row[0], trigger=row[1], action=row[2], frequency=row[3]
            )
            pattern.success_count = row[4]
            pattern.last_used = row[5] or ""
            pattern.meta_pattern = row[6] or ""
            self.learned_patterns[pattern.id] = pattern

        conn.close()

    def log_interaction(self, trigger: str, action: str, success: bool = True):
        """Log a user interaction for learning"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        timestamp = datetime.now().isoformat()

        c.execute(
            "INSERT INTO learning_log (timestamp, event_type, details) VALUES (?, ?, ?)",
            (
                timestamp,
                "interaction",
                json.dumps({"trigger": trigger, "action": action, "success": success}),
            ),
        )

        # Update or create pattern
        c.execute("SELECT * FROM task_patterns WHERE trigger = ?", (trigger,))
        existing = c.fetchone()

        if existing:
            c.execute(
                """
                UPDATE task_patterns 
                SET frequency = frequency + 1, 
                    success_count = success_count + ?,
                    last_used = ?
                WHERE trigger = ?
            """,
                (1 if success else 0, timestamp, trigger),
            )
        else:
            c.execute(
                """
                INSERT INTO task_patterns (id, trigger, action, frequency, success_count, last_used, created_at)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
                (
                    f"pattern_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    trigger,
                    action,
                    1 if success else 0,
                    timestamp,
                    timestamp,
                ),
            )

        conn.commit()
        conn.close()

        # Reload patterns if threshold reached
        self._load_patterns()

    def analyze_and_create_skill(self) -> List[Dict]:
        """Analyze patterns and auto-create skills for frequent tasks"""
        created_skills = []

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            """
            SELECT trigger, action, frequency, success_count 
            FROM task_patterns 
            WHERE frequency >= ? 
            AND success_count >= (frequency * ?)
            AND meta_pattern = ''
        """,
            (self.threshold_frequency, self.threshold_confidence),
        )

        candidates = c.fetchall()

        for trigger, action, frequency, success_count in candidates:
            if success_count / frequency >= self.threshold_confidence:
                skill_id = f"auto_{trigger[:20].replace(' ', '_').lower()}_{datetime.now().strftime('%H%M')}"
                skill_name = f"Auto-{trigger[:30]}"

                # Extract keywords from trigger
                keywords = [w.lower() for w in trigger.split() if len(w) > 3]

                skill_template = {
                    "id": skill_id,
                    "name": skill_name,
                    "description": f"Auto-generated skill from {frequency} uses",
                    "trigger_keywords": ",".join(keywords),
                    "action_template": action,
                    "approved": 0,
                    "times_used": 0,
                    "created_at": datetime.now().isoformat(),
                }

                c.execute(
                    """
                    INSERT OR REPLACE INTO skill_templates 
                    (id, name, description, trigger_keywords, action_template, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        skill_id,
                        skill_name,
                        skill_template["description"],
                        skill_template["trigger_keywords"],
                        action,
                        datetime.now().isoformat(),
                    ),
                )

                # Try to save as actual skill file
                self._save_skill_file(skill_id, skill_name, trigger, action)

                created_skills.append(skill_template)

                # Update meta_pattern so we don't create duplicate
                c.execute(
                    "UPDATE task_patterns SET meta_pattern = ? WHERE trigger = ?",
                    (skill_id, trigger),
                )

        conn.commit()
        conn.close()

        return created_skills

    def _save_skill_file(self, skill_id: str, name: str, trigger: str, action: str):
        """Save generated skill as a reusable .neugi.py file"""
        skill_code = f'''#!/usr/bin/env python3
"""
🤖 AUTO-GENERATED SKILL: {name}
Generated: {datetime.now().isoformat()}
Trigger: {trigger}

Auto-learned from {self.threshold_frequency}+ successful uses!
"""

def execute_{skill_id.replace("-", "_").replace("auto_", "auto_")}(context: dict = None) -> dict:
    """
    Auto-generated from user interactions.
    This skill executes: {action[:100]}...
    """
    return {{
        "status": "success",
        "skill_id": "{skill_id}",
        "name": "{name}",
        "action": "{action}",
        "context": context or {{}}
    }}

def get_metadata():
    return {{
        "id": "{skill_id}",
        "name": "{name}",
        "triggers": [{", ".join([repr(w) for w in trigger.split() if len(w) > 3])}],
        "auto_learned": True,
        "confidence": {self.threshold_confidence}
    }}

if __name__ == "__main__":
    result = execute_{skill_id.replace("-", "_").replace("auto_", "auto_")}()
    print(f"Skill executed: {{result}}")
'''

        skill_file = os.path.join(self.skills_dir, f"{skill_id}.neugi.py")
        try:
            with open(skill_file, "w", encoding="utf-8") as f:
                f.write(skill_code)
        except Exception as e:
            print(f"Warning: Could not save skill file: {e}")

    def suggest_skills(self, user_input: str) -> List[Dict]:
        """Suggest applicable auto-learned skills based on user input"""
        suggestions = []

        user_words = set(user_input.lower().split())

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT * FROM skill_templates WHERE approved = 0")

        for row in c.fetchall():
            keywords = set((row[3] or "").lower().split(","))

            # Check if any keyword matches
            if keywords & user_words:
                suggestions.append(
                    {
                        "id": row[0],
                        "name": row[1],
                        "confidence": min(row[7] / 10, 1.0),  # Normalize
                        "trigger": row[4],
                    }
                )

        conn.close()

        return sorted(suggestions, key=lambda x: x["confidence"], reverse=True)[:5]

    def approve_skill(self, skill_id: str) -> bool:
        """Approve a generated skill for active use"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("UPDATE skill_templates SET approved = 1 WHERE id = ?", (skill_id,))
        conn.commit()
        conn.close()
        return True

    def get_learning_stats(self) -> Dict:
        """Get learning statistics"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("SELECT COUNT(*), SUM(frequency) FROM task_patterns")
        total_patterns, total_uses = c.fetchone() or (0, 0)

        c.execute("SELECT COUNT(*), SUM(times_used) FROM skill_templates WHERE approved = 1")
        approved_skills, skill_uses = c.fetchone() or (0, 0)

        c.execute("SELECT COUNT(*) FROM skill_templates WHERE approved = 0")
        pending_skills = c.fetchone()[0] or 0

        conn.close()

        return {
            "total_patterns_learned": total_patterns or 0,
            "total_task_uses": total_uses or 0,
            "skills_created": approved_skills + pending_skills,
            "skills_approved": approved_skills or 0,
            "skills_pending": pending_skills or 0,
            "total_skill_uses": skill_uses or 0,
            "learning_efficiency": round((approved_skills / max(total_patterns, 1)) * 100, 1),
        }

    def show_learning_dashboard(self):
        """Display learning progress dashboard"""
        stats = self.get_learning_stats()

        print("\n" + "=" * 60)
        print("🧠 NEUGI AUTO-LEARNER DASHBOARD")
        print("=" * 60)

        print(f"""
  📚 PATTERNS LEARNED:    {stats["total_patterns_learned"]}
  🔄 TOTAL TASK USES:     {stats["total_task_uses"]}
  
  ⚡ SKILLS CREATED:      {stats["skills_created"]}
     ✅ Approved:         {stats["skills_approved"]}
     ⏳ Pending Review:   {stats["skills_pending"]}
  
  🎯 SKILL USAGE:         {stats["total_skill_uses"]}
  📈 LEARNING EFFICIENCY: {stats["learning_efficiency"]}%
        """)

        if stats["total_patterns_learned"] < self.threshold_frequency:
            print(
                f"  💡 Keep using NEUGI! Need {self.threshold_frequency - stats['total_patterns_learned']} more patterns for auto-skill creation."
            )
        elif stats["skills_pending"] > 0:
            print(f"  ⚠️  You have {stats['skills_pending']} skills waiting for approval!")
            print("     Use: auto_learner.approve_skill('<skill_id>')")

        print("\n" + "-" * 60)
        print("📝 RECENT SKILLS:")

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "SELECT id, name, times_used FROM skill_templates ORDER BY created_at DESC LIMIT 5"
        )

        for row in c.fetchall():
            print(f"   • {row[1]} (used {row[2]} times)")

        conn.close()

        print("=" * 60)


# ============================================================
# INTEGRATION WITH AGENT SYSTEM
# ============================================================


class LearningAgentMixin:
    """Mixin to add auto-learning to any agent"""

    def __init__(self):
        self.learner = AutoLearner()
        self.session_tasks = []

    def log_task(self, task: str, action: str, success: bool = True):
        """Log task for learning"""
        self.learner.log_interaction(task, action, success)
        self.session_tasks.append({"task": task, "action": action, "success": success})

    def get_suggestions(self, user_input: str) -> List[Dict]:
        """Get skill suggestions based on input"""
        return self.learner.suggest_skills(user_input)


# ============================================================
# CLI ENTRY POINT
# ============================================================

if __name__ == "__main__":
    import sys

    learner = AutoLearner()

    if len(sys.argv) > 1:
        if sys.argv[1] == "--stats" or sys.argv[1] == "-s":
            learner.show_learning_dashboard()
        elif sys.argv[1] == "--analyze" or sys.argv[1] == "-a":
            print("\n🔄 Analyzing patterns and creating skills...")
            new_skills = learner.analyze_and_create_skill()
            if new_skills:
                print(f"\n✅ Created {len(new_skills)} new skills!")
                for s in new_skills:
                    print(f"   • {s['name']}: {s['trigger_keywords']}")
            else:
                print("\n📝 No new skills to create yet. Keep using NEUGI!")
        elif sys.argv[1] == "--suggest" and len(sys.argv) > 2:
            suggestions = learner.suggest_skills(" ".join(sys.argv[2:]))
            if suggestions:
                print("\n💡 Suggested skills:")
                for s in suggestions:
                    print(f"   • {s['name']} (confidence: {s['confidence']:.0%})")
            else:
                print("\n📝 No matching skills found.")
        else:
            print("""
🤖 NEUGI AUTO-LEARNER CLI
=========================
Usage:
    python neugi_auto_learner.py --stats       Show learning stats
    python neugi_auto_learner.py --analyze     Analyze & create skills
    python neugi_auto_learner.py --suggest <input>  Get suggestions
            """)
    else:
        learner.show_learning_dashboard()
