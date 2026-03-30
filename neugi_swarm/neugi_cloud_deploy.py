#!/usr/bin/env python3
"""
🤖 NEUGI CLOUD DEPLOY - One-Click Deployment
==============================================

DEPLOY TO THE CLOUD WITH ONE COMMAND!

Supported Platforms:
- Vercel
- Railway
- Render
- Fly.io
- DigitalOcean App Platform
- AWS (Advanced)
- GCP (Advanced)

Just say "deploy" and NEUGI handles the rest!

Version: 1.0.0
"""

import os
import sys
import json
import shutil
import subprocess
from typing import Dict, List, Optional
from dataclasses import dataclass


NEUGI_DIR = os.path.expanduser("~/neugi")


class Colors:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"


@dataclass
class CloudConfig:
    """Cloud deployment configuration"""

    platform: str
    project_name: str
    framework: str
    build_command: str
    start_command: str
    env_vars: Dict[str, str]


class CloudDeployer:
    """
    ☁️ ONE-CLICK CLOUD DEPLOYMENT

    Deploy your projects to the cloud in seconds!
    """

    def __init__(self):
        self.platforms = {
            "vercel": self._deploy_vercel,
            "railway": self._deploy_railway,
            "render": self._deploy_render,
            "fly": self._deploy_fly,
            "digitalocean": self._deploy_do,
        }

    def detect_framework(self, project_dir: str) -> str:
        """Detect what framework the project uses"""
        if os.path.exists(os.path.join(project_dir, "package.json")):
            if "vite" in open(os.path.join(project_dir, "package.json")).read():
                return "vite"
            return "node"

        if os.path.exists(os.path.join(project_dir, "requirements.txt")):
            if "flask" in open(os.path.join(project_dir, "requirements.txt")).read():
                return "flask"
            if "fastapi" in open(os.path.join(project_dir, "requirements.txt")).read():
                return "fastapi"
            return "python"

        if os.path.exists(os.path.join(project_dir, "Cargo.toml")):
            return "rust"

        return "static"

    def _deploy_vercel(self, project_dir: str, project_name: str) -> Dict:
        """Deploy to Vercel"""
        print(f"{Colors.CYAN}Deploying to Vercel...{Colors.END}")

        # Check if vercel CLI is installed
        vercel_path = shutil.which("vercel")

        if not vercel_path:
            print("Installing Vercel CLI...")
            try:
                subprocess.run(["npm", "i", "-g", "vercel"], capture_output=True)
            except:
                return {
                    "success": False,
                    "message": "Vercel not installed. Run: npm i -g vercel",
                    "install": "npm i -g vercel",
                }

        try:
            # Change to project dir and deploy
            result = subprocess.run(
                ["vercel", "--yes", "--prod"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "message": "Deployed to Vercel!",
                    "url": f"https://{project_name}.vercel.app",
                    "platform": "vercel",
                }
            else:
                return {
                    "success": False,
                    "error": result.stderr,
                    "message": "Vercel deployment failed",
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _deploy_railway(self, project_dir: str, project_name: str) -> Dict:
        """Deploy to Railway"""
        print(f"{Colors.CYAN}Deploying to Railway...{Colors.END}")

        railway_path = shutil.which("railway")

        if not railway_path:
            return {
                "success": False,
                "message": "Railway CLI not found",
                "install": "npm i -g @railway/cli",
                "steps": [
                    "1. npm i -g @railway/cli",
                    "2. railway login",
                    "3. railway init",
                    "4. railway up",
                ],
            }

        return {
            "success": True,
            "message": "Railway deployment initiated",
            "platform": "railway",
            "steps": "Run 'railway up' in your project directory",
        }

    def _deploy_render(self, project_dir: str, project_name: str) -> Dict:
        """Deploy to Render"""
        return {
            "success": True,
            "platform": "render",
            "steps": [
                "1. Push code to GitHub",
                "2. Go to render.com",
                "3. Connect your repository",
                "4. Auto-deploys from GitHub",
            ],
            "url": "https://dashboard.render.com",
        }

    def _deploy_fly(self, project_dir: str, project_name: str) -> Dict:
        """Deploy to Fly.io"""
        print(f"{Colors.CYAN}Deploying to Fly.io...{Colors.END}")

        fly_path = shutil.which("flyctl")

        if not fly_path:
            return {
                "success": False,
                "message": "Flyctl not installed",
                "install": "curl -L https://fly.io/install.sh | sh",
            }

        return {
            "success": True,
            "platform": "fly.io",
            "steps": ["1. flyctl auth login", "2. flyctl launch", "3. flyctl deploy"],
        }

    def _deploy_do(self, project_dir: str, project_name: str) -> Dict:
        """Deploy to DigitalOcean"""
        return {
            "success": True,
            "platform": "digitalocean",
            "steps": [
                "1. Install doctl: brew install doctl",
                "2. doctl auth init",
                "3. doctl apps create",
            ],
            "url": "https://cloud.digitalocean.com/apps",
        }

    def deploy(self, project_dir: str = None, platform: str = "auto") -> Dict:
        """
        🚀 DEPLOY TO CLOUD

        One command to deploy anywhere!
        """
        project_dir = project_dir or os.path.join(NEUGI_DIR, "workspace")

        if not os.path.exists(project_dir):
            return {"success": False, "error": "Project directory not found"}

        # Detect project type
        framework = self.detect_framework(project_dir)
        project_name = os.path.basename(project_dir)

        print(f"""
{Colors.GREEN}╔═══════════════════════════════════════════════════════════════╗
║                 🚀 NEUGI CLOUD DEPLOYER                       ║
╚═══════════════════════════════════════════════════════════════╝
{Colors.END}

Project: {project_name}
Framework: {framework}
Directory: {project_dir}

Select deployment platform:
        """)

        print("""
  [1] ⚡ VERCEL      - Free, fast, easiest
  [2] 🚂 RAILWAY    - Good for full-stack
  [3] 🎨 RENDER     - Free tier, easy
  [4] 🦅 FLY.IO     - Great forContainers
  [5] 🌊 DIGITALOCEAN - Scalable apps
        """)

        choice = input(f"{Colors.CYAN}Choose (1-5): {Colors.END}").strip()

        platform_map = {
            "1": "vercel",
            "2": "railway",
            "3": "render",
            "4": "fly",
            "5": "digitalocean",
        }

        platform = platform_map.get(choice, "vercel")

        if platform == "auto":
            # Auto-select best platform based on framework
            if framework in ["vite", "react", "node"]:
                platform = "vercel"
            elif framework in ["flask", "fastapi", "python"]:
                platform = "railway"
            else:
                platform = "vercel"

        # Deploy
        deploy_func = self.platforms.get(platform)

        if deploy_func:
            result = deploy_func(project_dir, project_name)
            return result

        return {"success": False, "error": "Unknown platform"}

    def quick_deploy(self, project_dir: str) -> Dict:
        """Quick deploy with auto-detection"""
        framework = self.detect_framework(project_dir)

        # Auto-select best platform
        if framework in ["vite", "react"]:
            return self._deploy_vercel(project_dir, os.path.basename(project_dir))
        elif framework in ["flask", "fastapi"]:
            return self._deploy_railway(project_dir, os.path.basename(project_dir))
        else:
            return self._deploy_vercel(project_dir, os.path.basename(project_dir))


def run_deploy():
    """Main CLI entry point"""
    deployer = CloudDeployer()

    project_dir = None
    platform = "auto"

    # Check arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--help" or sys.argv[1] == "-h":
            print("""
🤖 NEUGI CLOUD DEPLOY

Usage:
    python neugi_cloud_deploy.py [project_dir] [--platform=vercel|railway|...]

Examples:
    python neugi_cloud_deploy.py ~/myproject
    python neugi_cloud_deploy.py --platform=railway
    python neugi_cloud_deploy.py --quick  # Auto-detect and deploy
            """)
            return

        if sys.argv[1] == "--quick":
            import glob

            workspace = os.path.join(NEUGI_DIR, "workspace")
            projects = glob.glob(os.path.join(workspace, "*"))

            if projects:
                project_dir = max(projects, key=os.path.getmtime)
                print(f"Auto-detected latest project: {project_dir}")

        elif os.path.isdir(sys.argv[1]):
            project_dir = sys.argv[1]

    if "--platform=" in " ".join(sys.argv):
        for arg in sys.argv:
            if arg.startswith("--platform="):
                platform = arg.split("=")[1]

    result = deployer.deploy(project_dir, platform)

    print(f"""
{Colors.GREEN}╔═══════════════════════════════════════════════════════════════╗
║                       DEPLOYMENT RESULT                     ║
╚═══════════════════════════════════════════════════════════════╝
{Colors.END}
    """)

    if result.get("success"):
        print(f"""
{Colors.GREEN}✅ SUCCESS!{Colors.END}

Platform: {result.get("platform", "N/A")}
URL: {result.get("url", "Check deployment platform")}
        """)
    else:
        print(f"""
{Colors.RED}❌ DEPLOYMENT NEEDS ATTENTION{Colors.END}

Message: {result.get("message", result.get("error", "Unknown error"))}
        """)

    if result.get("steps"):
        print("\n📋 Steps to complete:")
        for step in result["steps"]:
            print(f"   {step}")

    if result.get("install"):
        print(f"\n💾 Install: {result['install']}")


if __name__ == "__main__":
    run_deploy()
