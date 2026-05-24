"""
Scope Validator for Autonomous Security Harness.
Validates that targets are within the authorized scope.
"""
import ipaddress
import logging
from typing import Any

logger = logging.getLogger(__name__)

class ScopeValidator:
    def __init__(self, scope: dict[str, Any]):
        """
        Initialize the scope validator.

        Args:
            scope: A dictionary containing scope definition.
                   Expected keys:
                   - allowed_targets: list of strings (IPs, hostnames, CIDR ranges)
                   - allow_private_ips: boolean (default False)
                   - allowed_ports: list of ints or range (default 1-65535)
        """
        self.allowed_targets: set[str] = set()
        self.allow_private_ips: bool = scope.get('allow_private_ips', False)
        self.allowed_ports: set[int] = set()

        # Process allowed_targets
        for target in scope.get('allowed_targets', []):
            self.allowed_targets.add(target.strip())

        # Process allowed_ports
        ports_config = scope.get('allowed_ports', [])
        if isinstance(ports_config, list):
            for port in ports_config:
                if isinstance(port, int) and 1 <= port <= 65535:
                    self.allowed_ports.add(port)
                elif isinstance(port, str) and '-' in port:
                    # Handle port ranges like "1-1000"
                    try:
                        start, end = map(int, port.split('-'))
                        for p in range(start, end+1):
                            if 1 <= p <= 65535:
                                self.allowed_ports.add(p)
                    except ValueError:
                        pass
        elif isinstance(ports_config, str) and '-' in ports_config:
            # Single range string
            try:
                start, end = map(int, ports_config.split('-'))
                for p in range(start, end+1):
                    if 1 <= p <= 65535:
                        self.allowed_ports.add(p)
            except ValueError:
                pass
        else:
            # Default to all ports if not specified or invalid
            self.allowed_ports = set(range(1, 65536))

    def validate_target(self, target: str, tool: str) -> bool:
        """
        Validate if a target is within the authorized scope.

        Args:
            target: The target to validate (IP address or hostname)
            tool: The tool that wants to use the target (for logging)

        Returns:
            True if target is allowed, False otherwise
        """
        # Check if target is in the allowed_targets list (exact match or CIDR).
        # Explicit scope entries are the authorization boundary. A private IP is
        # allowed when it is explicitly listed or covered by an allowed CIDR.
        if self._is_target_allowed(target):
            return True
        else:
            logger.warning(f"Scope validation failed: Target {target} not in allowed targets for tool {tool}")
            return False

    def _is_target_allowed(self, target: str) -> bool:
        """Check if target matches any of the allowed targets (exact, CIDR, or hostname)."""
        # Exact match
        if target in self.allowed_targets:
            return True

        # Check if target is an IP address and if any allowed target is a CIDR that contains it
        if self._is_ip_address(target):
            try:
                ip = ipaddress.ip_address(target)
                for allowed in self.allowed_targets:
                    # Check if allowed is a CIDR network
                    try:
                        network = ipaddress.ip_network(allowed, strict=False)
                        if ip in network:
                            return True
                    except ValueError:
                        # Not a valid network, skip
                        pass
            except ValueError:
                # Not an IP address, so we already did exact match above
                pass

        # If we haven't returned True by now, it's not allowed
        return False

    def _is_ip_address(self, target: str) -> bool:
        """Check if the target string is an IP address."""
        try:
            ipaddress.ip_address(target)
            return True
        except ValueError:
            return False

    def validate_port(self, port: int) -> bool:
        """Validate if a port is within the allowed ports."""
        return port in self.allowed_ports
