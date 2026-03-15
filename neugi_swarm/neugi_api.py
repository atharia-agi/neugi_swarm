#!/usr/bin/env python3
"""
🤖 NEUGI REST API SERVER
=========================

FastAPI-based REST API for NEUGI:
- Agent management
- Memory access
- Skill execution
- Workflow triggers
- System metrics

Version: 1.0
Date: March 15, 2026
"""

import os
import sys
import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

# Try to import FastAPI
try:
    from fastapi import FastAPI, HTTPException, Request, Depends
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, StreamingResponse
    from pydantic import BaseModel

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    print("FastAPI not installed. Install with: pip install fastapi uvicorn")
    sys.exit(1)


NEUGI_DIR = os.path.expanduser("~/neugi")
app = FastAPI(
    title="NEUGI API", description="REST API for NEUGI Swarm Intelligence", version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== MODELS ==========


class ChatRequest(BaseModel):
    message: str
    agent: Optional[str] = None
    stream: bool = False


class MemoryRequest(BaseModel):
    query: Optional[str] = None
    fact: Optional[str] = None
    memory_type: str = "daily"


class SkillExecuteRequest(BaseModel):
    skill_name: str
    context: Optional[Dict] = None


class WorkflowRunRequest(BaseModel):
    workflow_id: str
    context: Optional[Dict] = None


class TaskScheduleRequest(BaseModel):
    name: str
    prompt: str
    schedule_type: str
    time: Optional[str] = None
    interval: Optional[int] = None


# ========== DEPENDENCIES ==========


def get_neugi_dir():
    """Get NEUGI directory"""
    return NEUGI_DIR


# ========== HEALTH & STATUS ==========


@app.get("/")
async def root():
    """Root endpoint"""
    return {"name": "NEUGI API", "version": "1.0.0", "status": "running"}


@app.get("/health")
async def health():
    """Health check"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat(), "neugi_dir": NEUGI_DIR}


@app.get("/status")
async def status():
    """Get system status"""
    import psutil

    return {
        "api": {"status": "running", "version": "1.0.0"},
        "system": {
            "cpu": psutil.cpu_percent(),
            "memory": psutil.virtual_memory().percent,
            "disk": psutil.disk_usage("/").percent,
        },
        "neugi_dir": NEUGI_DIR,
        "timestamp": datetime.now().isoformat(),
    }


# ========== MENU SYSTEM ==========

MENU_CATEGORIES = {
    "system": {"icon": "⚙️", "color": "#6366f1"},
    "ai": {"icon": "🧠", "color": "#8b5cf6"},
    "automation": {"icon": "🤖", "color": "#10b981"},
    "integrations": {"icon": "🔗", "color": "#f59e0b"},
    "developer": {"icon": "👨‍💻", "color": "#3b82f6"},
    "security": {"icon": "🔐", "color": "#ef4444"},
    "cloud": {"icon": "☁️", "color": "#06b6d4"},
    "operations": {"icon": "📊", "color": "#ec4899"},
}

MENU_ITEMS = [
    {"id": 1, "name": "Sovereign Heartbeat", "category": "system", "icon": "💓"},
    {"id": 2, "name": "Network Topology", "category": "system", "icon": "🌐"},
    {"id": 3, "name": "Skill Registry", "category": "system", "icon": "🛠️"},
    {"id": 4, "name": "Live Monitor", "category": "system", "icon": "📊"},
    {"id": 5, "name": "View Logs", "category": "system", "icon": "📄"},
    {"id": 6, "name": "Auto-Boot", "category": "system", "icon": "🔄"},
    {"id": 7, "name": "Setup/Install", "category": "system", "icon": "🎯"},
    {"id": 8, "name": "Repair System", "category": "system", "icon": "🔧"},
    {"id": 9, "name": "Diagnose System", "category": "system", "icon": "🧠"},
    {"id": 10, "name": "Chat with AI", "category": "ai", "icon": "💬"},
    {"id": 11, "name": "Manage Plugins", "category": "ai", "icon": "📦"},
    {"id": 12, "name": "Check Updates", "category": "system", "icon": "🔄"},
    {"id": 13, "name": "Security Settings", "category": "security", "icon": "🔐"},
    {"id": 14, "name": "Memory System", "category": "ai", "icon": "🧊"},
    {"id": 15, "name": "Soul/Personality", "category": "ai", "icon": "🎭"},
    {"id": 16, "name": "Skills V2", "category": "developer", "icon": "📚"},
    {"id": 17, "name": "Task Scheduler", "category": "automation", "icon": "⏰"},
    {"id": 18, "name": "MCP Server", "category": "integrations", "icon": "🌐"},
    {"id": 19, "name": "App Integrations", "category": "integrations", "icon": "📱"},
    {"id": 20, "name": "Workflow Automation", "category": "automation", "icon": "🔀"},
    {"id": 21, "name": "Run Tests", "category": "developer", "icon": "🧪"},
    {"id": 22, "name": "REST API Server", "category": "integrations", "icon": "🌍"},
    {"id": 23, "name": "Docker Management", "category": "system", "icon": "🐳"},
    {"id": 24, "name": "Advanced Monitoring", "category": "operations", "icon": "📈"},
    {"id": 25, "name": "Visual Workflow Builder", "category": "automation", "icon": "🎨"},
    {"id": 26, "name": "Automation Engine", "category": "automation", "icon": "🤖"},
    {"id": 27, "name": "Database Management", "category": "system", "icon": "🗄️"},
    {"id": 28, "name": "Command Palette", "category": "developer", "icon": "⌨️"},
    {"id": 29, "name": "File Manager", "category": "developer", "icon": "📁"},
    {"id": 30, "name": "Code Interpreter", "category": "developer", "icon": "💻"},
    {"id": 31, "name": "Plugin Marketplace", "category": "integrations", "icon": "🛒"},
    {"id": 32, "name": "Encryption Tools", "category": "security", "icon": "🔒"},
    {"id": 33, "name": "SSH Manager", "category": "system", "icon": "🔐"},
    {"id": 34, "name": "Cache Layer", "category": "operations", "icon": "🧠"},
    {"id": 35, "name": "Log Aggregator", "category": "operations", "icon": "📝"},
    {"id": 36, "name": "Backup System", "category": "system", "icon": "💾"},
    {"id": 37, "name": "Kubernetes", "category": "cloud", "icon": "☸️"},
    {"id": 38, "name": "WebSocket Server", "category": "integrations", "icon": "🔌"},
    {"id": 39, "name": "GraphQL API", "category": "integrations", "icon": "📊"},
    {"id": 40, "name": "Prometheus Metrics", "category": "operations", "icon": "📈"},
    {"id": 41, "name": "API Gateway", "category": "integrations", "icon": "🚪"},
    {"id": 42, "name": "Service Discovery", "category": "cloud", "icon": "🔍"},
    {"id": 43, "name": "Secrets Manager", "category": "security", "icon": "🔑"},
    {"id": 44, "name": "Multi-Cluster", "category": "cloud", "icon": "🌍"},
    {"id": 45, "name": "Circuit Breaker", "category": "cloud", "icon": "⚡"},
    {"id": 46, "name": "Load Balancer", "category": "cloud", "icon": "⚖️"},
    {"id": 47, "name": "Service Mesh", "category": "cloud", "icon": "🕸️"},
    {"id": 48, "name": "CDN Manager", "category": "cloud", "icon": "🌐"},
    {"id": 49, "name": "Event Bus", "category": "operations", "icon": "📨"},
    {"id": 50, "name": "Agents SDK", "category": "developer", "icon": "🤖"},
    {"id": 51, "name": "CLI Framework", "category": "developer", "icon": "⌘"},
    # v23.x NEW FEATURES
    {"id": 52, "name": "ML Pipeline", "category": "ai", "icon": "🧠"},
    {"id": 53, "name": "Data Pipeline", "category": "operations", "icon": "🔗"},
    {"id": 54, "name": "Notification System", "category": "operations", "icon": "🔔"},
    {"id": 55, "name": "Webhook Manager", "category": "integrations", "icon": "🪝"},
    {"id": 56, "name": "Rate Limiter", "category": "operations", "icon": "🚦"},
    {"id": 57, "name": "Config Manager", "category": "system", "icon": "⚙️"},
    {"id": 58, "name": "Template Engine", "category": "developer", "icon": "📝"},
    {"id": 59, "name": "Report Generator", "category": "operations", "icon": "📑"},
    {"id": 60, "name": "Analytics Dashboard", "category": "operations", "icon": "📉"},
    # v24.x NEW FEATURES
    {"id": 61, "name": "API Versioning", "category": "developer", "icon": "📌"},
    {"id": 62, "name": "API Docs UI", "category": "developer", "icon": "📖"},
    {"id": 63, "name": "Request Validator", "category": "developer", "icon": "✅"},
    {"id": 64, "name": "Response Cacher", "category": "operations", "icon": "💾"},
    {"id": 65, "name": "Metrics Exporter", "category": "operations", "icon": "📊"},
    {"id": 66, "name": "Health Checks", "category": "operations", "icon": "💚"},
    {"id": 67, "name": "Circuit Dashboard", "category": "cloud", "icon": "⚡"},
    {"id": 68, "name": "Service Registry", "category": "cloud", "icon": "📚"},
    {"id": 69, "name": "Config Sync", "category": "cloud", "icon": "🔄"},
    {"id": 70, "name": "Deployment Manager", "category": "cloud", "icon": "🚀"},
]


@app.get("/api/menu")
async def get_menu():
    """Get all menu items"""
    return {"items": MENU_ITEMS, "categories": MENU_CATEGORIES, "total": len(MENU_ITEMS)}


@app.get("/api/menu/{menu_id}")
async def get_menu_item(menu_id: int):
    """Get specific menu item"""
    for item in MENU_ITEMS:
        if item["id"] == menu_id:
            return item
    return {"error": "Not found"}


@app.get("/api/categories")
async def get_categories():
    """Get menu categories"""
    return MENU_CATEGORIES


# ========== AGENTS ==========


@app.get("/api/agents")
async def list_agents():
    """List available agents"""
    agents = [
        {"id": "aurora", "name": "Aurora", "role": "Data Extraction"},
        {"id": "cipher", "name": "Cipher", "role": "Code & Logic"},
        {"id": "nova", "name": "Nova", "role": "UI & Design"},
        {"id": "pulse", "name": "Pulse", "role": "Data Analysis"},
        {"id": "quark", "name": "Quark", "role": "Strategic Planning"},
        {"id": "shield", "name": "Shield", "role": "Security"},
        {"id": "spark", "name": "Spark", "role": "Network Ops"},
        {"id": "ink", "name": "Ink", "role": "Content"},
        {"id": "nexus", "name": "Nexus", "role": "Orchestration"},
    ]
    return {"agents": agents}


@app.post("/api/agents/delegate")
async def delegate_to_agent(request: ChatRequest):
    """Delegate task to agent"""
    return {
        "status": "delegated",
        "agent": request.agent or "nexus",
        "task": request.message,
        "timestamp": datetime.now().isoformat(),
    }


# ========== CHAT ==========


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Chat with NEUGI"""
    try:
        # Try to import and use NEUGI components
        from neugi_wizard import AIAgent

        agent = AIAgent()

        if request.stream:
            # Return streaming response
            async def generate():
                async for chunk in agent.chat_stream(request.message):
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"

            return StreamingResponse(generate(), media_type="text/event-stream")
        else:
            response = agent.ask(request.message)
            return {"response": response, "timestamp": datetime.now().isoformat()}

    except Exception as e:
        # Fallback response
        return {
            "response": f"I received your message: {request.message}",
            "note": "Using fallback mode",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


# ========== MEMORY ==========


@app.get("/api/memory")
async def get_memory(memory_type: str = "core"):
    """Get memory contents"""
    try:
        from neugi_memory_v2 import TwoTierMemory

        memory = TwoTierMemory()

        if memory_type == "core":
            return {"content": memory.read_core(), "type": "core"}
        else:
            return {"content": memory.read_daily(), "type": "daily"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/memory")
async def add_memory(request: MemoryRequest):
    """Add to memory"""
    try:
        from neugi_memory_v2 import TwoTierMemory

        memory = TwoTierMemory()

        if request.fact:
            if request.memory_type == "core":
                memory.add_core_fact("Notes", request.fact)
            else:
                memory.write_daily(request.fact)

            return {"status": "saved", "fact": request.fact}

        return {"error": "No fact provided"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/memory/recall")
async def recall_memory(request: MemoryRequest):
    """Search memory"""
    try:
        from neugi_memory_v2 import TwoTierMemory

        memory = TwoTierMemory()
        results = memory.recall(request.query or "")

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== SKILLS ==========


@app.get("/api/skills")
async def list_skills():
    """List all skills"""
    try:
        from neugi_skills_v2 import SkillManagerV2

        manager = SkillManagerV2()
        skills = manager.list_skills()

        return {"skills": [s.to_dict() for s in skills]}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/skills/execute")
async def execute_skill(request: SkillExecuteRequest):
    """Execute a skill"""
    try:
        from neugi_skills_v2 import SkillManagerV2

        manager = SkillManagerV2()
        result = manager.execute_skill(request.skill_name, request.context)

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== WORKFLOWS ==========


@app.get("/api/workflows")
async def list_workflows():
    """List workflows"""
    try:
        from neugi_workflows import WorkflowEngine

        engine = WorkflowEngine()
        workflows = engine.list_workflows()

        return {"workflows": workflows}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/workflows/run")
async def run_workflow(request: WorkflowRunRequest):
    """Run a workflow"""
    try:
        from neugi_workflows import WorkflowEngine

        engine = WorkflowEngine()
        run = engine.run_workflow(request.workflow_id, request.context)

        return {"run_id": run.id, "status": run.status, "results": run.step_results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== SCHEDULER ==========


@app.get("/api/scheduler/tasks")
async def list_tasks():
    """List scheduled tasks"""
    try:
        from neugi_scheduler import NEUGIScheduler

        scheduler = NEUGIScheduler()
        tasks = scheduler.list_tasks()

        return {"tasks": tasks}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scheduler/tasks")
async def add_task(request: TaskScheduleRequest):
    """Add scheduled task"""
    try:
        from neugi_scheduler import NEUGIScheduler

        scheduler = NEUGIScheduler()

        result = scheduler.add_task(
            request.name, request.prompt, request.schedule_type, request.time, request.interval
        )

        if result:
            return {"status": "created", "name": request.name}
        return {"error": "Task already exists"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/scheduler/tasks/{task_name}")
async def delete_task(task_name: str):
    """Delete scheduled task"""
    try:
        from neugi_scheduler import NEUGIScheduler

        scheduler = NEUGIScheduler()

        if scheduler.remove_task(task_name):
            return {"status": "deleted"}
        return {"error": "Task not found"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== FILESYSTEM (Cowork) ==========


@app.get("/api/fs/{path:path}")
async def read_file(path: str):
    """Read file"""
    try:
        from neugi_cowork import CoworkSession

        session = CoworkSession(os.path.join(NEUGI_DIR, "workspace"))
        result = session.read(path)

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/fs/{path:path}")
async def write_file(path: str, content: str):
    """Write file"""
    try:
        from neugi_cowork import CoworkSession

        session = CoworkSession(os.path.join(NEUGI_DIR, "workspace"))
        result = session.write(path, content)

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/fs/")
async def list_files(path: str = "."):
    """List files"""
    try:
        from neugi_cowork import CoworkSession

        session = CoworkSession(os.path.join(NEUGI_DIR, "workspace"))
        result = session.ls(path)

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== SYSTEM ==========


@app.get("/api/metrics")
async def get_metrics():
    """Get system metrics"""
    try:
        import psutil

        return {
            "cpu": {"percent": psutil.cpu_percent(), "count": psutil.cpu_count()},
            "memory": {
                "total": psutil.virtual_memory().total,
                "available": psutil.virtual_memory().available,
                "percent": psutil.virtual_memory().percent,
            },
            "disk": {
                "total": psutil.disk_usage("/").total,
                "used": psutil.disk_usage("/").used,
                "percent": psutil.disk_usage("/").percent,
            },
            "network": {
                "bytes_sent": psutil.net_io_counters().bytes_sent,
                "bytes_recv": psutil.net_io_counters().bytes_recv,
            },
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/processes")
async def list_processes(limit: int = 10):
    """List processes"""
    try:
        import psutil

        processes = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                processes.append(
                    {
                        "pid": p.info["pid"],
                        "name": p.info["name"],
                        "cpu": p.info["cpu_percent"],
                        "memory": p.info["memory_percent"],
                    }
                )
            except:
                pass

        processes.sort(key=lambda x: x["cpu"], reverse=True)

        return {"processes": processes[:limit]}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== SOUL ==========


@app.get("/api/soul")
async def get_soul():
    """Get soul/personality"""
    try:
        from neugi_soul import SoulSystem

        soul = SoulSystem()
        info = soul.get_info()

        return info

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/soul/preset")
async def load_preset(preset: str):
    """Load soul preset"""
    try:
        from neugi_soul import SoulSystem

        soul = SoulSystem()

        if soul.load_preset(preset):
            return {"status": "loaded", "preset": preset}

        return {"error": "Invalid preset"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== MAIN ==========


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI REST API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host")
    parser.add_argument("--port", type=int, default=19890, help="Port")
    parser.add_argument("--reload", action="store_true", help="Auto-reload")

    args = parser.parse_args()

    try:
        import uvicorn

        uvicorn.run("neugi_api:app", host=args.host, port=args.port, reload=args.reload)
    except ImportError:
        print("uvicorn not installed. Install with: pip install uvicorn")
        sys.exit(1)


if __name__ == "__main__":
    main()
