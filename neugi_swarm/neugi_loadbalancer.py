#!/usr/bin/env python3
"""
🤖 NEUGI LOAD BALANCER
=========================

Load balancing strategies:
- Round robin
- Least connections
- IP hash
- Weighted

Version: 1.0
Date: March 16, 2026
"""

import random
import hashlib
from typing import Dict, List, Any


class Backend:
    """Backend server"""

    def __init__(self, host: str, port: int, weight: int = 1):
        self.host = host
        self.port = port
        self.weight = weight
        self.connections = 0
        self.health = True

    def __str__(self):
        return f"{self.host}:{self.port}"


class LoadBalancer:
    """Load balancer"""

    STRATEGIES = ["round_robin", "least_connections", "ip_hash", "weighted", "random"]

    def __init__(self, strategy: str = "round_robin"):
        self.strategy = strategy
        self.backends: List[Backend] = []
        self.current_index = 0

    def add_backend(self, host: str, port: int, weight: int = 1):
        backend = Backend(host, port, weight)
        self.backends.append(backend)

    def remove_backend(self, host: str, port: int):
        self.backends = [b for b in self.backends if not (b.host == host and b.port == port)]

    def get_backend(self, client_ip: str = None) -> Backend:
        healthy = [b for b in self.backends if b.health]
        if not healthy:
            return None

        if self.strategy == "round_robin":
            backend = healthy[self.current_index % len(healthy)]
            self.current_index += 1
            return backend

        elif self.strategy == "least_connections":
            return min(healthy, key=lambda b: b.connections)

        elif self.strategy == "ip_hash" and client_ip:
            index = int(hashlib.md5(client_ip.encode()).hexdigest(), 16) % len(healthy)
            return healthy[index]

        elif self.strategy == "weighted":
            weights = [b.weight for b in healthy]
            return random.choices(healthy, weights=weights)[0]

        else:
            return random.choice(healthy)

    def release_backend(self, backend: Backend):
        if backend and backend.connections > 0:
            backend.connections -= 1

    def list_backends(self) -> List[Dict]:
        return [
            {
                "host": b.host,
                "port": b.port,
                "weight": b.weight,
                "connections": b.connections,
                "health": b.health,
            }
            for b in self.backends
        ]


lb = LoadBalancer()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Load Balancer")
    parser.add_argument("--add", nargs=2, metavar=("HOST", "PORT"), help="Add backend")
    parser.add_argument("--list", action="store_true", help="List backends")
    parser.add_argument("--strategy", type=str, help="Set strategy")
    args = parser.parse_args()

    if args.add:
        lb.add_backend(args.add[0], int(args.add[1]))
        print(f"Added: {args.add[0]}:{args.add[1]}")
    elif args.list:
        for b in lb.list_backends():
            print(
                f"{b['host']}:{b['port']} (weight: {b['weight']}, conn: {b['connections']}, healthy: {b['health']})"
            )
    elif args.strategy:
        lb.strategy = args.strategy
        print(f"Strategy: {args.strategy}")
    else:
        print("Usage: python -m neugi_loadbalancer [--add HOST PORT|--list|--strategy NAME]")


if __name__ == "__main__":
    main()
