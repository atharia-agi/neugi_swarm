#!/usr/bin/env python3
"""
🤖 NEUGI APP INTEGRATIONS
==========================

Based on BrowserOS 40+ OAuth app integrations:
- Gmail, Slack, GitHub, Google Calendar, etc.
- OAuth 2.0 authentication
- MCP tool exposure

Version: 1.0
Date: March 15, 2026
"""

import os
import json
import time
import hashlib
import secrets
import urllib.parse
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from base64 import b64encode, b64decode


NEUGI_DIR = os.path.expanduser("~/neugi")
APPS_DIR = os.path.join(NEUGI_DIR, "apps")
TOKENS_FILE = os.path.join(APPS_DIR, "tokens.json")


# ========== APP DEFINITIONS ==========

APPS = {
    # Email
    "gmail": {
        "name": "Gmail",
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": [
            "https://www.googleapis.com/auth/gmail.read",
            "https://www.googleapis.com/auth/gmail.send",
        ],
        "icon": "📧",
    },
    "outlook": {
        "name": "Outlook Mail",
        "auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "scopes": ["Mail.Read", "Mail.Send"],
        "icon": "📨",
    },
    # Calendar
    "google_calendar": {
        "name": "Google Calendar",
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": ["https://www.googleapis.com/auth/calendar"],
        "icon": "📅",
    },
    "outlook_calendar": {
        "name": "Outlook Calendar",
        "auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "scopes": ["Calendars.Read", "Calendars.ReadWrite"],
        "icon": "🗓️",
    },
    # Communication
    "slack": {
        "name": "Slack",
        "auth_url": "https://slack.com/oauth/v2/authorize",
        "token_url": "https://slack.com/api/oauth.v2.access",
        "scopes": ["chat:write", "channels:read"],
        "icon": "💬",
    },
    "discord": {
        "name": "Discord",
        "auth_url": "https://discord.com/api/oauth2/authorize",
        "token_url": "https://discord.com/api/oauth2/token",
        "scopes": ["messages.write"],
        "icon": "🎮",
    },
    # Development
    "github": {
        "name": "GitHub",
        "auth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "scopes": ["repo", "user"],
        "icon": "🐙",
    },
    "vercel": {
        "name": "Vercel",
        "auth_url": "https://vercel.com/oauth/authorize",
        "token_url": "https://api.vercel.com/v1/oauth/access_token",
        "scopes": ["deployment", "project"],
        "icon": "▲",
    },
    # Project Management
    "linear": {
        "name": "Linear",
        "auth_url": "https://linear.app/oauth/authorize",
        "token_url": "https://api.linear/oauth/token",
        "scopes": ["read", "write"],
        "icon": "📊",
    },
    "notion": {
        "name": "Notion",
        "auth_url": "https://api.notion.com/v1/oauth/authorize",
        "token_url": "https://api.notion.com/v1/oauth/token",
        "scopes": ["authorization_code"],
        "icon": "📝",
    },
    # Cloud Storage
    "google_drive": {
        "name": "Google Drive",
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": ["https://www.googleapis.com/auth/drive.file"],
        "icon": "☁️",
    },
    "dropbox": {
        "name": "Dropbox",
        "auth_url": "https://www.dropbox.com/oauth2/authorize",
        "token_url": "https://api.dropboxapi.com/oauth2/token",
        "scopes": ["files.content.write"],
        "icon": "📦",
    },
    # Social
    "linkedin": {
        "name": "LinkedIn",
        "auth_url": "https://www.linkedin.com/oauth/v2/authorization",
        "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
        "scopes": ["r_liteprofile", "w_member_social"],
        "icon": "💼",
    },
    # Analytics
    "posthog": {
        "name": "PostHog",
        "auth_url": "https://posthog.com/oauth/authorize",
        "token_url": "https://posthog.com/api/token",
        "scopes": ["read"],
        "icon": "📈",
    },
}


@dataclass
class AppConnection:
    """App connection state"""

    app_id: str
    connected: bool = False
    access_token: str = ""
    refresh_token: str = ""
    expires_at: int = 0
    user_id: str = ""
    last_sync: str = ""


