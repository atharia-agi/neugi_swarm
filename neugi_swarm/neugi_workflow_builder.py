#!/usr/bin/env python3
"""
🤖 NEUGI VISUAL WORKFLOW BUILDER
==================================

Web-based visual workflow builder:
- Drag and drop nodes
- Connect workflow steps
- Execute workflows visually
- Save and load workflows

Version: 1.0
Date: March 16, 2026
"""

import os
import json
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime

NEUGI_DIR = os.path.expanduser("~/neugi")
WORKFLOWS_DIR = os.path.join(NEUGI_DIR, "workflows")
os.makedirs(WORKFLOWS_DIR, exist_ok=True)


class WorkflowNode:
    """Base workflow node"""

    def __init__(self, id: str, node_type: str, label: str, config: Dict = None):
        self.id = id
        self.type = node_type
        self.label = label
        self.config = config or {}
        self.position = {"x": 0, "y": 0}
        self.connections = []

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type,
            "label": self.label,
            "config": self.config,
            "position": self.position,
            "connections": self.connections,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "WorkflowNode":
        node = cls(data["id"], data["type"], data["label"], data.get("config", {}))
        node.position = data.get("position", {"x": 0, "y": 0})
        node.connections = data.get("connections", [])
        return node


class Workflow:
    """Workflow definition"""

    NODE_TYPES = {
        "trigger": {"label": "Trigger", "color": "#ff6b6b", "icon": "⚡"},
        "action": {"label": "Action", "color": "#4ecdc4", "icon": "⚙️"},
        "condition": {"label": "Condition", "color": "#ffe66d", "icon": "🔀"},
        "http": {"label": "HTTP Request", "color": "#95e1d3", "icon": "🌐"},
        "transform": {"label": "Transform", "color": "#dfe6e9", "icon": "🔄"},
        "delay": {"label": "Delay", "color": "#a29bfe", "icon": "⏱️"},
        "log": {"label": "Log", "color": "#fd79a8", "icon": "📝"},
        "notification": {"label": "Notification", "color": "#00cec9", "icon": "🔔"},
    }

    def __init__(self, id: str = None, name: str = "Untitled Workflow", description: str = ""):
        self.id = id or str(uuid.uuid4())[:8]
        self.name = name
        self.description = description
        self.nodes: List[WorkflowNode] = []
        self.edges: List[Dict] = []
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        self.enabled = True
        self.schedule = None

    def add_node(self, node_type: str, label: str, position: Dict = None) -> WorkflowNode:
        """Add a node to the workflow"""
        node_id = str(uuid.uuid4())[:8]
        node = WorkflowNode(node_id, node_type, label)
        if position:
            node.position = position
        self.nodes.append(node)
        self.updated_at = datetime.now().isoformat()
        return node

    def remove_node(self, node_id: str):
        """Remove a node"""
        self.nodes = [n for n in self.nodes if n.id != node_id]
        self.edges = [e for e in self.edges if e["source"] != node_id and e["target"] != node_id]
        self.updated_at = datetime.now().isoformat()

    def connect(self, source_id: str, target_id: str):
        """Connect two nodes"""
        self.edges.append(
            {"id": f"{source_id}-{target_id}", "source": source_id, "target": target_id}
        )
        for node in self.nodes:
            if node.id == source_id and target_id not in node.connections:
                node.connections.append(target_id)
        self.updated_at = datetime.now().isoformat()

    def disconnect(self, source_id: str, target_id: str):
        """Disconnect two nodes"""
        self.edges = [
            e for e in self.edges if not (e["source"] == source_id and e["target"] == target_id)
        ]
        for node in self.nodes:
            if node.id == source_id and target_id in node.connections:
                node.connections.remove(target_id)
        self.updated_at = datetime.now().isoformat()

    def get_node(self, node_id: str) -> Optional[WorkflowNode]:
        """Get node by ID"""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def execute(self, context: Dict = None) -> Dict:
        """Execute the workflow"""
        if not context:
            context = {}

        results = []
        errors = []

        executed = set()

        def execute_node(node_id: str) -> Any:
            if node_id in executed:
                return None
            executed.add(node_id)

            node = self.get_node(node_id)
            if not node:
                return None

            try:
                result = self._execute_node(node, context)
                results.append(
                    {
                        "node_id": node_id,
                        "type": node.type,
                        "result": result,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

                for target_id in node.connections:
                    execute_node(target_id)

                return result
            except Exception as e:
                errors.append({"node_id": node_id, "error": str(e)})
                return None

        triggers = [n for n in self.nodes if n.type == "trigger"]
        for trigger in triggers:
            execute_node(trigger.id)

        return {
            "workflow_id": self.id,
            "workflow_name": self.name,
            "success": len(errors) == 0,
            "results": results,
            "errors": errors,
            "executed_nodes": len(executed),
        }

    def _execute_node(self, node: WorkflowNode, context: Dict) -> Any:
        """Execute a single node"""

        if node.type == "trigger":
            return {"triggered": True, "event": node.config.get("event", "manual")}

        elif node.type == "action":
            action = node.config.get("action", "noop")
            if action == "log":
                print(f"[LOG] {node.config.get('message', '')}")
                return {"logged": True}
            elif action == "shell":
                import subprocess

                result = subprocess.run(
                    node.config.get("command", ""), shell=True, capture_output=True
                )
                return {"output": result.stdout.decode(), "returncode": result.returncode}
            return {"action": action}

        elif node.type == "condition":
            condition = node.config.get("condition", "true")
            if condition == "true":
                return {"branch": "true"}
            return {"branch": "false"}

        elif node.type == "http":
            import requests

            method = node.config.get("method", "GET")
            url = node.config.get("url", "")
            try:
                response = requests.request(method, url, timeout=10)
                return {"status": response.status_code, "body": response.text[:500]}
            except Exception as e:
                return {"error": str(e)}

        elif node.type == "delay":
            import time

            seconds = node.config.get("seconds", 1)
            time.sleep(seconds)
            return {"delayed": seconds}

        elif node.type == "transform":
            transform = node.config.get("transform", "identity")
            data = context.get("data", {})
            if transform == "uppercase":
                return {"result": str(data).upper()}
            elif transform == "lowercase":
                return {"result": str(data).lower()}
            return {"result": data}

        elif node.type == "log":
            print(f"[WORKFLOW] {node.config.get('message', '')}")
            return {"logged": True}

        elif node.type == "notification":
            return {"notified": True, "message": node.config.get("message", "")}

        return {"noop": True}

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": self.edges,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "enabled": self.enabled,
            "schedule": self.schedule,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Workflow":
        workflow = cls(data["id"], data["name"], data["description"])
        workflow.nodes = [WorkflowNode.from_dict(n) for n in data.get("nodes", [])]
        workflow.edges = data.get("edges", [])
        workflow.created_at = data.get("created_at", datetime.now().isoformat())
        workflow.updated_at = data.get("updated_at", datetime.now().isoformat())
        workflow.enabled = data.get("enabled", True)
        workflow.schedule = data.get("schedule")
        return workflow

    def save(self):
        """Save workflow to file"""
        path = os.path.join(WORKFLOWS_DIR, f"{self.id}.json")
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        return path

    @classmethod
    def load(cls, workflow_id: str) -> Optional["Workflow"]:
        """Load workflow from file"""
        path = os.path.join(WORKFLOWS_DIR, f"{workflow_id}.json")
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return cls.from_dict(json.load(f))

    @classmethod
    def list_all(cls) -> List[Dict]:
        """List all workflows"""
        workflows = []
        for f in os.listdir(WORKFLOWS_DIR):
            if f.endswith(".json"):
                path = os.path.join(WORKFLOWS_DIR, f)
                with open(path) as fp:
                    data = json.load(fp)
                    workflows.append(
                        {
                            "id": data["id"],
                            "name": data["name"],
                            "description": data["description"],
                            "node_count": len(data.get("nodes", [])),
                            "enabled": data.get("enabled", True),
                            "updated_at": data["updated_at"],
                        }
                    )
        return sorted(workflows, key=lambda x: x["updated_at"], reverse=True)

    @classmethod
    def delete(cls, workflow_id: str) -> bool:
        """Delete workflow"""
        path = os.path.join(WORKFLOWS_DIR, f"{workflow_id}.json")
        if os.path.exists(path):
            os.remove(path)
            return True
        return False


class WorkflowBuilder:
    """Visual workflow builder web interface"""

    HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NEUGI Workflow Builder</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jsPlumb/2.15.6/jsplumb.min.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #eee; height: 100vh; display: flex; flex-direction: column; }
        
        header { background: #16213e; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #0f3460; }
        header h1 { font-size: 1.3rem; display: flex; align-items: center; gap: 10px; }
        .btn { padding: 8px 16px; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; transition: all 0.2s; }
        .btn-primary { background: #4ecdc4; color: #1a1a2e; }
        .btn-primary:hover { background: #45b7af; }
        .btn-secondary { background: #e94560; color: white; }
        .btn-secondary:hover { background: #d63d56; }
        
        .toolbar { background: #16213e; padding: 10px 20px; display: flex; gap: 10px; align-items: center; border-bottom: 1px solid #0f3460; }
        .toolbar-section { display: flex; gap: 5px; align-items: center; }
        .toolbar-divider { width: 1px; height: 30px; background: #0f3460; margin: 0 10px; }
        
        .node-type { padding: 8px 12px; background: #0f3460; border-radius: 6px; cursor: grab; display: flex; align-items: center; gap: 6px; font-size: 0.85rem; }
        .node-type:hover { background: #1a4a7a; }
        
        .main { flex: 1; display: flex; overflow: hidden; }
        
        .sidebar { width: 250px; background: #16213e; padding: 15px; border-right: 1px solid #0f3460; overflow-y: auto; }
        .sidebar h3 { font-size: 0.9rem; color: #888; margin-bottom: 15px; text-transform: uppercase; letter-spacing: 1px; }
        
        .workflow-list { display: flex; flex-direction: column; gap: 8px; }
        .workflow-item { padding: 12px; background: #0f3460; border-radius: 8px; cursor: pointer; transition: all 0.2s; }
        .workflow-item:hover { background: #1a4a7a; }
        .workflow-item.active { background: #4ecdc4; color: #1a1a2e; }
        .workflow-item h4 { font-size: 0.95rem; margin-bottom: 4px; }
        .workflow-item p { font-size: 0.8rem; color: #888; }
        
        #canvas { flex: 1; background: #1a1a2e; position: relative; overflow: auto; }
        #canvas-canvas { min-width: 2000px; min-height: 2000px; position: relative; }
        
        .node { position: absolute; width: 160px; padding: 12px; border-radius: 8px; cursor: move; user-select: none; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
        .node.trigger { background: #ff6b6b; }
        .node.action { background: #4ecdc4; color: #1a1a2e; }
        .node.condition { background: #ffe66d; color: #1a1a2e; }
        .node.http { background: #95e1d3; color: #1a1a2e; }
        .node.transform { background: #dfe6e9; color: #1a1a2e; }
        .node.delay { background: #a29bfe; }
        .node.log { background: #fd79a8; }
        .node.notification { background: #00cec9; }
        
        .node-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-weight: 600; font-size: 0.9rem; }
        .node-icon { font-size: 1.1rem; }
        .node-body { font-size: 0.8rem; opacity: 0.9; }
        
        .node-connector { width: 12px; height: 12px; background: white; border-radius: 50%; position: absolute; cursor: crosshair; }
        .node-connector.left { left: -6px; top: 50%; transform: translateY(-50%); }
        .node-connector.right { right: -6px; top: 50%; transform: translateY(-50%); }
        
        .properties { width: 280px; background: #16213e; padding: 15px; border-left: 1px solid #0f3460; overflow-y: auto; }
        .properties h3 { font-size: 0.9rem; color: #888; margin-bottom: 15px; text-transform: uppercase; }
        .property-group { margin-bottom: 15px; }
        .property-group label { display: block; font-size: 0.85rem; color: #aaa; margin-bottom: 5px; }
        .property-group input, .property-group select, .property-group textarea { width: 100%; padding: 8px; background: #0f3460; border: 1px solid #1a4a7a; border-radius: 4px; color: white; font-size: 0.9rem; }
        .property-group textarea { min-height: 80px; resize: vertical; }
        
        .jtk-connector { stroke: #4ecdc4; stroke-width: 2; }
        .jtk-connector:hover { stroke: #ffe66d; }
        
        .empty-state { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); text-align: center; color: #666; }
        .empty-state h2 { font-size: 1.5rem; margin-bottom: 10px; }
    </style>
</head>
<body>
    <header>
        <h1>🎯 NEUGI Workflow Builder</h1>
        <div>
            <button class="btn btn-secondary" onclick="deleteWorkflow()">🗑️ Delete</button>
            <button class="btn btn-primary" onclick="saveWorkflow()">💾 Save</button>
            <button class="btn btn-primary" onclick="executeWorkflow()">▶️ Run</button>
        </div>
    </header>
    
    <div class="toolbar">
        <div class="toolbar-section">
            <span style="color: #888; font-size: 0.85rem;">Add Node:</span>
        </div>
        <div class="toolbar-section">
            <div class="node-type" data-type="trigger" onclick="addNode('trigger')">⚡ Trigger</div>
            <div class="node-type" data-type="action" onclick="addNode('action')">⚙️ Action</div>
            <div class="node-type" data-type="condition" onclick="addNode('condition')">🔀 Condition</div>
            <div class="node-type" data-type="http" onclick="addNode('http')">🌐 HTTP</div>
            <div class="node-type" data-type="transform" onclick="addNode('transform')">🔄 Transform</div>
            <div class="node-type" data-type="delay" onclick="addNode('delay')">⏱️ Delay</div>
            <div class="node-type" data-type="log" onclick="addNode('log')">📝 Log</div>
            <div class="node-type" data-type="notification" onclick="addNode('notification')">🔔 Notify</div>
        </div>
        <div class="toolbar-divider"></div>
        <div class="toolbar-section">
            <button class="btn btn-secondary" onclick="clearCanvas()">🧹 Clear</button>
        </div>
    </div>
    
    <div class="main">
        <div class="sidebar">
            <h3>📁 Workflows</h3>
            <button class="btn btn-primary" style="width: 100%; margin-bottom: 15px;" onclick="newWorkflow()">+ New Workflow</button>
            <div class="workflow-list" id="workflowList"></div>
        </div>
        
        <div id="canvas">
            <div id="canvas-canvas">
                <div class="empty-state" id="emptyState">
                    <h2>No Workflow Selected</h2>
                    <p>Select a workflow or create a new one</p>
                </div>
            </div>
        </div>
        
        <div class="properties" id="properties">
            <h3>⚙️ Properties</h3>
            <div id="propertiesContent">
                <p style="color: #666; font-size: 0.9rem;">Select a node to edit its properties</p>
            </div>
        </div>
    </div>
    
    <script>
        let currentWorkflow = null;
        let jsPlumbInstance = null;
        let selectedNode = null;
        
        const NODE_TYPES = {
            trigger: {label: 'Trigger', color: '#ff6b6b', icon: '⚡'},
            action: {label: 'Action', color: '#4ecdc4', icon: '⚙️'},
            condition: {label: 'Condition', color: '#ffe66d', icon: '🔀'},
            http: {label: 'HTTP Request', color: '#95e1d3', icon: '🌐'},
            transform: {label: 'Transform', color: '#dfe6e9', icon: '🔄'},
            delay: {label: 'Delay', color: '#a29bfe', icon: '⏱️'},
            log: {label: 'Log', color: '#fd79a8', icon: '📝'},
            notification: {label: 'Notification', color: '#00cec9', icon: '🔔'},
        };
        
        document.addEventListener('DOMContentLoaded', function() {
            jsPlumbInstance = jsPlumb.getInstance({
                Container: 'canvas-canvas',
                Connector: ['Bezier', {curviness: 50}],
                ConnectionOverlays: [['Arrow', {location: 1, visible: true, width: 10, length: 10}]],
                PaintStyle: {stroke: '#4ecdc4', strokeWidth: 2},
                HoverPaintStyle: {stroke: '#ffe66d'}
            });
            
            loadWorkflowList();
        });
        
        async function loadWorkflowList() {
            const response = await fetch('/api/workflows');
            const workflows = await response.json();
            
            const list = document.getElementById('workflowList');
            list.innerHTML = '';
            
            workflows.forEach(w => {
                const item = document.createElement('div');
                item.className = 'workflow-item' + (currentWorkflow && currentWorkflow.id === w.id ? ' active' : '');
                item.onclick = () => loadWorkflow(w.id);
                item.innerHTML = `
                    <h4>${w.name}</h4>
                    <p>${w.node_count} nodes • ${w.enabled ? 'Enabled' : 'Disabled'}</p>
                `;
                list.appendChild(item);
            });
        }
        
        function newWorkflow() {
            currentWorkflow = {
                id: 'wf_' + Date.now(),
                name: 'New Workflow',
                description: '',
                nodes: [],
                edges: []
            };
            renderCanvas();
            loadWorkflowList();
        }
        
        async function loadWorkflow(id) {
            const response = await fetch('/api/workflows/' + id);
            currentWorkflow = await response.json();
            renderCanvas();
            loadWorkflowList();
        }
        
        function renderCanvas() {
            const canvas = document.getElementById('canvas-canvas');
            canvas.innerHTML = '';
            
            if (!currentWorkflow || currentWorkflow.nodes.length === 0) {
                canvas.innerHTML = `
                    <div class="empty-state" id="emptyState">
                        <h2>${currentWorkflow ? 'Empty Workflow' : 'No Workflow Selected'}</h2>
                        <p>${currentWorkflow ? 'Drag nodes from toolbar or click to add' : 'Select a workflow or create a new one'}</p>
                    </div>
                `;
                return;
            }
            
            currentWorkflow.nodes.forEach(node => {
                const el = createNodeElement(node);
                canvas.appendChild(el);
                jsPlumbInstance.makeSource(el, {anchor: 'Right', connectorOverlays: [['Arrow', {location: 1}]]});
                jsPlumbInstance.makeTarget(el, {anchor: 'Left'});
            });
            
            currentWorkflow.edges.forEach(edge => {
                const source = document.getElementById('node-' + edge.source);
                const target = document.getElementById('node-' + edge.target);
                if (source && target) {
                    jsPlumbInstance.connect({source: source, target: target});
                }
            });
            
            jsPlumbInstance.bind('connection', function(info) {
                const sourceId = info.source.id.replace('node-', '');
                const targetId = info.target.id.replace('node-', '');
                currentWorkflow.edges.push({id: sourceId + '-' + targetId, source: sourceId, target: targetId});
            });
        }
        
        function createNodeElement(node) {
            const type = NODE_TYPES[node.type] || NODE_TYPES.action;
            const el = document.createElement('div');
            el.id = 'node-' + node.id;
            el.className = 'node ' + node.type;
            el.style.left = (node.position?.x || 100) + 'px';
            el.style.top = (node.position?.y || 100) + 'px';
            el.innerHTML = `
                <div class="node-connector left"></div>
                <div class="node-header">
                    <span class="node-icon">${type.icon}</span>
                    <span>${node.label}</span>
                </div>
                <div class="node-body">${node.config?.description || type.label}</div>
                <div class="node-connector right"></div>
            `;
            el.onclick = () => selectNode(node);
            return el;
        }
        
        function addNode(type) {
            if (!currentWorkflow) { newWorkflow(); }
            
            const id = 'node_' + Date.now();
            const nodeType = NODE_TYPES[type];
            const node = {
                id: id,
                type: type,
                label: nodeType.label,
                config: {},
                position: {x: 200 + Math.random() * 100, y: 200 + Math.random() * 100}
            };
            
            currentWorkflow.nodes.push(node);
            renderCanvas();
            selectNode(node);
        }
        
        function selectNode(node) {
            selectedNode = node;
            const props = document.getElementById('propertiesContent');
            props.innerHTML = `
                <div class="property-group">
                    <label>Label</label>
                    <input type="text" value="${node.label}" onchange="updateNodeProp('label', this.value)">
                </div>
                <div class="property-group">
                    <label>Description</label>
                    <input type="text" value="${node.config?.description || ''}" onchange="updateNodeProp('description', this.value)">
                </div>
                ${getNodeConfigFields(node)}
            `;
        }
        
        function getNodeConfigFields(node) {
            let fields = '';
            if (node.type === 'action') {
                fields = `
                    <div class="property-group">
                        <label>Action</label>
                        <select onchange="updateNodeConfig('action', this.value)">
                            <option value="log" ${node.config?.action === 'log' ? 'selected' : ''}>Log</option>
                            <option value="shell" ${node.config?.action === 'shell' ? 'selected' : ''}>Shell Command</option>
                        </select>
                    </div>
                    <div class="property-group">
                        <label>Message / Command</label>
                        <textarea onchange="updateNodeConfig('message', this.value)">${node.config?.message || ''}</textarea>
                    </div>
                `;
            } else if (node.type === 'http') {
                fields = `
                    <div class="property-group">
                        <label>Method</label>
                        <select onchange="updateNodeConfig('method', this.value)">
                            <option value="GET" ${node.config?.method === 'GET' ? 'selected' : ''}>GET</option>
                            <option value="POST" ${node.config?.method === 'POST' ? 'selected' : ''}>POST</option>
                            <option value="PUT" ${node.config?.method === 'PUT' ? 'selected' : ''}>PUT</option>
                            <option value="DELETE" ${node.config?.method === 'DELETE' ? 'selected' : ''}>DELETE</option>
                        </select>
                    </div>
                    <div class="property-group">
                        <label>URL</label>
                        <input type="text" value="${node.config?.url || ''}" onchange="updateNodeConfig('url', this.value)">
                    </div>
                `;
            } else if (node.type === 'delay') {
                fields = `
                    <div class="property-group">
                        <label>Seconds</label>
                        <input type="number" value="${node.config?.seconds || 1}" onchange="updateNodeConfig('seconds', parseInt(this.value))">
                    </div>
                `;
            } else if (node.type === 'log' || node.type === 'notification') {
                fields = `
                    <div class="property-group">
                        <label>Message</label>
                        <textarea onchange="updateNodeConfig('message', this.value)">${node.config?.message || ''}</textarea>
                    </div>
                `;
            }
            return fields;
        }
        
        function updateNodeProp(prop, value) {
            if (!selectedNode) return;
            selectedNode.label = value;
            renderCanvas();
        }
        
        function updateNodeConfig(key, value) {
            if (!selectedNode) return;
            if (!selectedNode.config) selectedNode.config = {};
            selectedNode.config[key] = value;
        }
        
        function clearCanvas() {
            if (!currentWorkflow) return;
            currentWorkflow.nodes = [];
            currentWorkflow.edges = [];
            renderCanvas();
        }
        
        async function saveWorkflow() {
            if (!currentWorkflow) return;
            
            const response = await fetch('/api/workflows', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(currentWorkflow)
            });
            
            if (response.ok) {
                alert('Workflow saved!');
                loadWorkflowList();
            }
        }
        
        async function deleteWorkflow() {
            if (!currentWorkflow) return;
            if (!confirm('Delete this workflow?')) return;
            
            await fetch('/api/workflows/' + currentWorkflow.id, {method: 'DELETE'});
            currentWorkflow = null;
            renderCanvas();
            loadWorkflowList();
        }
        
        async function executeWorkflow() {
            if (!currentWorkflow) return;
            
            const response = await fetch('/api/workflows/' + currentWorkflow.id + '/execute', {
                method: 'POST'
            });
            const result = await response.json();
            
            let msg = 'Workflow executed!\\n';
            msg += 'Nodes executed: ' + result.executed_nodes + '\\n';
            if (result.errors.length > 0) {
                msg += 'Errors: ' + result.errors.length;
            } else {
                msg += 'Status: Success';
            }
            alert(msg);
        }
    </script>
</body>
</html>"""

    @staticmethod
    def get_html() -> str:
        return WorkflowBuilder.HTML


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Visual Workflow Builder")
    parser.add_argument("--port", type=int, default=19900, help="Port")
    parser.add_argument("--host", default="0.0.0.0", help="Host")

    args = parser.parse_args()

    try:
        from fastapi import FastAPI
        import uvicorn
    except ImportError:
        print("Install dependencies: pip install fastapi uvicorn")
        return

    app = FastAPI(title="NEUGI Workflow Builder")

    @app.get("/")
    async def index():
        from fastapi.responses import HTMLResponse

        return HTMLResponse(WorkflowBuilder.get_html())

    @app.get("/api/workflows")
    async def list_workflows():
        return Workflow.list_all()

    @app.get("/api/workflows/{workflow_id}")
    async def get_workflow(workflow_id: str):
        workflow = Workflow.load(workflow_id)
        if not workflow:
            return {"error": "Not found"}, 404
        return workflow.to_dict()

    @app.post("/api/workflows")
    async def create_workflow(data: dict):
        workflow = Workflow.from_dict(data)
        workflow.save()
        return {"id": workflow.id}

    @app.delete("/api/workflows/{workflow_id}")
    async def delete_workflow(workflow_id: str):
        Workflow.delete(workflow_id)
        return {"deleted": True}

    @app.post("/api/workflows/{workflow_id}/execute")
    async def execute_workflow(workflow_id: str):
        workflow = Workflow.load(workflow_id)
        if not workflow:
            return {"error": "Not found"}, 404
        return workflow.execute()

    print("🎯 NEUGI Workflow Builder")
    print(f"   URL: http://localhost:{args.port}")
    print(f"   API: http://localhost:{args.port}/api")

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
