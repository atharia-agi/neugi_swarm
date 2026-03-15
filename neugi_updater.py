#!/usr/bin/env python3
"""
🤖 NEUGI AUTO-UPDATER
======================

Version: 1.0
Date: March 14, 2026
"""

import os
import requests
import subprocess
import shutil
from typing import Dict, Optional


class AutoUpdater:
    """Auto-update NEUGI from GitHub"""

    REPO_OWNER = "atharia-agi"
    REPO_NAME = "neugi_swarm"
    CURRENT_VERSION = "15.2"

    def __init__(self):
        self.update_url = (
            f"https://api.github.com/repos/{self.REPO_OWNER}/{self.REPO_NAME}/releases/latest"
        )
        self.download_url = (
            f"https://github.com/{self.REPO_OWNER}/{self.REPO_NAME}/archive/refs/heads/master.zip"
        )

    def get_latest_version(self) -> Optional[str]:
        """Get latest version from GitHub"""
        try:
            response = requests.get(self.update_url, timeout=10)
            if response.ok:
                data = response.json()
                return data.get("tag_name", "").lstrip("v")
        except Exception:
            pass
        return None

    def check_for_update(self) -> Dict:
        """Check if update available"""
        current = self.CURRENT_VERSION
        latest = self.get_latest_version()

        result = {
            "current": current,
            "latest": latest,
            "update_available": False,
        }

        if latest and latest != current:
            # Simple version comparison
            try:
                curr_parts = [int(x) for x in current.split(".")]
                latest_parts = [int(x) for x in latest.split(".")]

                for curr, latest in zip(curr_parts, latest_parts):
                    if latest > curr:
                        result["update_available"] = True
                        break
                    elif latest < curr:
                        break
            except Exception:
                pass

        return result

    def download_update(self, target_dir: str = None) -> Dict:
        """Download latest version"""
        if target_dir is None:
            target_dir = os.path.expanduser("~/neugi_update")

        result = {"success": False, "path": target_dir, "message": ""}

        try:
            # Create temp directory
            os.makedirs(target_dir, exist_ok=True)

            # Download
            print("📥 Downloading NEUGI update...")
            response = requests.get(self.download_url, stream=True, timeout=60)

            if response.ok:
                zip_path = os.path.join(target_dir, "neugi.zip")
                with open(zip_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                # Extract
                print("📦 Extracting...")
                subprocess.run(["unzip", "-o", zip_path, "-d", target_dir], capture_output=True)

                result["success"] = True
                result["message"] = f"Update downloaded to {target_dir}"
                result["extracted"] = os.path.join(target_dir, f"{self.REPO_NAME}-master")
            else:
                result["message"] = "Download failed"

        except Exception as e:
            result["message"] = f"Error: {str(e)}"

        return result

    def apply_update(self, backup: bool = True) -> Dict:
        """Apply update (replaces files)"""
        result = {"success": False, "message": ""}

        neugi_dir = os.path.expanduser("~/neugi")
        backup_dir = os.path.expanduser("~/neugi_backup")

        try:
            # Backup
            if backup and os.path.exists(neugi_dir):
                print(f"📁 Backing up to {backup_dir}...")
                if os.path.exists(backup_dir):
                    shutil.rmtree(backup_dir)
                shutil.copytree(neugi_dir, backup_dir)

            # Download
            dl_result = self.download_update()
            if not dl_result["success"]:
                return dl_result

            # Copy files
            source = dl_result["extracted"]
            print("🔄 Updating files...")

            # Copy Python files
            for f in os.listdir(source):
                if f.endswith(".py") or f in [
                    "install.sh",
                    "install.bat",
                    "neugi",
                    "neugi.bat",
                    "neugi.service",
                ]:
                    src_path = os.path.join(source, f)
                    dst_path = os.path.join(neugi_dir, f)
                    if os.path.exists(src_path):
                        subprocess.run(["cp", src_path, dst_path], check=True)

            result["success"] = True
            result["message"] = "Update applied! Restart NEUGI to use new version."

        except Exception as e:
            result["message"] = f"Update failed: {str(e)}"

        return result


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Auto-Updater")
    parser.add_argument("action", choices=["check", "download", "apply"], help="Action to perform")
    parser.add_argument("--backup", action="store_true", default=True, help="Backup before update")

    args = parser.parse_args()

    updater = AutoUpdater()

    if args.action == "check":
        print("🔍 Checking for updates...")
        result = updater.check_for_update()
        print(f"Current version: {result['current']}")
        print(f"Latest version: {result['latest']}")
        print(f"Update available: {result['update_available']}")

    elif args.action == "download":
        print("📥 Downloading update...")
        result = updater.download_update()
        print(f"Success: {result['success']}")
        print(f"Message: {result['message']}")

    elif args.action == "apply":
        print("🔄 Applying update...")
        result = updater.apply_update(backup=args.backup)
        print(f"Success: {result['success']}")
        print(f"Message: {result['message']}")


if __name__ == "__main__":
    main()
