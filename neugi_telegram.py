#!/usr/bin/env python3
"""
🤖 NEUGI SWARM - TELEGRAM GATEWAY
===================================

Mobile interface for Neugi Swarm via Telegram.
Allows users to control their home swarm from anywhere.

Usage:
    python neugi_telegram.py
"""

import os
import json
import time
import requests

# Load config
CONFIG_PATH = os.path.expanduser("~/neugi/data/config.json")


def load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(config: dict):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


class TelegramGateway:
    def __init__(self):
        self.config = load_config()

        # Look for Telegram config under channels
        self.channels = self.config.get("channels", {})
        self.tg_config = self.channels.get("telegram", {})

        self.bot_token = self.tg_config.get("bot_token")
        self.allowed_users = self.tg_config.get("allowed_users", [])

        self.api_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None
        self.last_update_id = 0
        self.running = False

    def setup(self):
        """Interactive setup for Telegram Bot"""
        print("\n📱 NEUGI TELEGRAM GATEWAY SETUP")
        print("================================")
        print("This allows you to control your Neugi Swarm from your phone.\n")

        if not self.bot_token:
            print("1. Open Telegram and search for @BotFather")
            print("2. Send /newbot and follow instructions")
            print("3. Copy the HTTP API Token")

            token = input("\nEnter Bot Token: ").strip()
            if not token:
                print("Setup cancelled.")
                return False

            self.bot_token = token
            self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

        print("\nTesting connection...")
        try:
            r = requests.get(f"{self.api_url}/getMe", timeout=10)
            if not r.ok:
                print("❌ Invalid token or connection error.")
                return False

            bot_info = r.json().get("result", {})
            bot_username = bot_info.get("username")
            print(f"✅ Connected as @{bot_username}")

        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False

        if not self.allowed_users:
            print("\n⚠️ Security Warning: Your bot is currently public.")
            print("Send a message to your bot now to link your account.")

            print("Waiting for your message...")
            linked = False
            for _ in range(30):  # Wait up to 60 seconds
                try:
                    r = requests.get(f"{self.api_url}/getUpdates", timeout=5)
                    if r.ok:
                        updates = r.json().get("result", [])
                        if updates:
                            user_id = updates[-1]["message"]["from"]["id"]
                            username = updates[-1]["message"]["from"].get("username", "Unknown")

                            self.allowed_users.append(user_id)
                            linked = True
                            print(
                                f"\n🔒 Account linked! Only user ID {user_id} (@{username}) can command this swarm."
                            )

                            # Acknowledge
                            self._send_message(
                                user_id,
                                "🤖 Neugi Swarm linked securely. Send /help for commands.",
                            )
                            break
                except Exception:
                    pass
                time.sleep(2)

            if not linked:
                print("\nTimeout. You can link your account later.")

        # Save config
        if "channels" not in self.config:
            self.config["channels"] = {}

        self.config["channels"]["telegram"] = {
            "enabled": True,
            "bot_token": self.bot_token,
            "allowed_users": self.allowed_users,
        }

        save_config(self.config)
        print("\n✅ Telegram Gateway setup complete!")
        return True

    def _send_message(self, chat_id: int, text: str, parse_mode="Markdown"):
        if not self.api_url:
            return

        payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        try:
            requests.post(f"{self.api_url}/sendMessage", json=payload, timeout=5)
        except Exception:
            pass

    def _call_swarm(self, message: str) -> str:
        """Call the local Neugi Swarm API"""
        try:
            r = requests.post(
                "http://localhost:19888/api/chat", json={"message": message}, timeout=30
            )
            if r.ok:
                return r.json().get("response", "No response from swarm.")
            return "❌ Swarm API returned an error."
        except Exception as e:
            return f"❌ Could not reach local Swarm. Is it running? ({e})"

    def _process_command(self, chat_id: int, text: str):
        text = text.strip()

        if text.startswith("/start") or text.startswith("/help"):
            msg = "🤖 *NEUGI SWARM CONTROL*\n\n"
            msg += "I am connected to your home base.\n"
            msg += "Just type what you want the swarm to do.\n\n"
            msg += "*Commands:*\n"
            msg += "`/status`   - Check swarm health\n"
            msg += "`/agents`   - List active agents\n"
            msg += "`/logs`     - View recent system logs\n"
            msg += "`/topology` - View network nodes\n"
            msg += "`/monitor`  - Check live system telemetry\n"
            msg += "`/fix`      - Trigger auto-repair sequence\n"
            msg += "`/ping`     - Check connection latency\n"
            self._send_message(chat_id, msg)

        elif text.startswith("/status"):
            self._send_message(chat_id, "🔄 Gathering diagnostics...")
            try:
                r = requests.get("http://localhost:19888/api/status", timeout=10)
                if r.ok:
                    data = r.json()
                    issues = len(data.get("issues", []))
                    uptime = data.get("neugi", {}).get("uptime", 0)

                    msg = "*📊 System Status*\n"
                    msg += f"Status: `{'🟢 Optimal' if issues == 0 else '🔴 Anomalies Detected'}`\n"
                    msg += f"Uptime: `{uptime}s`\n"
                    msg += f"Issues: `{issues}`\n"
                    self._send_message(chat_id, msg)
                else:
                    self._send_message(chat_id, "❌ Status API failed.")
            except Exception:
                self._send_message(chat_id, "❌ Swarm unreachable.")

        elif text.startswith("/agents"):
            try:
                r = requests.get("http://localhost:19888/api/status", timeout=10)
                if r.ok:
                    agents = r.json().get("agents", [])
                    msg = f"*🤖 Active Agents ({len(agents)})*\n\n"
                    for a in agents:
                        msg += f"• *{a['name']}* ({a['role']}) - `{a['status']}`\n"
                    self._send_message(chat_id, msg)
            except Exception:
                self._send_message(chat_id, "❌ Swarm unreachable.")

        elif text.startswith("/logs"):
            try:
                r = requests.get("http://localhost:19888/api/logs", timeout=10)
                if r.ok:
                    logs = r.json().get("logs", "No logs found.")
                    # Telegram has a 4KB limit, take last 2000 chars
                    clean_logs = logs[-2000:] if len(logs) > 2000 else logs
                    msg = "*📋 Recent System Logs:*\n\n"
                    msg += f"```\n{clean_logs}\n```"
                    self._send_message(chat_id, msg)
            except Exception:
                self._send_message(chat_id, "❌ Could not fetch logs.")

        elif text.startswith("/topology"):
            try:
                r = requests.get("http://localhost:19888/api/swarm/nodes", timeout=10)
                if r.ok:
                    nodes = r.json()
                    msg = f"*🌐 Network Topology ({len(nodes)} Nodes)*\n\n"
                    msg += "`• localhost` (Primary Hub)\n"
                    if isinstance(nodes, dict):
                        for nid, info in nodes.items():
                            msg += f"`• {nid}` @ {info.get('ip', 'unknown')}:{info.get('port', 'unknown')}\n"
                    elif isinstance(nodes, list):
                        for node in nodes:
                            msg += f"`• {node}`\n"
                    self._send_message(chat_id, msg)
            except Exception:
                self._send_message(chat_id, "❌ Topology unavailable.")

        elif text.startswith("/monitor"):
            try:
                r = requests.get("http://localhost:19888/health", timeout=10)
                if r.ok:
                    tel = r.json().get("telemetry", {})
                    msg = "*📈 Live Telemetry*\n\n"
                    msg += f"CPU: `{tel.get('cpu')}%`\n"
                    msg += f"RAM: `{tel.get('ram')}%` ({tel.get('ram_used')}GB / {tel.get('ram_total')}GB)\n"
                    msg += f"Load: `{tel.get('load')}`\n"
                    self._send_message(chat_id, msg)
            except Exception:
                self._send_message(chat_id, "❌ Telemetry failed.")

        elif text.startswith("/fix"):
            self._send_message(chat_id, "🔧 *Initiating Auto-Repair Sequence...*")
            try:
                r = requests.get("http://localhost:19888/api/fix", timeout=15)
                if r.ok:
                    fixes = r.json().get("fixes", [])
                    if fixes:
                        msg = "✅ *Repairs Executed:*\n" + "\n".join([f"• {f}" for f in fixes])
                    else:
                        msg = "👍 No immediate repairs needed. system is stable."
                    self._send_message(chat_id, msg)
            except Exception:
                self._send_message(chat_id, "❌ Repair API failed.")

        elif text.startswith("/ping"):
            self._send_message(chat_id, "🏓 Pong! Link is active.")

        else:
            # Route directly to swarm
            self._send_message(chat_id, "⏳ *Processing...*")
            response = self._call_swarm(text)
            self._send_message(
                chat_id, response, parse_mode=""
            )  # No markdown for raw swarm responses to prevent parsing errors

    def start_polling(self):
        if not self.api_url:
            print("Telegram not configured. Run setup first.")
            return

        print("\n📡 Telegram Gateway Online. Polling for commands...")
        self.running = True

        while self.running:
            try:
                r = requests.get(
                    f"{self.api_url}/getUpdates?offset={self.last_update_id + 1}&timeout=10",
                    timeout=15,
                )

                if r.ok:
                    updates = r.json().get("result", [])
                    for update in updates:
                        self.last_update_id = update["update_id"]

                        if "message" in update and "text" in update["message"]:
                            msg = update["message"]
                            chat_id = msg["chat"]["id"]
                            user_id = msg["from"]["id"]
                            text = msg["text"]

                            # Security check
                            if self.allowed_users and user_id not in self.allowed_users:
                                print(f"⚠️ Unauthorized access attempt from user {user_id}")
                                continue

                            print(f"[TG] Command received: {text}")
                            self._process_command(chat_id, text)

            except Exception as e:
                print(f"[TG] Polling error: {e}")
                time.sleep(5)  # Backoff on error

            time.sleep(1)


if __name__ == "__main__":
    import sys

    gw = TelegramGateway()

    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        gw.setup()
    else:
        if not gw.bot_token:
            print("Telegram Gateway not configured.")
            print("Run: python neugi_telegram.py setup")
            sys.exit(1)
        try:
            gw.start_polling()
        except KeyboardInterrupt:
            print("\nShutting down Telegram Gateway...")
