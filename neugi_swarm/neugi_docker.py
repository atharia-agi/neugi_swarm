#!/usr/bin/env python3
"""
🤖 NEUGI DOCKER INTEGRATION
==============================

Docker container management:
- List containers
- Start/stop/restart
- View logs
- Execute commands
- Build images

Version: 1.0
Date: March 15, 2026
"""

import os
import json
import subprocess
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class Container:
    """Docker container"""

    id: str
    name: str
    image: str
    status: str
    ports: str
    created: str


class DockerManager:
    """
    NEUGI Docker Integration

    Manage Docker containers from NEUGI
    """

    def __init__(self):
        self._check_docker()

    def _check_docker(self):
        """Check if Docker is available"""
        try:
            result = subprocess.run(["docker", "version"], capture_output=True, text=True)
            self.available = result.returncode == 0
        except FileNotFoundError:
            self.available = False

    def list_containers(self, all: bool = True) -> List[Container]:
        """List containers"""
        if not self.available:
            return []

        result = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--format",
                "{{.ID}}|{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}|{{.CreatedAt}}",
            ],
            capture_output=True,
            text=True,
        )

        containers = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split("|")
                if len(parts) >= 6:
                    containers.append(
                        Container(
                            id=parts[0],
                            name=parts[1],
                            image=parts[2],
                            status=parts[3],
                            ports=parts[4],
                            created=parts[5],
                        )
                    )

        return containers

    def start(self, container: str) -> Dict:
        """Start container"""
        result = subprocess.run(["docker", "start", container], capture_output=True, text=True)
        return {"success": result.returncode == 0, "output": result.stdout}

    def stop(self, container: str) -> Dict:
        """Stop container"""
        result = subprocess.run(["docker", "stop", container], capture_output=True, text=True)
        return {"success": result.returncode == 0, "output": result.stdout}

    def restart(self, container: str) -> Dict:
        """Restart container"""
        result = subprocess.run(["docker", "restart", container], capture_output=True, text=True)
        return {"success": result.returncode == 0, "output": result.stdout}

    def remove(self, container: str, force: bool = False) -> Dict:
        """Remove container"""
        cmd = ["docker", "rm"]
        if force:
            cmd.append("-f")
        cmd.append(container)

        result = subprocess.run(cmd, capture_output=True, text=True)
        return {"success": result.returncode == 0, "output": result.stdout}

    def logs(self, container: str, tail: int = 100) -> str:
        """Get container logs"""
        result = subprocess.run(
            ["docker", "logs", "--tail", str(tail), container], capture_output=True, text=True
        )
        return result.stdout + result.stderr

    def exec(self, container: str, command: str) -> Dict:
        """Execute command in container"""
        result = subprocess.run(
            ["docker", "exec", container, "sh", "-c", command], capture_output=True, text=True
        )
        return {"success": result.returncode == 0, "output": result.stdout, "error": result.stderr}

    def images(self) -> List[Dict]:
        """List images"""
        result = subprocess.run(
            ["docker", "images", "--format", "{{.Repository}}|{{.Tag}}|{{.ID}}|{{.Size}}"],
            capture_output=True,
            text=True,
        )

        images = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split("|")
                if len(parts) >= 4:
                    images.append(
                        {"repository": parts[0], "tag": parts[1], "id": parts[2], "size": parts[3]}
                    )

        return images

    def pull(self, image: str) -> Dict:
        """Pull image"""
        result = subprocess.run(["docker", "pull", image], capture_output=True, text=True)
        return {"success": result.returncode == 0, "output": result.stdout}

    def build(self, path: str, tag: str, dockerfile: str = "Dockerfile") -> Dict:
        """Build image"""
        result = subprocess.run(
            ["docker", "build", "-f", dockerfile, "-t", tag, path], capture_output=True, text=True
        )
        return {"success": result.returncode == 0, "output": result.stdout, "error": result.stderr}

    def run(
        self,
        image: str,
        name: str = None,
        command: str = None,
        detach: bool = True,
        ports: Dict = None,
    ) -> Dict:
        """Run container"""
        cmd = ["docker", "run"]

        if detach:
            cmd.append("-d")

        if name:
            cmd.extend(["--name", name])

        if ports:
            for host, container in ports.items():
                cmd.extend(["-p", f"{host}:{container}"])

        cmd.append(image)

        if command:
            cmd.extend(command.split())

        result = subprocess.run(cmd, capture_output=True, text=True)
        return {"success": result.returncode == 0, "output": result.stdout}

    def stats(self) -> List[Dict]:
        """Get container stats"""
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}"],
            capture_output=True,
            text=True,
        )

        stats = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split("|")
                if len(parts) >= 3:
                    stats.append({"name": parts[0], "cpu": parts[1], "memory": parts[2]})

        return stats


# ========== CLI ==========


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Docker Integration")
    parser.add_argument(
        "action",
        choices=[
            "list",
            "start",
            "stop",
            "restart",
            "logs",
            "exec",
            "images",
            "pull",
            "build",
            "run",
            "stats",
        ],
    )
    parser.add_argument("--container", help="Container name/ID")
    parser.add_argument("--image", help="Image name")
    parser.add_argument("--command", help="Command to execute")
    parser.add_argument("--name", help="Container name")

    args = parser.parse_args()

    docker = DockerManager()

    if not docker.available:
        print("Docker is not available")
        return

    if args.action == "list":
        print("\n🐳 Docker Containers")
        print("=" * 80)

        containers = docker.list_containers()
        for c in containers:
            print(f"{c.name:<20} {c.image:<30} {c.status}")

    elif args.action == "images":
        print("\n🐳 Docker Images")
        print("=" * 60)

        images = docker.images()
        for img in images:
            print(f"{img['repository']:<30} {img['tag']:<10} {img['size']}")

    elif args.action == "stats":
        print("\n📊 Container Stats")
        print("=" * 40)

        stats = docker.stats()
        for s in stats:
            print(f"{s['name']:<20} CPU: {s['cpu']:<10} MEM: {s['memory']}")

    elif args.action == "logs":
        print(docker.logs(args.container))

    elif args.action == "start":
        result = docker.start(args.container)
        print(f"Started: {result['success']}")

    elif args.action == "stop":
        result = docker.stop(args.container)
        print(f"Stopped: {result['success']}")

    elif args.action == "restart":
        result = docker.restart(args.container)
        print(f"Restarted: {result['success']}")

    elif args.action == "exec":
        result = docker.exec(args.container, args.command)
        print(result["output"] if result["success"] else result["error"])

    elif args.action == "pull":
        print(f"Pulling {args.image}...")
        result = docker.pull(args.image)
        print(f"Success: {result['success']}")

    elif args.action == "build":
        print(f"Building {args.image}...")
        result = docker.build(".", args.image)
        print(f"Success: {result['success']}")

    elif args.action == "run":
        result = docker.run(args.image, args.name)
        print(f"Running: {result['success']}")


if __name__ == "__main__":
    main()
