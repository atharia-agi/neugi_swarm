#!/usr/bin/env python3
"""
🤖 NEUGI TEAM COLLABORATION - Multi-User Support
=================================================

WORK TOGETHER WITH YOUR TEAM!

Features:
- Multi-user sessions
- Team workspaces
- Shared agents
- Task assignment
- Activity feed
- Role-based access

Perfect for:
- Development teams
- Research groups
- DevOps teams
- Any team needing AI assistance

Version: 1.0.0
"""

import os
import json
import sqlite3
import hashlib
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum


NEUGI_DIR = os.path.expanduser("~/neugi")
os.makedirs(os.path.join(NEUGI_DIR, "data"), exist_ok=True)


class Colors:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"


class TeamRole(Enum):
    ADMIN = "admin"
    DEVELOPER = "developer"
    ANALYST = "analyst"
    VIEWER = "viewer"


class TeamMember:
    """Represents a team member"""

    def __init__(self, user_id: str, username: str, role: TeamRole):
        self.user_id = user_id
        self.username = username
        self.role = role
        self.joined_at = datetime.now().isoformat()
        self.last_active = datetime.now().isoformat()
        self.active = True


class Team:
    """Team workspace"""

    def __init__(self, team_id: str, name: str, owner_id: str):
        self.team_id = team_id
        self.name = name
        self.owner_id = owner_id
        self.created_at = datetime.now().isoformat()
        self.members: Dict[str, TeamMember] = {}
        self.shared_agents = []  # List of agent IDs shared with team
        self.workspace_path = os.path.join(NEUGI_DIR, "workspaces", team_id)

        os.makedirs(self.workspace_path, exist_ok=True)


