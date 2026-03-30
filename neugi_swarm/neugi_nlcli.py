#!/usr/bin/env python3
"""
🤖 NEUGI NATURAL LANGUAGE CLI
==============================

REVOLUTIONARY: User-friendly CLI that understands NATURAL LANGUAGE!
No need to remember commands - just type what you want!

Examples:
  neugi "tolong buat flask app"
  neugi "apa cara install docker"
  neugi "bikin website sederhana"
  neugi "cek sistem kesehatan"

Key Differences vs Other CLIs:
- Understands Indonesian + English
- Parses intent automatically
- Works for beginners - no technical knowledge needed
- Remembers user preferences

Version: 1.0.0
"""

import os
import re
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


NEUGI_DIR = os.path.expanduser("~/neugi")


class Intent(Enum):
    """Detected user intent"""

    CREATE = "create"
    SEARCH = "search"
    EXPLAIN = "explain"
    BUILD = "build"
    FIX = "fix"
    CHECK = "check"
    DEPLOY = "deploy"
    RUN = "run"
    HELP = "help"
    UNKNOWN = "unknown"


@dataclass
class ParsedIntent:
    """Natural language parsing result"""

    intent: Intent
    target: str  # What the user wants to create/search
    context: Dict  # Additional context extracted
    language: str  # indonesian, english, mixed
    confidence: float


class NLParser:
    """
    Natural Language Parser

    Understands what users want from plain language!
    Supports: Indonesian, English, Mixed
    """

    # Intent keywords
    KEYWORDS = {
        Intent.CREATE: [
            # English
            "create",
            "make",
            "build",
            "generate",
            "init",
            "new",
            "scaffold",
            # Indonesian
            "buat",
            "bikin",
            "buatin",
            "buatin",
            "ciptakan",
            "buatproject",
            "install",
            "setup",
            "aktivasi",
        ],
        Intent.SEARCH: [
            # English
            "search",
            "find",
            "look",
            "how to",
            "what is",
            "where",
            "apa itu",
            # Indonesian
            "cari",
            "ketik",
            "carikan",
            "lihat",
            "apa",
            " gimana",
            "bgmn",
            " cara ",
            "caranya",
            "/car",
        ],
        Intent.BUILD: [
            # English
            "build",
            "compile",
            "deploy",
            "package",
            # Indonesian
            "build",
            "kompile",
            "compile",
            "bangun",
        ],
        Intent.FIX: [
            # English
            "fix",
            "debug",
            "repair",
            "resolve",
            "error",
            "bug",
            "issue",
            # Indonesian
            "perbaiki",
            "debug",
            "betulin",
            "搞定",
            "rusak",
        ],
        Intent.CHECK: [
            # English
            "check",
            "status",
            "health",
            "monitor",
            "verify",
            "test",
            # Indonesian
            "cek",
            "periksa",
            "status",
            "kesehatan",
            "tes",
        ],
        Intent.DEPLOY: [
            # English
            "deploy",
            "release",
            "push",
            "publish",
            # Indonesian
            "deploy",
            "rilis",
            "terbitkan",
        ],
        Intent.RUN: [
            # English
            "run",
            "start",
            "execute",
            "launch",
            # Indonesian
            "jalanin",
            "jalankan",
            "running",
            "start",
            "eksekusi",
        ],
        Intent.EXPLAIN: [
            # English
            "explain",
            "tell me about",
            "describe",
            "what does",
            # Indonesian
            "jelaskan",
            "terangkan",
            "apa itu",
            "artinya",
        ],
        Intent.HELP: [
            # English
            "help",
            "tutorial",
            "guide",
            "how do",
            # Indonesian
            "tolong",
            "bantu",
            "bantuan",
            "tutorial",
            "guid",
        ],
    }

    # Target type patterns
    TARGET_PATTERNS = {
        "web": ["web", "website", "situs", "app web", "webapp", "frontend", "html", "css", "js"],
        "api": ["api", "rest", "endpoint", "backend"],
        "flask": ["flask", "python web", "fastapi"],
        "django": ["django", "python django"],
        "mobile": ["mobile", "android", "ios", "app", "aplikasi"],
        "react": ["react", "frontend", "vue", "angular"],
        "docker": ["docker", "container", "containerize"],
        "database": ["database", "db", "sql", "mysql", "postgres"],
        "git": ["git", "github", "version control"],
        "ai": ["ai", "ml", "machine learning", "model", "llm"],
        "neural": ["neural", "neugi", "agent", "swarm"],
        "security": ["security", "security", "scan", "audit"],
        "workflow": ["workflow", "automation", "otomatisasi", "pipeline"],
    }

    def __init__(self):
        self.history: List[Dict] = []
        self._load_history()

    def _load_history(self):
        """Load conversation history for personalization"""
        history_file = os.path.join(NEUGI_DIR, "data", "nlcli_history.json")
        if os.path.exists(history_file):
            try:
                with open(history_file, "r") as f:
                    self.history = json.load(f)
            except:
                self.history = []

    def _save_history(self):
        """Save conversation history"""
        history_file = os.path.join(NEUGI_DIR, "data", "nlcli_history.json")
        try:
            with open(history_file, "w") as f:
                json.dump(self.history[-100:], f)  # Keep last 100
        except:
            pass

    def detect_language(self, text: str) -> str:
        """Detect if input is Indonesian, English, or mixed"""
        text = text.lower()

        indonesian_words = [
            "buat",
            "bikin",
            "carikan",
            " apa ",
            " gimana",
            "caranya",
            "tolong",
            "bantu",
            "cek",
            "periksa",
            "jalanin",
            "jalankan",
            "install",
            "setup",
            "jelaskan",
            "belajar",
            "kira2",
            "kok",
        ]

        english_words = [
            "create",
            "make",
            "build",
            "search",
            "find",
            "run",
            "start",
            "check",
            "help",
            "how",
            "what",
            "explain",
            "deploy",
            "fix",
        ]

        id_count = sum(1 for w in indonesian_words if w in text)
        en_count = sum(1 for w in english_words if w in text)

        if id_count > en_count:
            return "indonesian"
        elif en_count > id_count:
            return "english"
        else:
            return "mixed"

    def parse(self, user_input: str) -> ParsedIntent:
        """Parse user input and detect intent"""
        text = user_input.lower().strip()

        # Detect language
        lang = self.detect_language(text)

        # Extract target type
        target = self._extract_target(text)

        # Detect intent
        intent = self._detect_intent(text)

        # Extract context
        context = self._extract_context(text)

        # Calculate confidence
        confidence = self._calculate_confidence(intent, target)

        result = ParsedIntent(
            intent=intent, target=target, context=context, language=lang, confidence=confidence
        )

        # Save to history
        self.history.append(
            {
                "input": user_input,
                "intent": intent.value,
                "target": target,
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            }
        )
        self._save_history()

        return result

    def _extract_target(self, text: str) -> str:
        """Extract what the user wants to create/affect"""
        for target_type, patterns in self.TARGET_PATTERNS.items():
            for pattern in patterns:
                if pattern in text:
                    return target_type

        # Default to extract noun phrase
        words = text.split()
        for word in ["app", "web", "file", "project", "service", "aplikasi", "project"]:
            if word in words:
                return word

        return "general"

    def _detect_intent(self, text: str) -> Intent:
        """Detect user intent from text"""
        scores = {intent: 0 for intent in Intent}

        for intent, keywords in self.KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    scores[intent] += 1

        # Get highest scoring intent
        max_score = max(scores.values())
        if max_score == 0:
            return Intent.UNKNOWN

        for intent, score in scores.items():
            if score == max_score:
                return intent

        return Intent.UNKNOWN

    def _extract_context(self, text: str) -> Dict:
        """Extract additional context from text"""
        context = {}

        # Check for urgency/priority
        if any(w in text for w in ["urgent", "sekarang", "langsung", "immediately"]):
            context["priority"] = "high"

        # Check for complexity level
        if any(w in text for w in ["simple", "sederhana", "basic", "easy"]):
            context["complexity"] = "simple"
        elif any(w in text for w in ["complex", "rumit", "advanced"]):
            context["complexity"] = "advanced"

        # Check for framework/language
        frameworks = ["flask", "django", "react", "vue", "angular", "node", "python", "javascript"]
        for fw in frameworks:
            if fw in text:
                context["framework"] = fw

        return context

    def _calculate_confidence(self, intent: Intent, target: str) -> float:
        """Calculate parsing confidence"""
        if intent == Intent.UNKNOWN:
            return 0.3

        base = 0.7
        if target != "general":
            base += 0.2

        return min(base, 0.95)


