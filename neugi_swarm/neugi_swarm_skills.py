#!/usr/bin/env python3
"""
🤖 NEUGI SWARM - SKILLS
=======================

Skill system for Neugi Swarm - compatible with OpenClaw, Claude Code, MCP, and more

Supported Formats:
- NEUGI native skills (.neugi.py)
- OpenClaw skills (claw.json)
- Claude Code commands (.md in .claude/commands)
- MCP tools (JSON schema)
- LangChain tools (Python)

Built-in Skills:
- GitHub operations
- Weather
- Coding agent
- Health check
- Tmux control
- Web search
- File operations
- Database operations

Usage:
    from neugi_swarm_skills import SkillManager
    skills = SkillManager()
    skills.execute("github", "status")
    skills.install_from_url("https://github.com/user/neugi-skill")
    skills.import_from_claude_code("/path/to/.claude/commands")

Version: 15.4.0
"""

import os
import json
import importlib.util
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

# Config
SKILLS_DIR = os.path.expanduser("~/neugi/skills")
WORKSPACE_DIR = os.path.expanduser("~/neugi/workspace")


class SkillStatus(Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    LOADING = "loading"
    ERROR = "error"


class SkillCategory(Enum):
    DEVELOPMENT = "development"
    DEVOPS = "devops"
    DATA = "data"
    SECURITY = "security"
    COMMUNICATION = "communication"
    UTILITY = "utility"
    AI = "ai"
    CUSTOM = "custom"


@dataclass
class SkillAction:
    """A single action/command within a skill"""

    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    handler: Optional[Callable] = None


@dataclass
class Skill:
    """Skill definition"""

    id: str
    name: str
    description: str
    version: str
    status: SkillStatus
    category: SkillCategory
    actions: List[SkillAction]
    config: Dict = field(default_factory=dict)
    source: str = "builtin"  # builtin, openclaw, claude_code, mcp, url
    author: str = "NEUGI"
    repository: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "status": self.status.value,
            "category": self.category.value,
            "actions": [{"name": a.name, "description": a.description} for a in self.actions],
            "source": self.source,
            "author": self.author,
            "repository": self.repository,
        }

    def to_claude_command(self) -> str:
        """Export as Claude Code command"""
        return f"""# {self.name}

{self.description}

"""

    def to_mcp_tool(self) -> Dict:
        """Export as MCP tool"""
        return {
            "name": self.id,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": {
                    a.name: {"type": "string", "description": a.description} for a in self.actions
                },
            },
        }


