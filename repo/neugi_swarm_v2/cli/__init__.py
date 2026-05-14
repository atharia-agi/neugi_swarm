"""
NEUGI v2 CLI & Wizard
=====================

Production-ready command-line interface and interactive setup wizard
for the NEUGI Swarm v2 agentic framework.

Usage:
    from neugi_swarm_v2.cli import NeugiCLI, SetupWizard, InteractiveChat

    cli = NeugiCLI()
    cli.run()
"""

from __future__ import annotations

from neugi_swarm_v2.cli.cli import CLICommand, CommandResult, NeugiCLI
from neugi_swarm_v2.cli.interactive import ChatUI, CommandPalette, InteractiveChat
from neugi_swarm_v2.cli.wizard import SetupWizard, WizardState, WizardStep

__all__ = [
    "NeugiCLI",
    "CLICommand",
    "CommandResult",
    "SetupWizard",
    "WizardStep",
    "WizardState",
    "InteractiveChat",
    "ChatUI",
    "CommandPalette",
]