class TeamManager:
    """
    👥 TEAM COLLABORATION SYSTEM

    Work together with your team using NEUGI agents!
    """

    def __init__(self):
        self.db_path = os.path.join(NEUGI_DIR, "data", "teams.db")
        self._init_db()
        self.teams: Dict[str, Team] = {}
        self._load_teams()

    def _init_db(self):
        """Initialize teams database"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                team_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                created_at TEXT,
                settings TEXT
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS team_members (
                user_id TEXT NOT NULL,
                team_id TEXT NOT NULL,
                username TEXT NOT NULL,
                role TEXT NOT NULL,
                joined_at TEXT,
                last_active TEXT,
                PRIMARY KEY (user_id, team_id)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS team_tasks (
                task_id TEXT PRIMARY KEY,
                team_id TEXT NOT NULL,
                title TEXT NOT NULL,
                assigned_to TEXT,
                status TEXT,
                created_by TEXT,
                created_at TEXT
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS team_activity (
                activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                action TEXT,
                details TEXT,
                timestamp TEXT
            )
        """)

        conn.commit()
        conn.close()

    def _load_teams(self):
        """Load teams from database"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("SELECT team_id, name, owner_id FROM teams")
        for row in c.fetchall():
            team = Team(row[0], row[1], row[2])
            self.teams[team.team_id] = team

            # Load members
            c.execute(
                "SELECT user_id, username, role FROM team_members WHERE team_id = ?", (row[0],)
            )
            for m in c.fetchall():
                team.members[m[0]] = TeamMember(m[0], m[1], TeamRole(m[2]))

        conn.close()

    def create_team(self, name: str, owner_username: str) -> str:
        """Create a new team"""
        team_id = f"team_{hashlib.md5(name.encode()).hexdigest()[:8]}"

        if team_id in self.teams:
            return f"Team already exists: {self.teams[team_id].name}"

        owner_id = f"user_{hashlib.md5(owner_username.encode()).hexdigest()[:8]}"

        team = Team(team_id, name, owner_id)
        team.members[owner_id] = TeamMember(owner_id, owner_username, TeamRole.ADMIN)
        self.teams[team_id] = team

        # Save to DB
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            "INSERT INTO teams VALUES (?, ?, ?, ?, ?)",
            (team_id, name, owner_id, team.created_at, "{}"),
        )

        c.execute(
            "INSERT INTO team_members VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                owner_id,
                team_id,
                owner_username,
                TeamRole.ADMIN.value,
                datetime.now().isoformat(),
                datetime.now().isoformat(),
            ),
        )

        conn.commit()
        conn.close()

        self._log_activity(team_id, owner_id, "created_team", f"Created team: {name}")

        return team_id

    def add_member(self, team_id: str, username: str, role: TeamRole = TeamRole.DEVELOPER):
        """Add member to team"""
        if team_id not in self.teams:
            return f"Team {team_id} not found"

        user_id = f"user_{hashlib.md5(username.encode()).hexdigest()[:8]}"
        team = self.teams[team_id]

        if user_id in team.members:
            return f"Member {username} already in team"

        member = TeamMember(user_id, username, role)
        team.members[user_id] = member

        # Save to DB
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "INSERT INTO team_members VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                team_id,
                username,
                role.value,
                datetime.now().isoformat(),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        conn.close()

        self._log_activity(team_id, user_id, "member_joined", f"Member joined: {username}")

        return f"Added {username} to team {team.name}"

    def assign_task(self, team_id: str, title: str, assigned_to: str, created_by: str) -> str:
        """Assign a task to a team member"""
        task_id = f"task_{hashlib.md5(title.encode()).hexdigest()[:8]}"

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            "INSERT INTO team_tasks VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                task_id,
                team_id,
                title,
                assigned_to,
                "pending",
                created_by,
                datetime.now().isoformat(),
            ),
        )

        conn.commit()
        conn.close()

        self._log_activity(team_id, created_by, "task_assigned", f"Task: {title} → {assigned_to}")

        return f"Task assigned: {title} to {assigned_to}"

    def get_team_activity(self, team_id: str, limit: int = 10) -> List[Dict]:
        """Get recent team activity"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            """
            SELECT user_id, action, details, timestamp 
            FROM team_activity 
            WHERE team_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        """,
            (team_id, limit),
        )

        activities = []
        for row in c.fetchall():
            activities.append({"user": row[0], "action": row[1], "details": row[2], "time": row[3]})

        conn.close()
        return activities

    def _log_activity(self, team_id: str, user_id: str, action: str, details: str):
        """Log team activity"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            "INSERT INTO team_activity VALUES (?, ?, ?, ?, ?, ?)",
            (None, team_id, user_id, action, details, datetime.now().isoformat()),
        )

        conn.commit()
        conn.close()

    def list_teams(self) -> List[Dict]:
        """List all teams"""
        return [
            {
                "team_id": t.team_id,
                "name": t.name,
                "members": len(t.members),
                "created": t.created_at,
            }
            for t in self.teams.values()
        ]

    def show_team_dashboard(self, team_id: str):
        """Show team dashboard"""
        if team_id not in self.teams:
            print(f"{Colors.RED}Team not found!{Colors.END}")
            return

        team = self.teams[team_id]

        print(f"""
{Colors.CYAN}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════╗
║              👥 NEUGI TEAM: {team.name.upper():<30}      ║
╚═══════════════════════════════════════════════════════════════╝
{Colors.END}

📊 TEAM STATS:
   Members: {len(team.members)}
   Workspace: {team.workspace_path}

👥 MEMBERS:
        """)

        for member in team.members.values():
            role_icon = {
                TeamRole.ADMIN: "👑",
                TeamRole.DEVELOPER: "💻",
                TeamRole.ANALYST: "📊",
                TeamRole.VIEWER: "👁️",
            }.get(member.role, "•")

            print(f"   {role_icon} {member.username} ({member.role.value})")

        # Recent activity
        activities = self.get_team_activity(team_id)

        if activities:
            print(f"""
📝 RECENT ACTIVITY:
            """)

            for act in activities[:5]:
                print(f"   • {act['user']}: {act['action']} - {act['details']}")

        print(f"""
═══════════════════════════════════════════════════════════════

💡 QUICK ACTIONS:
   /invite @username    - Invite member
   /task "title" @user  - Assign task
   /share agent         - Share agent with team
   /activity            - View all activity
        """)


def run_team():
    """Interactive team management"""
    manager = TeamManager()

    print(f"""
{Colors.CYAN}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════╗
║              👥 NEUGI TEAM COLLABORATION                       ║
║              Work together, smarter!                          ║
╚═══════════════════════════════════════════════════════════════╝
{Colors.END}

    """)

    print("Available teams:")
    teams = manager.list_teams()

    if not teams:
        print("   No teams yet. Create one!")
    else:
        for t in teams:
            print(f"   • {t['name']} ({t['members']} members)")

    print(f"""

COMMANDS:
   create <team_name>   - Create new team
   join <team_id>       - Join existing team
   list                 - List teams
   activity <team_id>  - View activity
   quit                 - Exit

    """)

    while True:
        cmd = input(f"{Colors.CYAN}> {Colors.END}").strip()

        if not cmd or cmd.lower() in ["quit", "exit"]:
            break

        parts = cmd.split()

        if parts[0] == "create" and len(parts) > 1:
            team_name = " ".join(parts[1:])
            owner = input("Your username: ").strip() or "admin"
            result = manager.create_team(team_name, owner)
            print(f"{Colors.GREEN}{result}{Colors.END}")

        elif parts[0] == "list":
            teams = manager.list_teams()
            for t in teams:
                manager.show_team_dashboard(t["team_id"])

        elif parts[0] == "activity" and len(parts) > 1:
            activities = manager.get_team_activity(parts[1])
            for a in activities:
                print(f"   {a['time']}: {a['user']} - {a['action']}")

        else:
            print("Unknown command")


if __name__ == "__main__":
    run_team()