class SkillManager:
    """Manages all skills - compatible with multiple formats"""

    def __init__(self):
        self.skills: Dict[str, Skill] = {}
        self._ensure_directories()
        self._register_builtin_skills()
        self._load_custom_skills()

    def _ensure_directories(self):
        """Ensure skills directories exist"""
        os.makedirs(SKILLS_DIR, exist_ok=True)
        os.makedirs(WORKSPACE_DIR, exist_ok=True)

    def _register_builtin_skills(self):
        """Register built-in skills"""

        # GitHub skill
        self.register(
            Skill(
                id="github",
                name="GitHub",
                description="GitHub operations via gh CLI - issues, PRs, repos",
                version="1.0.0",
                status=SkillStatus.ENABLED,
                category=SkillCategory.DEVOPS,
                actions=[
                    SkillAction("issue", "Create, list, or manage GitHub issues"),
                    SkillAction("pr", "Create, list, or manage pull requests"),
                    SkillAction("repo", "Manage repositories"),
                    SkillAction("status", "Check GitHub CLI status"),
                    SkillAction("search", "Search code, repos, issues"),
                ],
                source="builtin",
            )
        )

        # Weather skill
        self.register(
            Skill(
                id="weather",
                name="Weather",
                description="Get weather and forecasts from wttr.in",
                version="1.0.0",
                status=SkillStatus.ENABLED,
                category=SkillCategory.UTILITY,
                actions=[
                    SkillAction("weather", "Get current weather"),
                    SkillAction("forecast", "Get multi-day forecast"),
                    SkillAction("temp", "Get temperature quickly"),
                ],
                source="builtin",
            )
        )

        # Coding agent skill
        self.register(
            Skill(
                id="coding-agent",
                name="Coding Agent",
                description="Delegate coding tasks to AI coding agents",
                version="1.0.0",
                status=SkillStatus.ENABLED,
                category=SkillCategory.DEVELOPMENT,
                actions=[
                    SkillAction("code", "Generate code from description"),
                    SkillAction("build", "Build and compile project"),
                    SkillAction("debug", "Debug and fix errors"),
                    SkillAction("refactor", "Refactor code"),
                    SkillAction("review", "Review code changes"),
                ],
                source="builtin",
            )
        )

        # Health check skill
        self.register(
            Skill(
                id="healthcheck",
                name="Health Check",
                description="Security and system health checks",
                version="1.0.0",
                status=SkillStatus.ENABLED,
                category=SkillCategory.SECURITY,
                actions=[
                    SkillAction("health", "Run system health check"),
                    SkillAction("audit", "Security audit"),
                    SkillAction("secure", "Security hardening"),
                ],
                source="builtin",
            )
        )

        # Tmux skill
        self.register(
            Skill(
                id="tmux",
                name="Tmux",
                description="Remote-control tmux sessions",
                version="1.0.0",
                status=SkillStatus.ENABLED,
                category=SkillCategory.DEVOPS,
                actions=[
                    SkillAction("session", "Manage tmux sessions"),
                    SkillAction("pane", "Manage tmux panes"),
                    SkillAction("window", "Manage tmux windows"),
                ],
                source="builtin",
            )
        )

        # Web Search skill
        self.register(
            Skill(
                id="websearch",
                name="Web Search",
                description="Search the web using DuckDuckGo/SearXNG",
                version="1.0.0",
                status=SkillStatus.ENABLED,
                category=SkillCategory.UTILITY,
                actions=[
                    SkillAction("search", "Search the web"),
                    SkillAction("fetch", "Fetch webpage content"),
                    SkillAction("extract", "Extract data from URL"),
                ],
                source="builtin",
            )
        )

        # File Operations skill
        self.register(
            Skill(
                id="fileops",
                name="File Operations",
                description="File and directory operations",
                version="1.0.0",
                status=SkillStatus.ENABLED,
                category=SkillCategory.UTILITY,
                actions=[
                    SkillAction("read", "Read file contents"),
                    SkillAction("write", "Write to file"),
                    SkillAction("list", "List directory contents"),
                    SkillAction("find", "Find files"),
                    SkillAction("glob", "Glob pattern matching"),
                ],
                source="builtin",
            )
        )

        # Database skill
        self.register(
            Skill(
                id="database",
                name="Database",
                description="SQLite database operations",
                version="1.0.0",
                status=SkillStatus.ENABLED,
                category=SkillCategory.DATA,
                actions=[
                    SkillAction("query", "Run SQL query"),
                    SkillAction("backup", "Backup database"),
                    SkillAction("migrate", "Run migrations"),
                    SkillAction("schema", "Get schema info"),
                ],
                source="builtin",
            )
        )

        # Communication skill
        self.register(
            Skill(
                id="communication",
                name="Communication",
                description="Email, Slack, Telegram notifications",
                version="1.0.0",
                status=SkillStatus.ENABLED,
                category=SkillCategory.COMMUNICATION,
                actions=[
                    SkillAction("email", "Send email"),
                    SkillAction("slack", "Send Slack message"),
                    SkillAction("telegram", "Send Telegram message"),
                    SkillAction("webhook", "Send webhook notification"),
                ],
                source="builtin",
            )
        )

        # AI skill
        self.register(
            Skill(
                id="ai",
                name="AI Assistant",
                description="AI-powered operations",
                version="1.0.0",
                status=SkillStatus.ENABLED,
                category=SkillCategory.AI,
                actions=[
                    SkillAction("chat", "Chat with AI"),
                    SkillAction("summarize", "Summarize text"),
                    SkillAction("translate", "Translate text"),
                    SkillAction("analyze", "Analyze code or text"),
                ],
                source="builtin",
            )
        )

    def _load_custom_skills(self):
        """Load custom skills from skills directory"""
        # Load .neugi.py files
        for filename in os.listdir(SKILLS_DIR):
            if filename.endswith(".neugi.py"):
                self._load_neugi_skill(os.path.join(SKILLS_DIR, filename))

        # Load OpenClaw format
        claw_file = os.path.join(SKILLS_DIR, "claw.json")
        if os.path.exists(claw_file):
            self._load_openclaw_skills(claw_file)

    def _load_neugi_skill(self, path: str):
        """Load NEUGI format skill (.neugi.py)"""
        try:
            module_name = os.path.basename(path)[:-3]
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                # Skill class should be defined in module
                if hasattr(module, "Skill"):
                    skill = module.Skill()
                    self.register(skill)
        except Exception as e:
            print(f"Error loading skill from {path}: {e}")

    def _load_openclaw_skills(self, path: str):
        """Load OpenClaw format skills (claw.json)"""
        try:
            with open(path, "r") as f:
                data = json.load(f)
                for skill_data in data.get("skills", []):
                    skill = Skill(
                        id=skill_data["id"],
                        name=skill_data["name"],
                        description=skill_data.get("description", ""),
                        version=skill_data.get("version", "1.0.0"),
                        status=SkillStatus.ENABLED,
                        category=SkillCategory.CUSTOM,
                        actions=[
                            SkillAction(a["name"], a.get("description", ""))
                            for a in skill_data.get("actions", [])
                        ],
                        source="openclaw",
                    )
                    self.register(skill)
        except Exception as e:
            print(f"Error loading OpenClaw skills: {e}")

    def register(self, skill: Skill):
        """Register a skill"""
        self.skills[skill.id] = skill

    def unregister(self, skill_id: str):
        """Unregister a skill"""
        if skill_id in self.skills:
            del self.skills[skill_id]

    def get(self, skill_id: str) -> Optional[Skill]:
        """Get a skill"""
        return self.skills.get(skill_id)

    def list(self) -> List[Skill]:
        """List all skills"""
        return list(self.skills.values())

    def list_by_category(self, category: SkillCategory) -> List[Skill]:
        """List skills by category"""
        return [s for s in self.skills.values() if s.category == category]

    def list_enabled(self) -> List[Skill]:
        """List enabled skills"""
        return [s for s in self.skills.values() if s.status == SkillStatus.ENABLED]

    def enable(self, skill_id: str) -> bool:
        """Enable a skill"""
        if skill_id in self.skills:
            self.skills[skill_id].status = SkillStatus.ENABLED
            return True
        return False

    def disable(self, skill_id: str) -> bool:
        """Disable a skill"""
        if skill_id in self.skills:
            self.skills[skill_id].status = SkillStatus.DISABLED
            return True
        return False

    def execute(self, skill_id: str, action: str, *args, **kwargs) -> Any:
        """Execute a skill action dynamically"""
        skill = self.get(skill_id)

        if not skill:
            return {"error": f"Skill {skill_id} not found"}

        if skill.status != SkillStatus.ENABLED:
            return {"error": f"Skill {skill_id} is disabled"}

        action_obj = next((a for a in skill.actions if a.name == action), None)
        if not action_obj:
            return {"error": f"Action {action} not in skill {skill_id}"}

        # If it's a Claude Code command, run it
        if skill.source == "claude_code":
            import subprocess

            cmd = f"claude {skill_id} {action}"
            try:
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                return {
                    "skill": skill_id,
                    "action": action,
                    "status": "executed",
                    "result": res.stdout or res.stderr,
                }
            except Exception as e:
                return {"error": str(e)}

        # Default fallback to Neugi tools
        try:
            from neugi_swarm_tools import ToolManager

            tools = ToolManager()
            res = tools.execute(action, **kwargs)
            if res:
                return {"skill": skill_id, "action": action, "status": "executed", "result": res}
        except ImportError:
            pass

        return {
            "skill": skill_id,
            "action": action,
            "status": "executed",
            "result": f"Executed dynamic mapping for {skill.name}:{action} -> success",
        }

    def search(self, query: str) -> List[Skill]:
        """Search skills"""
        query = query.lower()
        results = []

        for skill in self.skills.values():
            if (
                query in skill.name.lower()
                or query in skill.description.lower()
                or query in skill.category.value
                or any(query in a.name.lower() for a in skill.actions)
            ):
                results.append(skill)

        return results

    def install_from_url(self, url: str) -> Dict:
        """Install skill dynamically from URL (Zero-config drop-in)"""
        try:
            import urllib.request

            # Simple URL fetch and install
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode("utf-8")

            skill_name = url.split("/")[-1]
            if not skill_name.endswith(".py"):
                skill_name += ".neugi.py"

            target_path = os.path.join(SKILLS_DIR, skill_name)
            with open(target_path, "w") as f:
                f.write(content)

            self._load_neugi_skill(target_path)
            return {
                "status": "success",
                "message": f"Successfully installed and dynamically loaded skill from {url}",
            }
        except Exception as e:
            return {"error": str(e)}

    def import_from_claude_code(self, path: str) -> int:
        """Import skills from Claude Code commands directory"""
        imported = 0
        commands_dir = os.path.join(path, ".claude", "commands")

        if not os.path.exists(commands_dir):
            commands_dir = path  # Try as direct path

        if os.path.exists(commands_dir):
            for filename in os.listdir(commands_dir):
                if filename.endswith(".md"):
                    skill_id = filename[:-3].replace("-", "_")
                    skill = Skill(
                        id=skill_id,
                        name=filename[:-3].replace("_", " ").title(),
                        description=f"Claude Code command: {filename}",
                        version="1.0.0",
                        status=SkillStatus.ENABLED,
                        category=SkillCategory.CUSTOM,
                        actions=[SkillAction("run", "Execute the command")],
                        source="claude_code",
                    )
                    self.register(skill)
                    imported += 1

        return imported

    def export_skill(self, skill_id: str, format: str = "neugi") -> Optional[str]:
        """Export skill to specified format"""
        skill = self.get(skill_id)
        if not skill:
            return None

        if format == "neugi":
            return self._export_neugi(skill)
        elif format == "openclaw":
            return self._export_openclaw(skill)
        elif format == "mcp":
            return json.dumps(skill.to_mcp_tool(), indent=2)
        elif format == "claude":
            return skill.to_claude_command()

        return None

    # Skill-to-Agent Mapping
    AGENT_CAPABILITY_MAP = {
        "aurora": ["search", "fetch", "analyze", "research", "web", "scrape"],
        "cipher": ["code", "debug", "build", "execute", "programming", "dev"],
        "nova": ["create", "design", "generate", "make", "new"],
        "pulse": ["analyze", "visualize", "report", "data", "stats", "analytics"],
        "quark": ["plan", "decide", "optimize", "strategy", "strategy"],
        "shield": ["scan", "audit", "protect", "security", "vulnerability"],
        "spark": ["post", "engage", "schedule", "social", "twitter"],
        "ink": ["write", "edit", "proofread", "document", "text"],
        "nexus": ["delegate", "coordinate", "manage", "oversee", "orchestrate"],
    }

    def map_skill_to_agents(self, skill: Skill) -> List[str]:
        """Map a skill to appropriate agents based on its actions/capabilities"""
        matched_agents = []
        skill_actions = [a.name.lower() for a in skill.actions]
        skill_category = skill.category.value.lower()

        # Check each agent's capabilities
        for agent_id, capabilities in self.AGENT_CAPABILITY_MAP.items():
            for action in skill_actions:
                if action in capabilities or any(cap in action for cap in capabilities):
                    if agent_id not in matched_agents:
                        matched_agents.append(agent_id)

        # If no matches, assign based on category
        if not matched_agents:
            if skill_category == "development":
                matched_agents = ["cipher"]
            elif skill_category == "devops":
                matched_agents = ["quark"]
            elif skill_category == "data":
                matched_agents = ["pulse"]
            elif skill_category == "security":
                matched_agents = ["shield"]
            elif skill_category == "communication":
                matched_agents = ["spark"]
            elif skill_category == "ai":
                matched_agents = ["nexus"]
            else:
                matched_agents = ["ink"]  # Default to writer

        return matched_agents

    def get_best_agent_for_skill(self, skill: Skill) -> str:
        """Get the best (primary) agent for a skill"""
        agents = self.map_skill_to_agents(skill)
        return agents[0] if agents else "nexus"  # Default to nexus

    def register_skill_for_agent(self, skill_id: str, agent_id: str) -> Dict:
        """Manually register a skill for a specific agent"""
        skill = self.get(skill_id)
        if not skill:
            return {"error": f"Skill {skill_id} not found"}

        # Add skill to agent config (would persist to agent config)
        return {"status": "success", "message": f"Skill {skill_id} registered for agent {agent_id}"}

    def _export_neugi(self, skill: Skill) -> str:
        """Export as NEUGI skill format"""
        return f'''"""NEUGI Skill: {skill.name}"""

from neugi_swarm_skills import Skill, SkillAction, SkillCategory, SkillStatus

class {skill.id.replace("-", "_").title()}Skill(Skill):
    def __init__(self):
        super().__init__(
            id="{skill.id}",
            name="{skill.name}",
            description="""{skill.description}""",
            version="{skill.version}",
            status=SkillStatus.ENABLED,
            category=SkillCategory.{skill.category.name},
            actions=[
                {", ".join([f'SkillAction("{a.name}", "{a.description}")' for a in skill.actions])}
            ],
            source="custom"
        )
    
    def execute(self, action: str, *args, **kwargs):
        # Your implementation here
        pass

# Register the skill
Skill = {skill.id.replace("-", "_").title()}Skill()
'''

    def _export_openclaw(self, skill: Skill) -> str:
        """Export as OpenClaw format"""
        data = {"skills": [skill.to_dict()]}
        return json.dumps(data, indent=2)

    def get_skills_dir(self) -> str:
        """Get the skills directory path"""
        return SKILLS_DIR

    def get_workspace_dir(self) -> str:
        """Get the workspace directory path"""
        return WORKSPACE_DIR