class AppIntegrationManager:
    """
    NEUGI App Integrations Manager

    Handles OAuth connections to external services
    """

    def __init__(self, apps_dir: str = None):
        self.apps_dir = apps_dir or APPS_DIR
        self.tokens_file = os.path.join(self.apps_dir, "tokens.json")
        self.connections: Dict[str, AppConnection] = {}
        self._ensure_directory()
        self._load_tokens()

    def _ensure_directory(self):
        """Create apps directory"""
        os.makedirs(self.apps_dir, exist_ok=True)

    def _load_tokens(self):
        """Load saved tokens"""
        if os.path.exists(self.tokens_file):
            try:
                with open(self.tokens_file, "r") as f:
                    data = json.load(f)
                    for app_id, conn_data in data.items():
                        self.connections[app_id] = AppConnection(**conn_data)
            except Exception:
                pass

    def _save_tokens(self):
        """Save tokens"""
        data = {
            app_id: {
                "app_id": conn.app_id,
                "connected": conn.connected,
                "access_token": conn.access_token,
                "refresh_token": conn.refresh_token,
                "expires_at": conn.expires_at,
                "user_id": conn.user_id,
                "last_sync": conn.last_sync,
            }
            for app_id, conn in self.connections.items()
        }

        with open(self.tokens_file, "w") as f:
            json.dump(data, f, indent=2)

    def list_apps(self) -> List[Dict]:
        """List all available apps"""
        apps = []
        for app_id, app_info in APPS.items():
            conn = self.connections.get(app_id)
            apps.append(
                {
                    "id": app_id,
                    "name": app_info["name"],
                    "icon": app_info["icon"],
                    "connected": conn.connected if conn else False,
                    "last_sync": conn.last_sync if conn else None,
                }
            )
        return apps

    def get_connected_apps(self) -> List[str]:
        """Get list of connected app IDs"""
        return [app_id for app_id, conn in self.connections.items() if conn.connected]

    def is_connected(self, app_id: str) -> bool:
        """Check if app is connected"""
        conn = self.connections.get(app_id)
        return conn.connected if conn else False

    def get_auth_url(self, app_id: str, redirect_uri: str) -> Optional[str]:
        """Generate OAuth URL"""
        if app_id not in APPS:
            return None

        app = APPS[app_id]
        state = secrets.token_urlsafe(32)

        # Save state for verification
        self._save_state(app_id, state)

        params = {
            "client_id": f"{app_id}_client_id",  # User would configure this
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(app["scopes"]),
            "state": state,
        }

        return f"{app['auth_url']}?{urllib.parse.urlencode(params)}"

    def _save_state(self, app_id: str, state: str):
        """Save OAuth state"""
        state_file = os.path.join(self.apps_dir, f"{app_id}_state")
        with open(state_file, "w") as f:
            f.write(state)

    def _load_state(self, app_id: str) -> Optional[str]:
        """Load OAuth state"""
        state_file = os.path.join(self.apps_dir, f"{app_id}_state")
        if os.path.exists(state_file):
            with open(state_file, "r") as f:
                return f.read()
        return None

    def handle_callback(self, app_id: str, code: str, state: str) -> Dict:
        """Handle OAuth callback"""
        # Verify state
        saved_state = self._load_state(app_id)
        if state != saved_state:
            return {"error": "Invalid state parameter"}

        # In real implementation, exchange code for token
        # For demo, simulate token storage
        conn = AppConnection(
            app_id=app_id,
            connected=True,
            access_token=f"demo_token_{app_id}",
            refresh_token=f"demo_refresh_{app_id}",
            expires_at=int(time.time()) + 3600,
            user_id="demo_user",
            last_sync=datetime.now().isoformat(),
        )

        self.connections[app_id] = conn
        self._save_tokens()

        return {"status": "connected", "app": app_id}

    def disconnect(self, app_id: str) -> bool:
        """Disconnect an app"""
        if app_id in self.connections:
            del self.connections[app_id]
            self._save_tokens()
            return True
        return False

    def call_api(self, app_id: str, endpoint: str, method: str = "GET") -> Dict:
        """Call app API (simulated for demo)"""
        if not self.is_connected(app_id):
            return {"error": f"App {app_id} not connected"}

        # Simulated API responses
        if app_id == "github":
            if "user" in endpoint:
                return {"login": "demo_user", "name": "Demo User"}
            elif "repos" in endpoint:
                return [{"name": "neugi_swarm", "full_name": "user/neugi_swarm"}]

        elif app_id == "slack":
            if "channels" in endpoint:
                return {"ok": True, "channels": [{"name": "general", "id": "C123"}]}

        elif app_id == "gmail":
            if "messages" in endpoint:
                return {"messages": [{"id": "123", "snippet": "Demo email..."}]}

        elif app_id == "google_calendar":
            if "events" in endpoint:
                return {
                    "items": [{"summary": "Meeting", "start": {"dateTime": "2026-03-15T10:00:00"}}]
                }

        return {"ok": True, "message": f"API call to {app_id}/{endpoint}"}

    # ========== TOOL GENERATORS ==========

    def generate_mcp_tools(self) -> List[Dict]:
        """Generate MCP tools for connected apps"""
        tools = []

        for app_id in self.get_connected_apps():
            app = APPS.get(app_id)
            if not app:
                continue

            # Generate generic API tool
            tools.append(
                {
                    "name": f"neugi_{app_id}_call",
                    "description": f"Call {app['name']} API",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "endpoint": {"type": "string", "description": "API endpoint"},
                            "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"]},
                        },
                        "required": ["endpoint"],
                    },
                }
            )

        return tools


# ========== STANDALONE CLI ==========


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI App Integrations")
    parser.add_argument("action", choices=["list", "connect", "disconnect", "status", "tools"])
    parser.add_argument("--app", help="App ID")

    args = parser.parse_args()

    manager = AppIntegrationManager()

    if args.action == "list":
        print("\n📱 NEUGI APP INTEGRATIONS")
        print("=" * 50)

        for app in manager.list_apps():
            status = "✅ Connected" if app["connected"] else "❌ Not connected"
            print(f"{app['icon']} {app['name']}: {status}")

        print(f"\nTotal: {len(manager.list_apps())} apps")
        print(f"Connected: {len(manager.get_connected_apps())}")

    elif args.action == "connect":
        if not args.app:
            print("Specify --app")
            return

        print(f"\n🔗 Connect to {args.app}")
        print("Note: OAuth flow requires client_id configuration")
        print(f"\nURL: {manager.get_auth_url(args.app, 'http://localhost:19889/oauth/callback')}")

    elif args.action == "disconnect":
        if manager.disconnect(args.app):
            print(f"✅ Disconnected: {args.app}")
        else:
            print(f"❌ Not connected: {args.app}")

    elif args.action == "status":
        if manager.is_connected(args.app):
            print(f"✅ {args.app} is connected")
        else:
            print(f"❌ {args.app} is not connected")

    elif args.action == "tools":
        tools = manager.generate_mcp_tools()
        print(f"\n🔧 MCP Tools ({len(tools)}):")
        for tool in tools:
            print(f"  • {tool['name']}")


if __name__ == "__main__":
    main()
