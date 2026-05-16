"""Deprecated compatibility wrapper for the canonical setup wizard."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from neugi_swarm_v2.cli.genius_wizard import GeniusWizard


@dataclass
class WizardState:
    """Minimal legacy state container kept for import compatibility."""

    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class WizardStep:
    """Minimal legacy step container kept for import compatibility."""

    name: str = ""
    title: str = ""
    completed: bool = False


class SetupWizard(GeniusWizard):
    """Backward-compatible alias for :class:`GeniusWizard`.

    Older code imported ``SetupWizard`` from this module. The real setup flow is
    now centralized in ``cli/genius_wizard.py`` and exposed as ``neugi wizard``.
    """


__all__ = ["SetupWizard", "WizardState", "WizardStep"]
