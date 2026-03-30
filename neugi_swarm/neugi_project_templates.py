#!/usr/bin/env python3
"""
🤖 NEUGI ONE-CLICK PROJECT TEMPLATES
======================================

REVOLUTIONARY: User just says what they want - NEUGI builds it!

Just tell NEUGI:
  • "Build me a Flask web app"
  • "Create a React + Node project"
  • "Setup a Docker dev environment"
  • "Make a mobile app"

And NEUGI will automatically scaffold the entire project!

Version: 1.0.0
"""

import os
import shutil
import subprocess
from typing import Dict, List, Optional
from dataclasses import dataclass


NEUGI_DIR = os.path.expanduser("~/neugi")
WORKSPACE_DIR = os.path.expanduser("~/neugi/workspace")
os.makedirs(WORKSPACE_DIR, exist_ok=True)


class Colors:
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"


@dataclass
class ProjectTemplate:
    """Project template definition"""

    id: str
    name: str
    description: str
    keywords: List[str]
    files: Dict[str, str]  # filename -> content
    commands: List[str]  # setup commands
    requirements: List[str]  # package requirements


class ProjectFactory:
    """
    One-Click Project Generation

    The ultimate beginner-friendly feature!
    """

    def __init__(self):
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict[str, ProjectTemplate]:
        """Load all available templates"""
        return {
            "flask": ProjectTemplate(
                id="flask",
                name="Flask Web App",
                description="Python Flask web application",
                keywords=["flask", "python web", "api", "backend"],
                files={
                    "app.py": """from flask import Flask, jsonify
app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({"message": "Hello from NEUGI!", "status": "ok"})

@app.route("/api/health")
def health():
    return jsonify({"status": "healthy"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
""",
                    "requirements.txt": "flask\ngunicorn\npython-dotenv\n",
                    ".env": "FLASK_ENV=development\nDEBUG=True\n",
                    "README.md": """# Flask App

## Setup
```bash
pip install -r requirements.txt
python app.py
```

## Endpoints
- `/` - Home
- `/api/health` - Health check
""",
                },
                commands=["pip install -r requirements.txt"],
                requirements=["flask"],
            ),
            "react": ProjectTemplate(
                id="react",
                name="React + Vite App",
                description="Modern React frontend with Vite",
                keywords=["react", "frontend", "vite", "javascript", "ui"],
                files={
                    "src/App.jsx": """function App() {
  return (
    <div style={{padding: '20px', fontFamily: 'system-ui'}}>
      <h1>🚀 Hello from NEUGI!</h1>
      <p>Your React app is ready.</p>
    </div>
  );
}
export default App;
""",
                    "src/main.jsx": "import React from 'react'\nimport ReactDOM from 'react-dom/client'\nimport App from './App.jsx'\n\nReactDOM.createRoot(document.getElementById('root')).render(<App />)\n",
                    "index.html": """<!DOCTYPE html>
<html>
  <head>
    <title>NEUGI App</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
""",
                    "package.json": """{
  "name": "neugi-app",
  "private": true,
  "version": "0.0.1",
  "scripts": {
    "dev": "vite",
    "build": "vite build"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.0.0",
    "vite": "^5.0.0"
  }
}
""",
                    "vite.config.js": "import { defineConfig } from 'vite'\nimport react from '@vitejs/plugin-react'\n\nexport default defineConfig({\n  plugins: [react()]\n})\n",
                    "README.md": """# React App (Vite)

## Setup
```bash
npm install
npm run dev
```
""",
                },
                commands=["npm install"],
                requirements=["node", "npm"],
            ),
            "docker": ProjectTemplate(
                id="docker",
                name="Docker Dev Environment",
                description="Containerized development setup",
                keywords=["docker", "container", "devops", "compose"],
                files={
                    "Dockerfile": """FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["python", "app.py"]
""",
                    "docker-compose.yml": """version: '3.8'
services:
  app:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - .:/app
    environment:
      - FLASK_ENV=development
""",
                    ".dockerignore": "__pycache__\n*.pyc\n.git\nnode_modules\n",
                    "requirements.txt": "flask\ngunicorn\n",
                    "README.md": """# Docker Setup

## Build & Run
```bash
docker-compose up --build
```
""",
                },
                commands=["docker-compose up --build"],
                requirements=["docker", "docker-compose"],
            ),
            "api": ProjectTemplate(
                id="api",
                name="REST API (FastAPI)",
                description="High-performance Python API",
                keywords=["fastapi", "api", "rest", "python", "backend"],
                files={
                    "main.py": """from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="NEUGI API")

class Item(BaseModel):
    name: str
    description: str = None
    price: float

@app.get("/")
def read_root():
    return {"message": "NEUGI API", "version": "1.0.0"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/items/")
def create_item(item: Item):
    return {"item": item.name, "status": "created"}
""",
                    "requirements.txt": "fastapi\nuvicorn\npydantic\n",
                    "README.md": """# FastAPI REST API

## Run
```bash
uvicorn main:app --reload
```

## Endpoints
- GET `/` - Root
- GET `/health` - Health check
- POST `/items/` - Create item
""",
                },
                commands=["pip install -r requirements.txt", "uvicorn main:app --reload"],
                requirements=["fastapi"],
            ),
            "ml": ProjectTemplate(
                id="ml",
                name="ML Project",
                description="Machine learning starter with PyTorch",
                keywords=["ml", "machine learning", "pytorch", "ai", "model"],
                files={
                    "train.py": """import torch
import torch.nn as nn

class SimpleModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc = nn.Linear(784, 10)
    
    def forward(self, x):
        return self.fc(x)

def train():
    model = SimpleModel()
    print(f"Model: {model}")
    print("Training not implemented yet!")

if __name__ == "__main__":
    train()
""",
                    "requirements.txt": "torch\nnumpy\nmatplotlib\n",
                    "README.md": """# ML Project

## Setup
```bash
pip install -r requirements.txt
python train.py
```

## Features
- PyTorch starter
- Simple neural network template
- Ready for training
""",
                },
                commands=["pip install -r requirements.txt"],
                requirements=["pytorch"],
            ),
            "cli": ProjectTemplate(
                id="cli",
                name="CLI Tool",
                description="Command-line tool with Click",
                keywords=["cli", "click", "terminal", "command"],
                files={
                    "cli.py": '''#!/usr/bin/env python3
import click

@click.group()
def cli():
    """NEUGI CLI Tool"""
    pass

@cli.command()
@click.argument("name")
def greet(name):
    click.echo(f"Hello, {name}!")

@cli.command()
def version():
    click.echo("Version: 1.0.0")

if __name__ == "__main__":
    cli()
''',
                    "requirements.txt": "click\ncolorama\n",
                    "README.md": """# CLI Tool

## Install & Run
```bash
pip install -r requirements.txt
python cli.py greet World
python cli.py version
```
""",
                },
                commands=["pip install -r requirements.txt"],
                requirements=["click"],
            ),
            "discord": ProjectTemplate(
                id="discord",
                name="Discord Bot",
                description="Discord bot with Python",
                keywords=["discord", "bot", "discord.py", "social"],
                files={
                    "bot.py": """import os
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print(f"Bot is ready!")

@bot.command()
async def hello(ctx):
    await ctx.send("Hello from NEUGI bot! 👋")

@bot.command()
async def info(ctx):
    await ctx.send("NEUGI Discord Bot v1.0.0")

# Run with: python bot.py
# Add your token in DISCORD_TOKEN env var
if __name__ == "__main__":
    token = os.environ.get("DISCORD_TOKEN", "YOUR_TOKEN_HERE")
    bot.run(token)
""",
                    "requirements.txt": "discord.py\npython-dotenv\n",
                    ".env": "DISCORD_TOKEN=your_token_here\n",
                    "README.md": """# Discord Bot

## Setup
1. Create a bot at Discord Developer Portal
2. Copy token to .env
3. Run: python bot.py

## Commands
- !hello - Greet
- !info - Bot info
""",
                },
                commands=["pip install -r requirements.txt"],
                requirements=["discord.py"],
            ),
            "telegram": ProjectTemplate(
                id="telegram",
                name="Telegram Bot",
                description="Telegram bot with Python",
                keywords=["telegram", "bot", "python-telegram-bot"],
                files={
                    "bot.py": """import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

async def start(update: Update, context):
    await update.message.reply_text("Hello from NEUGI Bot! 👋")

async def help_cmd(update: Update, context):
    await update.message.reply_text("Commands: /start, /help, /echo")

async def echo(update: Update, context):
    await update.message.reply_text(update.message.text)

if __name__ == "__main__":
    token = os.environ.get("TELEGRAM_TOKEN", "YOUR_TOKEN_HERE")
    app = Application.builder().token(token).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    
    print("Bot running...")
    app.run_polling(allow_upserting=True)
""",
                    "requirements.txt": "python-telegram-bot\npython-dotenv\n",
                    ".env": "TELEGRAM_TOKEN=your_token_here\n",
                    "README.md": """# Telegram Bot

## Setup
1. Create bot via @BotFather
2. Copy token to .env
3. Run: python bot.py

## Usage
- /start - Start the bot
- /help - Get help
- Any text - Echo back
""",
                },
                commands=["pip install -r requirements.txt"],
                requirements=["python-telegram-bot"],
            ),
        }

    def list_templates(self) -> List[Dict]:
        """List all available templates"""
        return [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "keywords": ", ".join(t.keywords),
            }
            for t in self.templates.values()
        ]

    def detect_template(self, user_input: str) -> Optional[str]:
        """Detect which template matches user request"""
        user_input = user_input.lower()

        scores = {}
        for template_id, template in self.templates.items():
            score = 0
            for keyword in template.keywords:
                if keyword.lower() in user_input:
                    score += 1
            if score > 0:
                scores[template_id] = score

        if not scores:
            return None

        return max(scores, key=scores.get)

    def create_project(self, template_id: str, project_name: str = None) -> Dict:
        """Create project from template"""
        template = self.templates.get(template_id)
        if not template:
            return {"error": f"Template {template_id} not found"}

        project_name = project_name or f"project_{template_id}"
        project_dir = os.path.join(WORKSPACE_DIR, project_name)

        # Create directory
        os.makedirs(project_dir, exist_ok=True)

        # Create files
        for filename, content in template.files.items():
            filepath = os.path.join(project_dir, filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True) if os.path.dirname(
                filepath
            ) else None
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

        # Save template info
        info = {
            "template": template_id,
            "name": template.name,
            "created_at": __import__("datetime").datetime.now().isoformat(),
            "files": list(template.files.keys()),
            "commands": template.commands,
        }

        with open(os.path.join(project_dir, ".neugi.json"), "w") as f:
            json.dump(info, f, indent=2)

        return {
            "success": True,
            "project_name": project_name,
            "directory": project_dir,
            "files_created": len(template.files),
            "setup_commands": template.commands,
        }

    def suggest_template(self, user_input: str) -> Dict:
        """Suggest template based on user input"""
        detected = self.detect_template(user_input)

        if detected:
            template = self.templates[detected]
            return {
                "suggestion": detected,
                "template_name": template.name,
                "confidence": "high",
                "description": template.description,
            }

        # No match - ask user
        return {
            "suggestion": None,
            "message": "I couldn't determine what you want to build.",
            "available": [t.id for t in self.templates.values()],
        }


