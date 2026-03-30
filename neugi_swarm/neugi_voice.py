#!/usr/bin/env python3
"""
🤖 NEUGI VOICE COMMAND - Hands-Free Operation
==============================================

CONTROL NEUGI WITH YOUR VOICE!
Just speak and NEUGI will execute your commands.

No more typing - just say what you need!

Supported Languages:
- English (primary)
- Indonesian
- Spanish
- Chinese
- And more via speech recognition

Version: 1.0.0
"""

import os
import sys
import json
import time
import threading
from typing import Optional, Callable, Dict, List


NEUGI_DIR = os.path.expanduser("~/neugi")


class Colors:
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"


class VoiceCommand:
    """Represents a voice command"""

    def __init__(self, phrase: str, action: Callable, description: str = ""):
        self.phrase = phrase.lower()
        self.action = action
        self.description = description

    def matches(self, spoken: str) -> bool:
        spoken = spoken.lower()
        return spoken == self.phrase or spoken in self.phrase or self.phrase in spoken


class VoiceController:
    """
    🎤 HANDS-FREE NEUGI CONTROL

    Just speak and NEUGI will execute!
    """

    def __init__(self):
        self.is_listening = False
        self.commands: List[VoiceCommand] = []
        self._register_default_commands()

        # Try to use speech recognition
        self.sr_available = False
        self._init_speech_recognition()

    def _init_speech_recognition(self):
        """Try to initialize speech recognition"""
        try:
            import speech_recognition as sr

            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()
            self.sr_available = True
            print(f"{Colors.GREEN}✓ Speech recognition initialized!{Colors.END}")
        except ImportError:
            print(f"{Colors.YELLOW}⚠ speech_recognition not installed{Colors.END}")
            print(f"   Install with: pip install SpeechRecognition")
            self.sr_available = False
        except Exception as e:
            print(f"{Colors.RED}⚠ Could not initialize mic: {e}{Colors.END}")
            self.sr_available = False

    def _register_default_commands(self):
        """Register all voice commands"""

        # Basic commands
        self.commands.extend(
            [
                VoiceCommand(
                    "start neugi", lambda: self._run_command("neugi start"), "Start NEUGI service"
                ),
                VoiceCommand(
                    "stop neugi", lambda: self._run_command("neugi stop"), "Stop NEUGI service"
                ),
                VoiceCommand(
                    "neugi status", lambda: self._run_command("neugi status"), "Check NEUGI status"
                ),
                VoiceCommand(
                    "check system", lambda: self._run_command("neugi status"), "Check system health"
                ),
                VoiceCommand(
                    "open dashboard",
                    lambda: self._open_url("http://localhost:19888"),
                    "Open dashboard in browser",
                ),
                VoiceCommand("help me", lambda: print(self._help_text()), "Show help"),
                # Project creation
                VoiceCommand(
                    "create project", self._create_project_interactive, "Create a new project"
                ),
                VoiceCommand(
                    "build flask", lambda: self._create_project("flask"), "Create Flask project"
                ),
                VoiceCommand(
                    "build react", lambda: self._create_project("react"), "Create React project"
                ),
                VoiceCommand(
                    "setup docker",
                    lambda: self._create_project("docker"),
                    "Setup Docker environment",
                ),
                # Agent commands
                VoiceCommand("run agent", self._run_agent_interactive, "Run a specific agent"),
                VoiceCommand("create agent", self._open_agent_studio, "Go to agent studio"),
                # Search commands
                VoiceCommand("search for", self._search_interactive, "Search the web"),
                # Utility
                VoiceCommand("take screenshot", self._take_screenshot, "Take a screenshot"),
                VoiceCommand("open Terminal", self._open_terminal, "Open terminal"),
                # Emergency
                VoiceCommand("emergency stop", self._emergency_stop, "Emergency stop all"),
            ]
        )

    def _help_text(self) -> str:
        return f"""
{Colors.CYAN}🎤 AVAILABLE VOICE COMMANDS:{Colors.END}

  • "start neugi" - Start NEUGI service
  • "stop neugi" - Stop NEUGI service  
  • "check system" - Check system status
  • "open dashboard" - Open web dashboard
  • "create project" - Create new project
  • "build flask" - Create Flask app
  • "build react" - Create React app
  • "setup docker" - Setup Docker
  • "run agent" - Run specific agent
  • "create agent" - Open Agent Studio
  • "search for [query]" - Search web
  • "emergency stop" - Stop everything
  
Just speak clearly and NEUGI will respond!
        """

    def _run_command(self, cmd: str) -> str:
        """Execute a shell command"""
        import subprocess

        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return result.stdout[:200] if result.stdout else "Command executed"
        except Exception as e:
            return f"Error: {e}"

    def _open_url(self, url: str) -> str:
        """Open URL in browser"""
        import webbrowser

        try:
            webbrowser.open(url)
            return f"Opened {url}"
        except Exception as e:
            return f"Error: {e}"

    def _create_project_interactive(self):
        """Interactive project creation"""
        print(f"""
{Colors.CYAN}🎯 WHAT DO YOU WANT TO BUILD?{Colors.END}

Say one of:
  • "build flask" - Python Flask web app
  • "build react" - React frontend
  • "build api" - FastAPI backend
  • "build docker" - Docker setup
  • "build ml" - Machine learning project
  • "build cli" - Command-line tool
        """)

    def _create_project(self, template: str):
        """Create project from template"""
        from neugi_project_templates import ProjectFactory

        factory = ProjectFactory()

        # Map voice to template
        template_map = {
            "flask": "flask",
            "react": "react",
            "api": "api",
            "docker": "docker",
            "ml": "ml",
            "cli": "cli",
        }

        template_id = template_map.get(template.lower(), template.lower())
        result = factory.create_project(template_id, f"voice_{template}")

        if result.get("success"):
            return f"Created {template} project!"
        return f"Could not create project"

    def _run_agent_interactive(self):
        """Run an agent"""
        print(f"""
{Colors.CYAN}🤖 WHICH AGENT?{Colors.END}

Available agents:
  • "aurora" - Research
  • "cipher" - Coding
  • "nova" - Creation
  • "pulse" - Analysis
  • "shield" - Security
  
Or "stop" to cancel
        """)

    def _open_agent_studio(self):
        """Open agent studio"""
        from neugi_agent_studio import AgentStudio

        studio = AgentStudio()
        studio.create_agent_interactive()

    def _search_interactive(self):
        """Interactive web search"""
        print(f"""
{Colors.CYAN}🔍 WHAT DO YOU WANT TO SEARCH?{Colors.END}

Just say what you want to find!
        """)

    def _take_screenshot(self) -> str:
        """Take screenshot"""
        try:
            from PIL import ImageGrab
            import datetime

            filename = f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            ImageGrab.grab().save(filename)
            return f"Screenshot saved: {filename}"
        except:
            return "Screenshot not available"

    def _open_terminal(self) -> str:
        """Open terminal"""
        try:
            if sys.platform == "win32":
                os.system("start cmd")
            elif sys.platform == "darwin":
                os.system("open -a Terminal")
            else:
                os.system("x-terminal-emulator &")
            return "Terminal opened"
        except:
            return "Could not open terminal"

    def _emergency_stop(self) -> str:
        """Emergency stop all processes"""
        print(f"""
{Colors.RED}{Colors.BOLD}
⚠️ EMERGENCY STOP! ⚠️

Stopping all NEUGI processes...
        """)

        try:
            os.system("taskkill /F /IM python.exe >nul 2>&1")  # Windows
            os.system("pkill -f neugi >/dev/null 2>&1")  # Linux
        except:
            pass

        return "Emergency stop complete"

    def recognize_speech(self) -> Optional[str]:
        """Recognize speech using available libraries"""
        if not self.sr_available:
            return None

        try:
            import speech_recognition as sr

            with self.microphone as source:
                print(f"{Colors.YELLOW}🎤 Listening...{Colors.END}")
                self.recognizer.adjust_for_ambient_noise(source)
                audio = self.recognizer.listen(source, timeout=5)

            # Try Google Speech Recognition
            try:
                text = self.recognizer.recognize_google(audio)
                print(f"{Colors.GREEN}You said: {text}{Colors.END}")
                return text
            except sr.UnknownValueError:
                print(f"{Colors.YELLOW}Could not understand. Try again.{Colors.END}")
            except sr.RequestError:
                print(f"{Colors.RED}Speech service unavailable{Colors.END}")

        except Exception as e:
            print(f"{Colors.RED}Error: {e}{Colors.END}")

        return None

    def process_command(self, spoken: str) -> str:
        """Process a spoken command"""
        spoken = spoken.lower().strip()

        # Check for search "search for X"
        if spoken.startswith("search for "):
            query = spoken.replace("search for ", "")
            return self._run_command(f"neugi search {query}")

        # Check all commands
        for cmd in self.commands:
            if cmd.matches(spoken):
                try:
                    result = cmd.action()
                    if result:
                        return result
                    return f"Executed: {cmd.description}"
                except Exception as e:
                    return f"Error: {e}"

        return f"Command not recognized: '{spoken}'"

    def listen_continuous(self):
        """Continuous listening mode"""
        self.is_listening = True

        print(f"""
{Colors.GREEN}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════╗
║                 🎤 VOICE LISTENING ACTIVE                      ║
║                                                                   ║
║    Say a command (or "exit" to stop)                            ║
╚═══════════════════════════════════════════════════════════════╝
{Colors.END}

Available commands:
{self._help_text()}
        """)

        while self.is_listening:
            text = self.recognize_speech()

            if text:
                if text.lower() in ["exit", "stop", "quit"]:
                    self.is_listening = False
                    print(f"{Colors.CYAN}Stopping voice mode...{Colors.END}")
                    break

                result = self.process_command(text)
                print(f"{Colors.CYAN}Result: {result}{Colors.END}")

    def start_voice_mode(self):
        """Start interactive voice mode"""
        if not self.sr_available:
            print(f"""
{Colors.RED}Speech recognition not available!{Colors.END}

To use voice commands, install:
  pip install SpeechRecognition

Or use text-based Natural Language CLI:
  python neugi_nlcli.py "help me build a website"
            """)

            # Fallback to text input
            print(f"""
{Colors.YELLOW}Using TEXT input fallback{Colors.END}
            
Type what you want NEUGI to do!
            """)

            while True:
                try:
                    text = input(f"{Colors.CYAN}🎤 You: {Colors.END}").strip()
                    if text.lower() in ["exit", "quit"]:
                        break
                    if text:
                        result = self.process_command(text)
                        print(f"{Colors.GREEN}Result: {result}{Colors.END}")
                except KeyboardInterrupt:
                    break
        else:
            self.listen_continuous()


def run_voice():
    """Main entry point"""
    print(f"""
{Colors.CYAN}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════╗
║              🤖 NEUGI VOICE COMMAND v1.0                       ║
║              🎤 Hands-Free Control for Everyone                ║
╚═══════════════════════════════════════════════════════════════╝
{Colors.END}
    """)

    controller = VoiceController()
    controller.start_voice_mode()


if __name__ == "__main__":
    run_voice()
