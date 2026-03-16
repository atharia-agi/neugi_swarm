#!/usr/bin/env python3
"""
🤖 NEUGI SERVICE DISCOVERY
============================

Service discovery system:
- Register services
- Health checks
- DNS management
- Load balancing

Version: 1.0
Date: March 16, 2026
"""

import os
import json
import uuid
import time
import socket
from typing import Dict, List, Optional

NEUGI_DIR = os.path.expanduser("~/neugi")
REGISTRY_FILE = os.path.join(NEUGI_DIR, "service_discovery.json")


class ServiceInstance:
    """Service instance"""

    def __init__(self, service_name: str, host: str, port: int, metadata: Dict = None):
        self.id = str(uuid.uuid4())[:8]
        self.service_name = service_name
        self.host = host
        self.port = port
        self.metadata = metadata or {}
        self.status = "healthy"
        self.created_at = time.time()
        self.last_health_check = time.time()
        self.health_check_interval = 30

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "service_name": self.service_name,
            "host": self.host,
            "port": self.port,
            "metadata": self.metadata,
            "status": self.status,
            "created_at": self.created_at,
            "last_health_check": self.last_health_check,
        }


class ServiceRegistry:
    """Service registry"""

    def __init__(self):
        self.services: Dict[str, List[ServiceInstance]] = {}
        self._load()

    def _load(self):
        """Load registry"""
        if os.path.exists(REGISTRY_FILE):
            try:
                with open(REGISTRY_FILE) as f:
                    data = json.load(f)
                    for service_name, instances in data.items():
                        self.services[service_name] = [
                            ServiceInstance(
                                s["service_name"], s["host"], s["port"], s.get("metadata")
                            )
                            for s in instances
                        ]
            except:
                pass

    def _save(self):
        """Save registry"""
        data = {name: [s.to_dict() for s in instances] for name, instances in self.services.items()}
        with open(REGISTRY_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def register(
        self, service_name: str, host: str, port: int, metadata: Dict = None
    ) -> ServiceInstance:
        """Register service"""
        instance = ServiceInstance(service_name, host, port, metadata)

        if service_name not in self.services:
            self.services[service_name] = []

        self.services[service_name].append(instance)
        self._save()

        return instance

    def deregister(self, service_name: str, instance_id: str):
        """Deregister service"""
        if service_name in self.services:
            self.services[service_name] = [
                s for s in self.services[service_name] if s.id != instance_id
            ]
            self._save()

    def discover(self, service_name: str) -> List[ServiceInstance]:
        """Discover services"""
        return self.services.get(service_name, [])

    def get_healthy(self, service_name: str) -> List[ServiceInstance]:
        """Get healthy instances"""
        instances = self.discover(service_name)
        now = time.time()

        healthy = []
        for instance in instances:
            if now - instance.last_health_check < instance.health_check_interval:
                healthy.append(instance)

        return healthy

    def get_all(self) -> Dict[str, List[Dict]]:
        """Get all services"""
        return {name: [s.to_dict() for s in instances] for name, instances in self.services.items()}

    def health_check(self, instance_id: str) -> bool:
        """Perform health check"""
        for service_name, instances in self.services.items():
            for instance in instances:
                if instance.id == instance_id:
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(5)
                        result = sock.connect_ex((instance.host, instance.port))
                        sock.close()

                        if result == 0:
                            instance.status = "healthy"
                        else:
                            instance.status = "unhealthy"

                        instance.last_health_check = time.time()
                        self._save()
                        return result == 0
                    except:
                        instance.status = "unhealthy"
                        return False

        return False

    def round_robin(self, service_name: str) -> Optional[ServiceInstance]:
        """Get next instance (round robin)"""
        healthy = self.get_healthy(service_name)
        if not healthy:
            return None

        index = int(time.time()) % len(healthy)
        return healthy[index]


registry = ServiceRegistry()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Service Discovery")
    parser.add_argument(
        "--register", nargs=3, metavar=("SERVICE", "HOST", "PORT"), help="Register service"
    )
    parser.add_argument("--discover", type=str, help="Discover services")
    parser.add_argument("--list", action="store_true", help="List all services")
    parser.add_argument("--health", type=str, help="Health check instance")

    args = parser.parse_args()

    if args.register:
        service, host, port = args.register
        instance = registry.register(service, host, int(port))
        print(f"Registered: {service} at {host}:{port} (ID: {instance.id})")

    elif args.discover:
        instances = registry.discover(args.discover)
        print(f"\n📡 {args.discover}:\n")
        for i in instances:
            status = "✅" if i.status == "healthy" else "❌"
            print(f"  {status} {i.host}:{i.port}")

    elif args.list:
        all_services = registry.get_all()
        print(f"\n📡 Services ({len(all_services)}):\n")
        for name, instances in all_services.items():
            healthy = len([i for i in instances if i["status"] == "healthy"])
            print(f"  {name}: {healthy}/{len(instances)} healthy")

    elif args.health:
        result = registry.health_check(args.health)
        print(f"Health check: {'✅ Healthy' if result else '❌ Unhealthy'}")

    else:
        print("NEUGI Service Discovery")
        print(
            "Usage: python -m neugi_discovery [--register SERVICE HOST PORT|--discover SERVICE|--list|--health ID]"
        )


if __name__ == "__main__":
    main()
