"""
📡 NEUGI SWARM - NETWORKING LAYER
================================

Handles peer-to-peer communication between Neugi nodes.
Allows for 'Swarm Expansion' across multiple machines.
"""

import os
import json
import requests
import time
from typing import List, Dict

NEUGI_DIR = os.path.expanduser("~/neugi")
NODES_FILE = os.path.join(NEUGI_DIR, "nodes.json")

class NodeManager:
    """Manages the lifecycle and discovery of peer nodes."""
    
    def __init__(self):
        self.nodes = self._load_nodes()
        self.local_node = {"id": "local", "ip": "127.0.0.1", "port": 19888}

    def _load_nodes(self) -> List[Dict]:
        if os.path.exists(NODES_FILE):
            try:
                with open(NODES_FILE, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []

    def _save_nodes(self):
        os.makedirs(NEUGI_DIR, exist_ok=True)
        with open(NODES_FILE, 'w') as f:
            json.dump(self.nodes, f, indent=4)

    def register_node(self, node_id: str, ip: str, port: int):
        """Registers a new peer node in the swarm."""
        for node in self.nodes:
            if node['id'] == node_id:
                node.update({"ip": ip, "port": port, "last_seen": time.time()})
                self._save_nodes()
                return
        
        self.nodes.append({
            "id": node_id,
            "ip": ip,
            "port": port,
            "last_seen": time.time(),
            "status": "online"
        })
        self._save_nodes()

    def get_online_nodes(self) -> List[Dict]:
        """Returns nodes that have been seen recently."""
        # Simple health check based on time for now
        now = time.time()
        return [n for n in self.nodes if now - n.get('last_seen', 0) < 300]

    def send_to_node(self, node_id: str, task: str, payload: Dict):
        """Sends a task to a specific node."""
        for node in self.nodes:
            if node['id'] == node_id:
                try:
                    url = f"http://{node['ip']}:{node['port']}/api/swarm/delegate"
                    resp = requests.post(url, json={"task": task, "payload": payload}, timeout=10)
                    return resp.json()
                except Exception as e:
                    return {"error": str(e)}
        return {"error": f"Node {node_id} not found or offline"}

    def broadcast_task(self, task: str, payload: Dict):
        """Sends a task to all online peer nodes."""
        results = []
        for node in self.get_online_nodes():
            try:
                url = f"http://{node['ip']}:{node['port']}/api/swarm/delegate"
                resp = requests.post(url, json={"task": task, "payload": payload}, timeout=5)
                results.append({"node": node['id'], "response": resp.json()})
            except Exception as e:
                results.append({"node": node['id'], "error": str(e)})
        return results

# Singleton instance
swarm_net = NodeManager()
