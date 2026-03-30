#!/usr/bin/env python3
"""
🤖 NEUGI ONBOARDING - First Time User Experience (GLOBAL EDITION)
===================================================================

STEP-BY-STEP guided experience for new users worldwide!
Multi-language support: English, Indonesian, Spanish, Chinese, etc.

Version: 1.0.0 - Global Edition
"""

import os
import sys
from typing import Optional, Dict


NEUGI_DIR = os.path.expanduser("~/neugi")
os.makedirs(NEUGI_DIR, exist_ok=True)


class Colors:
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    END = "\033[0m"


def print_banner():
    print(f"""
{Colors.CYAN}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║       🤖 WELCOME TO NEUGI!                                    ║
║       The Most Powerful Agent Platform You've Ever Seen     ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
{Colors.END}
    """)


def print_step(step: int, total: int, title: str):
    print(f"\n{Colors.CYAN}{'─' * 60}{Colors.END}")
    print(f"{Colors.BOLD}STEP {step}/{total}: {title}{Colors.END}")
    print(f"{Colors.CYAN}{'─' * 60}{Colors.END}\n")


def wait_enter():
    input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.END}")


class Onboarding:
    """Bilingual onboarding experience"""

    def __init__(self):
        self.language = "english"
        self.use_case = ""
        self.user_level = ""
        self.config = {}
        self.user_name = ""

    def run(self):
        print_banner()

        print(f"""
{Colors.GREEN}I'll help you set up NEUGI easily!{Colors.END}

Just follow these simple steps...

        """)

        wait_enter()

        self.step_language()
        self.step_name()
        self.step_use_case()
        self.step_level()
        self.step_demo()
        self.step_create_agent()
        self.step_summary()

    def step_language(self):
        print_step(1, 6, "SELECT LANGUAGE")

        print("""Choose your preferred language:

  [1] 🇺🇸 English - Perfect for global users
  [2] 🇮🇩 Indonesia - Bahasa Indonesia supported
  [3] 🇪🇸 Español - Spanish
  [4] 🇨🇳 中文 - Chinese
  [5] 🇯🇵 日本語 - Japanese
  [6] 🇰🇷 한국어 - Korean
        """)

        lang_map = {
            "1": "english",
            "2": "indonesian",
            "3": "spanish",
            "4": "chinese",
            "5": "japanese",
            "6": "korean",
        }

        while True:
            choice = input(f"{Colors.YELLOW}Choose (1-6): {Colors.END}").strip()
            if choice in lang_map:
                self.language = lang_map[choice]
                break
            print(f"{Colors.RED}Please enter 1-6{Colors.END}")

        print(f"\n{Colors.GREEN}✓ Language set!{Colors.END}")

    def step_name(self):
        print_step(2, 6, "WHO ARE YOU?")

        print("""Let's get to know each other!

What should I call you? (Your name)
        """)

        self.user_name = input(f"{Colors.CYAN}Your name: {Colors.END}").strip()
        if not self.user_name:
            self.user_name = "User"

        print(f"\n{Colors.GREEN}✓ Nice to meet you, {self.user_name}!{Colors.END}")

    def step_use_case(self):
        print_step(3, 6, "WHAT DO YOU WANT TO DO?")

        print(f"""Hi {self.user_name}! What would you like to use NEUGI for?

Select your primary use case:
        """)

        use_cases = [
            (
                "coding",
                "💻 Programming & Development",
                "Build apps, write code, debug, create projects",
            ),
            (
                "research",
                "🔍 Research & Information",
                "Search web, gather data, analyze information",
            ),
            (
                "automation",
                "⚙️ Automation & Workflows",
                "Automate tasks, schedule jobs, create pipelines",
            ),
            (
                "data",
                "📊 Data Analysis & Visualization",
                "Analyze data, create reports, build dashboards",
            ),
            (
                "writing",
                "✍️ Writing & Content Creation",
                "Write content, edit documents, create copy",
            ),
            (
                "security",
                "🔐 Security & Auditing",
                "Scan code, audit security, vulnerability detection",
            ),
            ("general", "🤖 General Purpose", "Just exploring, haven't decided yet"),
        ]

        for i, (key, label, desc) in enumerate(use_cases, 1):
            print(f"  {Colors.CYAN}[{i}]{Colors.END} {label}")
            print(f"      {desc}")

        while True:
            choice = input(f"\n{Colors.YELLOW}Choose (1-7): {Colors.END}").strip()
            if choice.isdigit() and 1 <= int(choice) <= 7:
                self.use_case = use_cases[int(choice) - 1][0]
                break
            print(f"{Colors.RED}Please enter 1-7{Colors.END}")

        print(f"\n{Colors.GREEN}✓ Got it! I'll tailor NEUGI for {self.use_case}{Colors.END}")

    def step_level(self):
        print_step(4, 6, "TECHNICAL EXPERTISE LEVEL")

        print(f"""{Colors.BOLD}How would you rate your technical expertise?{Colors.END}

Don't worry - NEUGI adapts to YOUR level!
        """)

        levels = [
            ("beginner", "🌱 Beginner", "New to coding/tech, need guidance and simplicity"),
            ("intermediate", "🌿 Intermediate", "Know some tools, comfortable with CLI basics"),
            ("expert", "🌳 Expert", "Tech veteran, need full power and customization"),
        ]

        for i, (key, label, desc) in enumerate(levels, 1):
            print(f"  {Colors.CYAN}[{i}]{Colors.END} {label}")
            print(f"      {desc}")

        while True:
            choice = input(f"\n{Colors.YELLOW}Choose (1-3): {Colors.END}").strip()
            if choice in ["1", "2", "3"]:
                self.user_level = levels[int(choice) - 1][0]
                break
            print(f"{Colors.RED}Please enter 1-3{Colors.END}")

        print(f"\n{Colors.GREEN}✓ Perfect! I'll customize the experience for you.{Colors.END}")

    def step_demo(self):
        print_step(5, 6, "TRY IT NOW!")

        print(f"""
{Colors.BOLD}🎯 Let's try NEUGI right away!{Colors.END}

Tell me what you want - in plain English!

Examples:
  • "build me a Flask web app"
  • "how to install docker"
  • "check system health"
  • "create a simple website"
  
Or simply describe what you need:
        """)

        user_input = input(f"\n{Colors.CYAN}👤 {self.user_name}: {Colors.END}").strip()

        if user_input:
            try:
                from neugi_nlcli import NLCLI

                cli = NLCLI()
                print(f"\n{Colors.CYAN}{'─' * 50}{Colors.END}")
                result = cli.execute(user_input)
                print(result)
            except Exception as e:
                print(f"""
  {Colors.YELLOW}I'll note your request for now!{Colors.END}
  
  Your request: "{user_input}"
  
  Don't worry - I'll help you with this soon!
                """)
        else:
            print(f"""
  {Colors.CYAN}No problem! You can try it anytime from the main menu.{Colors.END}
            """)

        print(f"""
{Colors.GREEN}✓ Awesome! You've just used NEUGI!{Colors.END}
        """)

    def step_create_agent(self):
        print_step(6, 6, "CREATE YOUR FIRST CUSTOM AGENT")

        print(f"""
{Colors.BOLD}Want to create your OWN personalized AI agent?{Colors.END}

With NEUGI Agent Studio, you can create agents that:
  • Have their own personality
  • Use your chosen tools
  • Handle specific workflows
  • Work alongside the 9 built-in agents!

Choose a template and customize it!
        """)

        choice = (
            input(f"\n{Colors.YELLOW}Create your own agent? (y/n): {Colors.END}").strip().lower()
        )

        if choice == "y":
            try:
                from neugi_agent_studio import AgentStudio, TEMPLATES

                studio = AgentStudio()
                studio.create_agent_interactive()
            except Exception as e:
                print(f"  {Colors.RED}Error: {e}{Colors.END}")
        else:
            print(f"""
  {Colors.CYAN}✓ No problem! You can create agents anytime later.{Colors.END}
            """)

    def step_summary(self):
        print(f"""
{Colors.GREEN}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║           🎉 CONGRATULATIONS! NEUGI IS READY!                 ║
║                                                               ║
║              The most powerful agent platform                 ║
║              just got USER-FRIENDLIER!                        ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
{Colors.END}
        """)

        print("""
╔═══════════════════════════════════════════════════════════════╗
║                     📋 YOUR SETTINGS                           ║
╚═══════════════════════════════════════════════════════════════╝
        """)

        # Check if Ollama is running
        ollama_status = "✅ Running" if self._check_ollama() else "❌ Not Running"

        settings = [
            f"  👤 Name: {self.user_name}",
            f"  🌍 Language: {self.language.title()}",
            f"  🎯 Use Case: {self.use_case}",
            f"  📊 Expertise: {self.user_level}",
            f"  🧠 Ollama: {ollama_status}",
        ]

        for s in settings:
            print(s)

        print(f"""

╔═══════════════════════════════════════════════════════════════╗
║               🚀 QUICK START GUIDE                             ║
╚═══════════════════════════════════════════════════════════════╝

💻 TERMINAL COMMANDS:

  1. Start NEUGI:
     $ neugi start
     
  2. Open Dashboard (web UI):
     http://localhost:19888
     
  3. Interactive Wizard:
     $ python neugi_wizard.py
     
  4. Natural Language Mode:
     $ python neugi_nlcli.py "help me build a website"
     
  5. Check Status:
     $ neugi status

═══════════════════════════════════════════════════════════════

💡 PRO TIPS:

  • Just type what you need - no commands to memorize!
  • NEUGI gets smarter the more you use it
  • Create custom agents for specific workflows
  • Use Agent Studio for personalized automation
  • Access from anywhere via Telegram bot

═══════════════════════════════════════════════════════════════

🌐 NEED HELP?

  • Docs: neugi.com/docs.html
  • Support: neugi.com/support
  • GitHub: github.com/atharia-agi/neugi_swarm

═══════════════════════════════════════════════════════════════

    {Colors.CYAN}Let's build amazing things together! 🚀{Colors.END}
    
        """)

        input(f"\n{Colors.YELLOW}Press Enter to start NEUGI...{Colors.END}")

    def _check_ollama(self) -> bool:
        """Check if Ollama is running"""
        import requests

        try:
            r = requests.get("http://localhost:11434", timeout=2)
            return r.status_code == 200
        except:
            return False


def run_onboarding():
    onboarding = Onboarding()
    onboarding.run()


if __name__ == "__main__":
    run_onboarding()