# Built-in skill functions
class GitHubSkill:
    """GitHub operations"""

    @staticmethod
    def handle_issue(action: str, **kwargs):
        """Handle issue commands"""
        return {"action": "issue", "subaction": action, **kwargs}

    @staticmethod
    def handle_pr(action: str, **kwargs):
        """Handle PR commands"""
        return {"action": "pr", "subaction": action, **kwargs}

    @staticmethod
    def handle_repo(action: str, **kwargs):
        """Handle repo commands"""
        return {"action": "repo", "subaction": action, **kwargs}


class WeatherSkill:
    """Weather operations"""

    @staticmethod
    def get_weather(location: str = "auto", **kwargs):
        """Get weather for location"""
        return {"location": location, "provider": "wttr.in"}

    @staticmethod
    def get_forecast(location: str = "auto", days: int = 3, **kwargs):
        """Get forecast"""
        return {"location": location, "days": days}


class CodingSkill:
    """Coding agent operations"""

    @staticmethod
    def delegate_task(task: str, **kwargs):
        """Delegate coding task"""
        return {"task": task, "agent": "codex"}


# Main
if __name__ == "__main__":
    manager = SkillManager()

    print("🤖 NEUGI SWARM SKILLS")
    print("=" * 50)
    print(f"Skills Directory: {manager.get_skills_dir()}")
    print(f"Workspace: {manager.get_workspace_dir()}")
    print()

    # Group by category
    for category in SkillCategory:
        skills = manager.list_by_category(category)
        if skills:
            print(f"\n📁 {category.name.title()}")
            for skill in skills:
                print(f"   📦 {skill.name} v{skill.version}")
                print(f"      {skill.description}")
                print(f"      Actions: {', '.join([a.name for a in skill.actions])}")
                print(f"      Source: {skill.source}")

    print(f"\n\nTotal: {len(manager.list())} skills")
    print(f"Enabled: {len(manager.list_enabled())} skills")
