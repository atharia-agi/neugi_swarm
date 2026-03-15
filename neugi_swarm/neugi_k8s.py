#!/usr/bin/env python3
"""
🤖 NEUGI KUBERNETES CONNECTOR
================================

Kubernetes management:
- Cluster connection
- Pod management
- Deployment control
- Service management

Version: 1.0
Date: March 16, 2026
"""

import os
import json
import subprocess
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

NEUGI_DIR = os.path.expanduser("~/neugi")
K8S_CONFIG = os.path.join(NEUGI_DIR, "kubernetes", "config.json")
os.makedirs(os.path.dirname(K8S_CONFIG), exist_ok=True)


class KubernetesConnector:
    """Kubernetes connector"""

    def __init__(self, context: str = None):
        self.context = context
        self._check_kubectl()

    def _check_kubectl(self):
        """Check if kubectl is available"""
        try:
            subprocess.run(["kubectl", "version", "--client"], capture_output=True, check=True)
            self.kubectl_available = True
        except:
            self.kubectl_available = False

    def _run_kubectl(self, args: List[str]) -> Dict:
        """Run kubectl command"""
        if not self.kubectl_available:
            return {"success": False, "error": "kubectl not installed"}

        cmd = ["kubectl"]
        if self.context:
            cmd.extend(["--context", self.context])
        cmd.extend(args)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_clusters(self) -> List[Dict]:
        """Get available clusters"""
        result = self._run_kubectl(["config", "get-contexts", "-o", "json"])
        if not result.get("success"):
            return []

        try:
            data = json.loads(result["output"])
            return data.get("contexts", [])
        except:
            return []

    def get_pods(self, namespace: str = "default") -> List[Dict]:
        """Get pods in namespace"""
        result = self._run_kubectl(["get", "pods", "-n", namespace, "-o", "json"])
        if not result.get("success"):
            return []

        try:
            data = json.loads(result["output"])
            return data.get("items", [])
        except:
            return []

    def get_services(self, namespace: str = "default") -> List[Dict]:
        """Get services in namespace"""
        result = self._run_kubectl(["get", "services", "-n", namespace, "-o", "json"])
        if not result.get("success"):
            return []

        try:
            data = json.loads(result["output"])
            return data.get("items", [])
        except:
            return []

    def get_deployments(self, namespace: str = "default") -> List[Dict]:
        """Get deployments in namespace"""
        result = self._run_kubectl(["get", "deployments", "-n", namespace, "-o", "json"])
        if not result.get("success"):
            return []

        try:
            data = json.loads(result["output"])
            return data.get("items", [])
        except:
            return []

    def get_nodes(self) -> List[Dict]:
        """Get cluster nodes"""
        result = self._run_kubectl(["get", "nodes", "-o", "json"])
        if not result.get("success"):
            return []

        try:
            data = json.loads(result["output"])
            return data.get("items", [])
        except:
            return []

    def get_namespaces(self) -> List[str]:
        """Get all namespaces"""
        result = self._run_kubectl(["get", "namespaces", "-o", "json"])
        if not result.get("success"):
            return []

        try:
            data = json.loads(result["output"])
            return [item["metadata"]["name"] for item in data.get("items", [])]
        except:
            return []

    def describe_pod(self, name: str, namespace: str = "default") -> str:
        """Get pod details"""
        result = self._run_kubectl(["describe", "pod", name, "-n", namespace])
        return result.get("output", "")

    def get_pod_logs(self, name: str, namespace: str = "default", container: str = None) -> str:
        """Get pod logs"""
        args = ["logs", name, "-n", namespace]
        if container:
            args.extend(["-c", container])

        result = self._run_kubectl(args)
        return result.get("output", "")

    def scale_deployment(self, name: str, replicas: int, namespace: str = "default") -> Dict:
        """Scale deployment"""
        result = self._run_kubectl(
            ["scale", "deployment", name, f"--replicas={replicas}", "-n", namespace]
        )
        return result

    def delete_pod(self, name: str, namespace: str = "default") -> Dict:
        """Delete pod"""
        result = self._run_kubectl(["delete", "pod", name, "-n", namespace])
        return result

    def apply_manifest(self, manifest: str) -> Dict:
        """Apply YAML manifest"""
        result = self._run_kubectl(["apply", "-f", "-"])
        return result

    def get_dashboard_url(self) -> str:
        """Get Kubernetes dashboard URL"""
        result = self._run_kubectl(["cluster-info", "kubernetes-dashboard"])
        if result.get("success"):
            for line in result["output"].split("\n"):
                if "kubernetes-dashboard" in line:
                    return line.split(" ")[-1].rstrip("/")
        return None

    def get_resource_usage(self) -> Dict:
        """Get cluster resource usage"""
        usage = {"nodes": 0, "pods": 0, "services": 0, "deployments": 0}

        try:
            nodes = self.get_nodes()
            usage["nodes"] = len(nodes)

            for ns in self.get_namespaces():
                usage["pods"] += len(self.get_pods(ns))
                usage["services"] += len(self.get_services(ns))
                usage["deployments"] += len(self.get_deployments(ns))
        except:
            pass

        return usage


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Kubernetes Connector")
    parser.add_argument("--context", type=str, help="Kubernetes context")
    parser.add_argument("--clusters", action="store_true", help="List clusters")
    parser.add_argument("--pods", type=str, help="Get pods in namespace")
    parser.add_argument("--services", type=str, help="Get services in namespace")
    parser.add_argument("--deployments", type=str, help="Get deployments in namespace")
    parser.add_argument("--nodes", action="store_true", help="Get nodes")
    parser.add_argument("--namespaces", action="store_true", help="Get namespaces")
    parser.add_argument("--logs", nargs=2, metavar=("POD", "NAMESPACE"), help="Get pod logs")
    parser.add_argument(
        "--scale", nargs=3, metavar=("DEPLOYMENT", "REPLICAS", "NS"), help="Scale deployment"
    )
    parser.add_argument("--usage", action="store_true", help="Resource usage")

    args = parser.parse_args()

    k8s = KubernetesConnector(args.context)

    if args.clusters:
        clusters = k8s.get_clusters()
        print(f"\n🔗 Clusters:\n")
        for c in clusters:
            print(f"  {c['context-name']} -> {c['cluster']}")

    elif args.pods:
        pods = k8s.get_pods(args.pods)
        print(f"\n📦 Pods in {args.pods}:\n")
        for p in pods:
            status = p["status"]["phase"]
            print(f"  {p['metadata']['name']} - {status}")

    elif args.services:
        svcs = k8s.get_services(args.services)
        print(f"\n🔌 Services in {args.services}:\n")
        for s in svcs:
            print(f"  {s['metadata']['name']} -> {s['spec']['type']}")

    elif args.deployments:
        deploys = k8s.get_deployments(args.deployments)
        print(f"\n🚀 Deployments in {args.deployments}:\n")
        for d in deploys:
            ready = d["status"].get("readyReplicas", 0)
            desired = d["spec"]["replicas"]
            print(f"  {d['metadata']['name']} - {ready}/{desired}")

    elif args.nodes:
        nodes = k8s.get_nodes()
        print(f"\n🖥️  Nodes:\n")
        for n in nodes:
            print(f"  {n['metadata']['name']}")

    elif args.namespaces:
        nss = k8s.get_namespaces()
        print(f"\n📁 Namespaces:\n")
        for ns in nss:
            print(f"  {ns}")

    elif args.logs:
        pod, ns = args.logs
        logs = k8s.get_pod_logs(pod, ns)
        print(logs[:2000])

    elif args.scale:
        deploy, replicas, ns = args.scale
        result = k8s.scale_deployment(deploy, int(replicas), ns)
        print(result.get("output") or result.get("error"))

    elif args.usage:
        usage = k8s.get_resource_usage()
        print(f"\n📊 Cluster Usage:\n")
        print(f"  Nodes: {usage['nodes']}")
        print(f"  Pods: {usage['pods']}")
        print(f"  Services: {usage['services']}")
        print(f"  Deployments: {usage['deployments']}")

    else:
        print("NEUGI Kubernetes Connector")
        print(
            "Usage: python -m neugi_k8s [--clusters|--pods NS|--services NS|--deployments NS|--nodes|--namespaces|--logs POD NS|--scale DEPLOY REPLICAS NS|--usage]"
        )


if __name__ == "__main__":
    main()
