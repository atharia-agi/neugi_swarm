#!/usr/bin/env python3
"""
🤖 NEUGI CLI FRAMEWORK
=========================

Build CLI apps:
- Commands
- Arguments
- Auto-help

Version: 1.0
Date: March 16, 2026
"""

from typing import Dict, Callable


class CLI:
    def __init__(self, name: str):
        self.name = name
        self.commands: Dict[str, Callable] = {}

    def command(self, name: str):
        def decorator(func):
            self.commands[name] = func
            return func

        return decorator

    def run(self, args: list = None):
        if not args:
            print(f"{self.name} - Available commands:")
            for cmd in self.commands:
                print(f"  {cmd}")
        elif args[0] in self.commands:
            self.commands[args[0]](*args[1:])
        else:
            print(f"Unknown command: {args[0]}")


cli = CLI("neugi")


@cli.command("hello")
def hello():
    print("Hello from NEUGI!")


if __name__ == "__main__":
    import sys

    cli.run(sys.argv[1:] if len(sys.argv) > 1 else None)
