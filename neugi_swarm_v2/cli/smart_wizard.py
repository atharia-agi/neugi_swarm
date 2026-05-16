"""Deprecated compatibility wrapper for the canonical setup wizard."""

from __future__ import annotations

from neugi_swarm_v2.cli.genius_wizard import GeniusWizard


class SmartWizard(GeniusWizard):
    """Backward-compatible alias for :class:`GeniusWizard`.

    NEUGI keeps one setup path now: ``neugi wizard`` -> ``GeniusWizard``.
    This class remains only so old imports keep working.
    """


__all__ = ["SmartWizard"]