def run_project_creator():
    """Interactive CLI for project creation"""
    factory = ProjectFactory()

    print(f"""
{Colors.CYAN}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════╗
║         🤖 NEUGI ONE-CLICK PROJECT CREATOR                    ║
║                                                               ║
║     Just tell me what you want to build!                      ║
╚═══════════════════════════════════════════════════════════════╝
{Colors.END}
    """)

    print("Available templates:")
    for t in factory.list_templates():
        print(f"  • {t['name']}: {t['description']}")

    print("\n" + "=" * 50)
    user_input = input(f"{Colors.CYAN}What do you want to build? {Colors.END}").strip()

    if not user_input:
        print(f"{Colors.RED}Please enter a project type!{Colors.END}")
        return

    # Detect and suggest
    result = factory.suggest_template(user_input)

    if result.get("suggestion"):
        print(f"""
{Colors.GREEN}I think you want: {result["template_name"]}{Colors.END}

Description: {result["description"]}
        """)

        confirm = input(f"{Colors.YELLOW}Create this project? (y/n): {Colors.END}").strip().lower()

        if confirm == "y":
            project_name = (
                input(f"Project name [{result['suggestion']}]: ").strip() or result["suggestion"]
            )
            result = factory.create_project(result["suggestion"], project_name)

            if result.get("success"):
                print(f"""
{Colors.GREEN}{Colors.BOLD}✅ PROJECT CREATED!{Colors.END}

Location: {result["directory"]}
Files: {result["files_created"]}

To get started:
  cd {result["project_name"]}
  {" && ".join(result["setup_commands"])}
                """)
            else:
                print(f"{Colors.RED}Error: {result.get('error')}{Colors.END}")
        else:
            print(f"{Colors.YELLOW}Ok, cancelled!{Colors.END}")
    else:
        # Ask which template
        print(f"""
{Colors.YELLOW}Available templates:{Colors.END}
        """)
        for t in factory.list_templates():
            print(f"  [{t['id']:10}] {t['name']}")

        template_id = input(f"\n{Colors.CYAN}Choose template: {Colors.END}").strip()

        if template_id in factory.templates:
            project_name = input(f"Project name: ").strip() or f"project_{template_id}"
            result = factory.create_project(template_id, project_name)

            if result.get("success"):
                print(f"""
{Colors.GREEN}{Colors.BOLD}✅ SUCCESS!{Colors.END}

Directory: {result["directory"]}
Run: cd {result["project_name"]} && {" && ".join(result["setup_commands"])}
                """)
        else:
            print(f"{Colors.RED}Invalid template!{Colors.END}")


if __name__ == "__main__":
    import json

    run_project_creator()
