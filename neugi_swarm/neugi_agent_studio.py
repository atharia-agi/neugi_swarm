#!/usr/bin/env python3
"""
🤖 NEUGI AGENT STUDIO - User-Friendly Agent Creation
======================================================

Platform provides TEMPLATES - Users create & customize their own agents!
FULL INTEGRATION with existing AgentManager + ToolManager + Memory!

Features:
- Pre-built templates for different use cases
- Interactive CLI wizard for agent creation
- Tool selection from available pool
- Role-based agent configuration
- INTEGRATES with 9 existing agents (aurora, cipher, nova, etc)
- Shared memory, tools, and security

Usage:
    from neugi_agent_studio import AgentStudio, TEMPLATES
    studio = AgentStudio()
    studio.create_agent_interactive()
    # Or use the integrated method:
    studio.create_integrated_agent("my_coder", "developer", ["code_execute", "llm_think"])
"""

import os
import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

try:
    from neugi_swarm_agents import AgentManager, Agent, AgentRole, AgentStatus
    from neugi_swarm_tools import ToolManager
    from neugi_swarm_memory import MemoryManager

    AGENT_IMPORT = True
except ImportError:
    AGENT_IMPORT = False
    AgentManager = None


NEUGI_DIR = os.path.expanduser("~/neugi")
os.makedirs(os.path.join(NEUGI_DIR, "data"), exist_ok=True)


# ============================================================
# AVAILABLE TOOLS - Users pick from here
# ============================================================

AVAILABLE_TOOLS = {
    "web": {
        "web_search": "Search the web for information",
        "web_fetch": "Fetch content from URLs",
        "web_browse": "Browse websites interactively",
    },
    "code": {
        "code_execute": "Execute Python code",
        "code_debug": "Debug and fix code",
        "file_read": "Read files from disk",
        "file_write": "Write files to disk",
    },
    "ai": {
        "llm_think": "Use LLM for reasoning",
        "llm_generate": "Generate content with LLM",
    },
    "data": {
        "json_parse": "Parse JSON data",
        "csv_analyze": "Analyze CSV files",
        "db_query": "Query databases",
    },
    "comm": {
        "send_telegram": "Send messages via Telegram",
        "send_discord": "Send messages via Discord",
        "send_email": "Send emails",
    },
    "media": {
        "image_generate": "Generate images",
        "audio_speak": "Text-to-speech",
    },
    "system": {
        "shell_execute": "Execute shell commands",
        "process_run": "Run system processes",
    },
}


# ============================================================
# ROLE DEFINITIONS
# ============================================================

AGENT_ROLES = {
    "researcher": {
        "name": "Researcher",
        "description": "Research, analyze, and gather information",
        "default_tools": ["web_search", "web_fetch", "llm_think"],
        "color": "\033[96m",
    },
    "coder": {
        "name": "Coder",
        "description": "Write, debug, and build code",
        "default_tools": ["code_execute", "file_write", "llm_think"],
        "color": "\033[92m",
    },
    "creator": {
        "name": "Creator",
        "description": "Design, create, and generate content",
        "default_tools": ["image_generate", "llm_generate", "file_write"],
        "color": "\033[95m",
    },
    "analyst": {
        "name": "Analyst",
        "description": "Analyze data, visualize, and report",
        "default_tools": ["json_parse", "csv_analyze", "llm_think"],
        "color": "\033[93m",
    },
    "strategist": {
        "name": "Strategist",
        "description": "Plan, decide, and optimize strategies",
        "default_tools": ["llm_think", "llm_generate"],
        "color": "\033[91m",
    },
    "security": {
        "name": "Security",
        "description": "Scan, audit, and protect systems",
        "default_tools": ["code_debug", "web_fetch", "llm_think"],
        "color": "\033[91m",
    },
    "social": {
        "name": "Social",
        "description": "Post, engage, and schedule content",
        "default_tools": ["send_telegram", "send_discord", "llm_generate"],
        "color": "\033[94m",
    },
    "writer": {
        "name": "Writer",
        "description": "Write, edit, and create documents",
        "default_tools": ["llm_generate", "file_write", "file_read"],
        "color": "\033[97m",
    },
    "custom": {
        "name": "Custom",
        "description": "Build your own custom agent",
        "default_tools": [],
        "color": "\033[90m",
    },
}


# ============================================================
# AGENT TEMPLATES - Pre-built for users to customize
# ============================================================