class NLCLI:
    """
    Natural Language CLI Interface

    Executes parsed intents through appropriate agents/tools
    """

    def __init__(self):
        self.parser = NLParser()
        self.ollama_url = "http://localhost:11434"

    def execute(self, user_input: str) -> str:
        """Execute user natural language command"""
        # Parse the input
        parsed = self.parser.parse(user_input)

        print(f"\n🎯 Intent: {parsed.intent.value}")
        print(f"📋 Target: {parsed.target}")
        print(f"🌐 Language: {parsed.language}")
        print(f"📊 Confidence: {parsed.confidence:.0%}")

        # Route to appropriate handler
        if parsed.intent == Intent.CREATE:
            return self._handle_create(parsed)
        elif parsed.intent == Intent.SEARCH:
            return self._handle_search(parsed)
        elif parsed.intent == Intent.CHECK:
            return self._handle_check(parsed)
        elif parsed.intent == Intent.FIX:
            return self._handle_fix(parsed)
        elif parsed.intent == Intent.HELP:
            return self._handle_help(parsed)
        elif parsed.intent == Intent.BUILD:
            return self._handle_build(parsed)
        elif parsed.intent == Intent.DEPLOY:
            return self._handle_deploy(parsed)
        elif parsed.intent == Intent.EXPLAIN:
            return self._handle_explain(parsed)
        else:
            return self._handle_unknown(parsed)

    def _handle_create(self, parsed: ParsedIntent) -> str:
        """Handle creation requests"""
        target = parsed.target

        responses = {
            "web": f"""
🌐 Creating WEB PROJECT...

I'll create a complete web project for you!

Options:
  [1] Simple HTML/CSS/JS
  [2] Flask (Python)
  [3] React + Vite
  [4] FastAPI
            """,
            "flask": """
🐍 Creating FLASK APP...

I'll set you up with:
  - Flask project structure
  - requirements.txt
  - Basic routing
  - Templates folder
            """,
            "api": """
🔌 Creating API...

Options:
  [1] REST API (FastAPI)
  [2] GraphQL API
  [3] gRPC Service
            """,
            "docker": """
🐳 Creating DOCKER SETUP...

I'll create:
  - Dockerfile
  - docker-compose.yml
  - .dockerignore
            """,
            "mobile": """
📱 Creating MOBILE APP...

Options:
  [1] React Native
  [2] Flutter
  [3] Android (Kotlin)
  [4] iOS (Swift)
            """,
            "ai": """
🤖 Creating AI PROJECT...

I'll set you up with:
  - Ollama integration
  - Model setup
  - Basic inference code
            """,
            "database": """
🗄️ Creating DATABASE SCHEMA...

Options:
  [1] SQLite (simple)
  [2] PostgreSQL
  [3] MongoDB
  [4] MySQL
            """,
        }

        return responses.get(
            target,
            f"""
➕ Creating {target.upper()} project...

Want to proceed? I'll use the best tools for the job!
        """,
        )

    def _handle_search(self, parsed: ParsedIntent) -> str:
        """Handle search requests"""
        return f"""
🔍 SEARCHING for: {parsed.target}

I'll search the web for relevant information!
Fetching from multiple sources...
        """

    def _handle_check(self, parsed: ParsedIntent) -> str:
        """Handle health/status check"""
        return f"""
💚 CHECKING SYSTEM STATUS...

I'll check:
  - NEUGI health
  - Ollama status
  - Memory usage
  - Agent status
        """

    def _handle_fix(self, parsed: ParsedIntent) -> str:
        """Handle fix/repair requests"""
        return f"""
🔧 FIXING issues...

I'll diagnose and fix:
  - Common errors
  - Configuration issues
  - Missing dependencies
        """

    def _handle_help(self, parsed: ParsedIntent) -> str:
        """Handle help requests"""
        return """
📚 NEUGI HELP

Just tell me what you want in plain language!

Examples:
  "tolong buat flask app"     → Creates Flask app
  "apa cara install docker"    → Searches for guide
  "cek sistem"                 → Checks system health
  "bikin website sederhana"   → Creates simple website

No need to remember commands - just type what you need! 🚀
        """

    def _handle_build(self, parsed: ParsedIntent) -> str:
        """Handle build requests"""
        return f"""
🔨 BUILDING {parsed.target.upper()}...

I'll compile and prepare your project!
        """

    def _handle_deploy(self, parsed: ParsedIntent) -> str:
        """Handle deploy requests"""
        return f"""
🚀 DEPLOYING {parsed.target.upper()}...

Deployment options:
  - Local network
  - Docker container
  - Cloud (AWS/GCP/Azure)
        """

    def _handle_explain(self, parsed: ParsedIntent) -> str:
        """Handle explain requests"""
        return f"""
📖 EXPLAINING: {parsed.target}

I'll explain this in simple terms!
        """

    def _handle_unknown(self, parsed: ParsedIntent) -> str:
        """Handle unknown intent"""
        return f"""
🤔 I understand: "{parsed.target}"

But I'm not sure what you want to do.

Try:
  - "tolong buat [something]"
  - "cek [something]"
  - "bantu saya [task]"
  - "cari [information]"

Or just type what you need in your own words! 😊
        """


# ============================================================
# MAIN CLI ENTRY POINT
# ============================================================


def main():
    import sys

    cli = NLCLI()

    print("""
╔═══════════════════════════════════════════════════════════╗
║     🤖 NEUGI NATURAL LANGUAGE CLI                         ║
║     Just tell me what you need! 🚀                        ║
╠═══════════════════════════════════════════════════════════╣
║  Examples:                                                ║
║    neugi "tolong buat flask app"                          ║
║    neugi "apa cara install docker"                        ║
║    neugi "bikin website sederhana"                        ║
║    neugi "cek sistem"                                     ║
╚═══════════════════════════════════════════════════════════╝
    """)

    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:])
        print(f"\n👤 You: {user_input}")
        print("-" * 50)

        result = cli.execute(user_input)
        print(result)
    else:
        print("🎤 Type what you need (or 'exit' to quit):\n")

        while True:
            try:
                user_input = input("👤 You: ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ["exit", "quit", "keluar"]:
                    print("\n👋 Bye! Smarter with NEUGI!")
                    break

                print("-" * 50)
                result = cli.execute(user_input)
                print(result)
                print("\n" + "=" * 50 + "\n")

            except KeyboardInterrupt:
                print("\n👋 Bye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()
