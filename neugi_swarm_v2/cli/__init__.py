"""
NEUGI v2 CLI & Wizard
=====================

Production-ready command-line interface and interactive setup wizard
for the NEUGI Swarm v2 agentic framework.

Usage:
    from neugi_swarm_v2.cli import NeugiCLI, GeniusWizard, InteractiveChat

    cli = NeugiCLI()
    cli.run()
"""

from __future__ import annotations

from neugi_swarm_v2.cli.cli import CLICommand, CommandResult, NeugiCLI
from neugi_swarm_v2.cli.genius_wizard import GeniusWizard
from neugi_swarm_v2.cli.interactive import ChatUI, CommandPalette, InteractiveChat

__all__ = [
    "NeugiCLI",
    "CLICommand",
    "CommandResult",
    "GeniusWizard",
    "InteractiveChat",
    "ChatUI",
    "CommandPalette",
]