TEMPLATES = {
    "blank": {
        "id": "blank",
        "name": "Blank Agent",
        "description": "Start from scratch - create your own agent",
        "role": "custom",
        "capabilities": [],
        "tools": [],
        "personality": "neutral",
    },
    "developer": {
        "id": "developer",
        "name": "Developer Agent",
        "description": "Full-stack developer for coding tasks",
        "role": "coder",
        "capabilities": ["code", "debug", "build", "test"],
        "tools": ["code_execute", "file_read", "file_write", "llm_think"],
        "personality": "practical",
    },
    "researcher": {
        "id": "researcher",
        "name": "Researcher Agent",
        "description": "Research assistant for information gathering",
        "role": "researcher",
        "capabilities": ["search", "fetch", "analyze", "summarize"],
        "tools": ["web_search", "web_fetch", "llm_think"],
        "personality": "inquisitive",
    },
    "designer": {
        "id": "designer",
        "name": "Designer Agent",
        "description": "Creative designer for visual content",
        "role": "creator",
        "capabilities": ["design", "create", "generate", "edit"],
        "tools": ["image_generate", "llm_generate", "file_write"],
        "personality": "creative",
    },
    "analyst": {
        "id": "analyst",
        "name": "Analyst Agent",
        "description": "Data analyst for charts and reports",
        "role": "analyst",
        "capabilities": ["analyze", "visualize", "report", "present"],
        "tools": ["json_parse", "csv_analyze", "llm_think"],
        "personality": "analytical",
    },
    "helper": {
        "id": "helper",
        "name": "General Helper",
        "description": "General purpose assistant for everyday tasks",
        "role": "custom",
        "capabilities": ["assist", "explain", "summarize", "respond"],
        "tools": ["llm_think", "web_fetch", "file_read"],
        "personality": "helpful",
    },
    "writer": {
        "id": "writer",
        "name": "Writer Agent",
        "description": "Writing assistant for documents and content",
        "role": "writer",
        "capabilities": ["write", "edit", "proofread", "create"],
        "tools": ["llm_generate", "file_write", "file_read"],
        "personality": "expressive",
    },
    "guardian": {
        "id": "guardian",
        "name": "Security Guardian",
        "description": "Security-focused agent for auditing",
        "role": "security",
        "capabilities": ["scan", "audit", "protect", "detect"],
        "tools": ["code_debug", "web_fetch", "llm_think"],
        "personality": "vigilant",
    },
}


# ============================================================
# USER AGENT CREATOR - Interactive CLI
# ============================================================


class AgentStudio:
    """User-friendly agent creation studio"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.join(NEUGI_DIR, "data", "user_agents.db")
        self._init_db()

    def _init_db(self):
        """Initialize user agent database"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS user_agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                template_id TEXT,
                role TEXT,
                capabilities TEXT,
                tools TEXT,
                personality TEXT,
                description TEXT,
                created_at TEXT,
                tasks_completed INTEGER DEFAULT 0,
                xp INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()

    def list_templates(self) -> Dict:
        """List all available templates"""
        return TEMPLATES

    def get_template(self, template_id: str) -> Optional[Dict]:
        """Get specific template"""
        return TEMPLATES.get(template_id)

    def create_from_template(self, template_id: str, custom_name: str = None) -> bool:
        """Create agent from template with user customization"""
        template = TEMPLATES.get(template_id)
        if not template:
            print(f"Template '{template_id}' not found!")
            return False

        agent_id = f"user_{template_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        name = custom_name or template["name"]

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO user_agents 
            (id, name, template_id, role, capabilities, tools, personality, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                agent_id,
                name,
                template_id,
                template["role"],
                json.dumps(template["capabilities"]),
                json.dumps(template["tools"]),
                template["personality"],
                template["description"],
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        conn.close()

        print(f"✅ Agent '{name}' created from template '{template['name']}'!")
        return True

    def customize_agent(self, agent_id: str, **updates) -> bool:
        """Update agent configuration"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        for key, value in updates.items():
            if key in ["capabilities", "tools"]:
                value = json.dumps(value) if isinstance(value, list) else value
            c.execute(f"UPDATE user_agents SET {key} = ? WHERE id = ?", (value, agent_id))

        conn.commit()
        conn.close()
        return True

    def add_tool_to_agent(self, agent_id: str, tool: str) -> bool:
        """Add a tool to existing agent"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT tools FROM user_agents WHERE id = ?", (agent_id,))
        row = c.fetchone()

        if not row:
            conn.close()
            return False

        tools = json.loads(row[0])
        if tool not in tools:
            tools.append(tool)
            c.execute(
                "UPDATE user_agents SET tools = ? WHERE id = ?", (json.dumps(tools), agent_id)
            )
            conn.commit()

        conn.close()
        return True

    def list_user_agents(self) -> List[Dict]:
        """List all user-created agents"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT * FROM user_agents ORDER BY created_at DESC")
        columns = [desc[0] for desc in c.description]
        rows = c.fetchall()
        conn.close()

        return [dict(zip(columns, row)) for row in rows]

    def delete_agent(self, agent_id: str) -> bool:
        """Delete a user agent"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("DELETE FROM user_agents WHERE id = ?", (agent_id,))
        conn.commit()
        conn.close()
        return True

    # ============================================================
    # INTERACTIVE CLI WIZARD
    # ============================================================

    def create_agent_interactive(self):
        """Interactive CLI wizard for agent creation"""
        print("\n" + "=" * 50)
        print("🤖 NEUGI AGENT STUDIO - Create Your Agent")
        print("=" * 50)
        print("\n📋 STEP 1: Choose a Template")
        print("-" * 40)

        for tid, tpl in TEMPLATES.items():
            print(f"  [{tid:12}] {tpl['name']}")
            print(f"             {tpl['description']}")

        print("\n📝 STEP 2: Customization")
        print("-" * 40)

        template_id = input("Choose template (or 'blank' to start fresh): ").strip().lower()
        if template_id not in TEMPLATES:
            template_id = "blank"

        template = TEMPLATES[template_id]
        name = input(f"Agent name [{template['name']}]: ").strip()
        if not name:
            name = template["name"]

        description = input(f"Description [{template['description']}]: ").strip()
        if not description:
            description = template["description"]

        role = template["role"]
        if role == "custom":
            print("\n🔧 Available Roles:")
            for rid, rinfo in AGENT_ROLES.items():
                print(f"  [{rid:12}] {rinfo['name']}: {rinfo['description']}")
            role = input("Choose role: ").strip().lower()
            if role not in AGENT_ROLES:
                role = "custom"

        print(f"\n🛠️  Available Tools (comma-separated, empty for defaults):")
        print("-" * 40)
        for cat, tools in AVAILABLE_TOOLS.items():
            print(f"  {cat}: {', '.join(tools.keys())}")

        selected_tools_input = input("Select tools: ").strip()
        if selected_tools_input:
            tools = [t.strip() for t in selected_tools_input.split(",")]
        else:
            tools = template["default_tools"]

        print("\n🎭 Available Personalities:")
        print("  [neutral] Most versatile")
        print("  [helpful] Friendly and supportive")
        print("  [practical] Goal-oriented, efficient")
        print("  [creative] Imaginative, artistic")
        print("  [analytical] Logical, detail-focused")
        personality = input("Choose personality [neutral]: ").strip().lower() or "neutral"

        agent_id = f"user_{role}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO user_agents 
            (id, name, template_id, role, capabilities, tools, personality, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                agent_id,
                name,
                template_id,
                role,
                json.dumps(template["capabilities"]),
                json.dumps(tools),
                personality,
                description,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        conn.close()

        print("\n" + "=" * 50)
        print(f"✅ SUCCESS! Agent '{name}' created!")
        print(f"   Role: {role}")
        print(f"   Tools: {', '.join(tools)}")
        print(f"   Personality: {personality}")
        print("=" * 50)

    def show_dashboard(self):
        """Show user agent dashboard"""
        agents = self.list_user_agents()

        print("\n" + "=" * 60)
        print("🤖 YOUR NEUGI AGENTS")
        print("=" * 60)

        if not agents:
            print("\n📭 No agents yet! Create your first agent:")
            print("   python -m neugi_agent_studio --create")
            return

        for a in agents:
            tools = json.loads(a["tools"]) if isinstance(a["tools"], str) else a["tools"]
            print(f"\n  👤 {a['name']} (Level {a['xp'] // 100 + 1})")
            print(f"     Role: {a['role']}")
            print(f"     Description: {a['description']}")
            print(f"     Tasks: {a['tasks_completed']} | XP: {a['xp']}")
            print(f"     Tools: {', '.join(tools[:5])}")

        print("\n" + "-" * 60)
        print("📋 Available Templates:")
        for tid, tpl in TEMPLATES.items():
            print(f"   {tid}: {tpl['name']}")

    # ============================================================
    # FULL INTEGRATION WITH AGENTMANAGER
    # ============================================================

    def create_integrated_agent(
        self,
        name: str,
        template_id: str = "blank",
        tools: List[str] = None,
        capabilities: List[str] = None,
        description: str = None,
    ) -> Optional[str]:
        """
        Create agent that integrates directly with existing AgentManager.
        This agent will work alongside the 9 built-in agents!
        """
        if not AGENT_IMPORT:
            print("⚠️  AgentManager not available. Creating local agent only.")
            return self._create_local_agent(name, template_id, tools, capabilities, description)

        template = TEMPLATES.get(template_id, TEMPLATES["blank"])
        role_str = template.get("role", "custom")

        try:
            role = AgentRole[role_str.upper()]
        except KeyError:
            role = AgentRole.CUSTOM

        tools = tools or template.get("default_tools", [])
        capabilities = capabilities or template.get("capabilities", [])
        description = description or template.get("description", "")

        agent_id = (
            f"user_{name.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO user_agents 
            (id, name, template_id, role, capabilities, tools, personality, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                agent_id,
                name,
                template_id,
                role_str,
                json.dumps(capabilities),
                json.dumps(tools),
                template.get("personality", "neutral"),
                description,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        conn.close()

        if AGENT_IMPORT and AgentManager:
            try:
                manager = AgentManager()
                agent_id_db = f"user_{name.lower().replace(' ', '_')}"

                existing = manager.get(agent_id_db)
                if existing:
                    agent_id_db = f"{agent_id_db}_{datetime.now().strftime('%H%M%S')}"

                agent = Agent(
                    id=agent_id_db,
                    name=name,
                    role=role,
                    status=AgentStatus.IDLE,
                    capabilities=capabilities,
                    tools=tools,
                )
                manager.agents[agent_id_db] = agent
                manager._save_agent(agent)

                print(f"✅ Agent '{name}' registered to AgentManager!")
                print(f"   ID: {agent_id_db}")
                print(f"   Tools: {', '.join(tools)}")
                print(f"   Can now work with aurora, cipher, nova, and other agents!")

                return agent_id_db
            except Exception as e:
                print(f"⚠️  Could not register to AgentManager: {e}")
                return agent_id

        return agent_id

    def _create_local_agent(self, name, template_id, tools, capabilities, description):
        """Fallback: create agent in local DB only"""
        template = TEMPLATES.get(template_id, TEMPLATES["blank"])
        agent_id = (
            f"local_{name.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO user_agents 
            (id, name, template_id, role, capabilities, tools, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                agent_id,
                name,
                template_id,
                template.get("role", "custom"),
                json.dumps(capabilities or []),
                json.dumps(tools or []),
                description or template.get("description", ""),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        conn.close()

        print(f"✅ Agent '{name}' created (local mode)")
        return agent_id

    def run_user_agent(self, agent_name: str, task: str) -> Dict:
        """Run a user-created agent using the integrated AgentManager"""
        if not AGENT_IMPORT or not AgentManager:
            return {"error": "AgentManager not available"}

        manager = AgentManager()
        agent_id = f"user_{agent_name.lower().replace(' ', '_')}"

        result = manager.run(agent_id, task)
        return result

    def list_all_agents(self) -> Dict:
        """List ALL agents - built-in + user-created"""
        result = {"built_in": [], "user_created": []}

        if AGENT_IMPORT and AgentManager:
            try:
                manager = AgentManager()
                for agent in manager.list():
                    result["built_in"].append(
                        {
                            "id": agent.id,
                            "name": agent.name,
                            "role": agent.role.value,
                            "status": agent.status.value,
                            "level": agent.level,
                        }
                    )
            except Exception as e:
                print(f"⚠️  Could not load built-in agents: {e}")

        result["user_created"] = self.list_user_agents()
        return result


# ============================================================
# CLI ENTRY POINT
# ============================================================

if __name__ == "__main__":
    import sys

    studio = AgentStudio()

    if len(sys.argv) > 1:
        if sys.argv[1] == "--create" or sys.argv[1] == "-c":
            studio.create_agent_interactive()
        elif sys.argv[1] == "--list" or sys.argv[1] == "-l":
            studio.show_dashboard()
        elif sys.argv[1] == "--templates":
            print("\n📋 Available Templates:")
            for tid, tpl in TEMPLATES.items():
                print(f"  {tid}: {tpl['name']} - {tpl['description']}")
        elif sys.argv[1] == "--delete" and len(sys.argv) > 2:
            studio.delete_agent(sys.argv[2])
            print(f"✅ Agent deleted!")
        else:
            print("""
🤖 NEUGI AGENT STUDIO CLI
=========================
Usage:
    python neugi_agent_studio.py --create    Create new agent (interactive)
    python neugi_agent_studio.py --list      Show your agents
    python neugi_agent_studio.py --templates List templates
    python neugi_agent_studio.py --delete <id> Delete an agent
            """)
    else:
        studio.show_dashboard()
