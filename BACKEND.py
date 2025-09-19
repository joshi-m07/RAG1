from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import requests

app = FastAPI(title="Reminder Agent Backend")

# -----------------------------
# MODELS
# -----------------------------
class TaskCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    due_datetime: str
    status: Optional[str] = Field(default="Pending")

class Task(TaskCreate):
    id: int

class MCPRequest(BaseModel):
    agent: str   # "scheduler" | "rag"
    action: str  # "add_task", "ask", ...
    payload: Optional[dict] = {}

class MCPResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None

# -----------------------------
# STORAGE (In-memory for tasks)
# -----------------------------
_tasks: Dict[int, Task] = {}
_next_id: int = 1

def _parse_iso(dt_str: str) -> datetime:
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid datetime format; use ISO 8601.")

# -----------------------------
# DIRECT ENDPOINTS (scheduler)
# -----------------------------
@app.post("/add_task", response_model=Task)
def add_task(payload: TaskCreate):
    global _next_id
    _ = _parse_iso(payload.due_datetime)
    task = Task(id=_next_id, **payload.dict())
    _tasks[_next_id] = task
    _next_id += 1
    return task

@app.get("/get_tasks", response_model=List[Task])
def get_tasks():
    return list(_tasks.values())

@app.get("/get_tasks/today", response_model=List[Task])
def get_tasks_today():
    today = date.today()
    return [t for t in _tasks.values() if _parse_iso(t.due_datetime).date() == today]

@app.put("/update_task/{task_id}", response_model=Task)
def update_task(task_id: int, payload: Dict[str, Any]):
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    task = _tasks[task_id]
    if "due_datetime" in payload:
        _ = _parse_iso(payload["due_datetime"])
    for k, v in payload.items():
        if hasattr(task, k) and v is not None:
            setattr(task, k, v)
    _tasks[task_id] = task
    return task

@app.delete("/delete_task/{task_id}", status_code=204)
def delete_task(task_id: int):
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    del _tasks[task_id]
    return None

# -----------------------------
# RAG Forwarder
# -----------------------------
RAG_API_BASE = "http://localhost:9000"

def forward_to_rag(action: str, payload: dict):
    if action in ["ask", "insert", "update", "delete"]:
        resp = requests.post(f"{RAG_API_BASE}/{action}", json=payload)
    elif action == "receive":
        resp = requests.get(f"{RAG_API_BASE}/receive")
    else:
        return {"error": f"Unknown RAG action {action}"}
    return resp.json()

# -----------------------------
# UNIFIED MCP ENDPOINT
# -----------------------------
@app.post("/mcp", response_model=MCPResponse)
def mcp_endpoint(req: MCPRequest):
    try:
        if req.agent == "rag":
            rag_result = forward_to_rag(req.action, req.payload or {})
            return MCPResponse(success=True, data=rag_result)

        elif req.agent == "scheduler":
            if req.action == "add_task":
                task = add_task(TaskCreate(**req.payload))
                return MCPResponse(success=True, data=task.dict())

            elif req.action == "get_tasks":
                tasks = get_tasks()
                return MCPResponse(success=True, data=[t.dict() for t in tasks])

            elif req.action == "get_tasks_today":
                tasks = get_tasks_today()
                return MCPResponse(success=True, data=[t.dict() for t in tasks])

            elif req.action == "update_task":
                task_id = req.payload.get("id")
                if not task_id:
                    return MCPResponse(success=False, error="Missing id for update_task")
                task = update_task(task_id, req.payload)
                return MCPResponse(success=True, data=task.dict())

            elif req.action == "delete_task":
                task_id = req.payload.get("id")
                if not task_id:
                    return MCPResponse(success=False, error="Missing id for delete_task")
                delete_task(task_id)
                return MCPResponse(success=True, data={"deleted_id": task_id})

            else:
                return MCPResponse(success=False, error=f"Unknown scheduler action {req.action}")

        else:
            return MCPResponse(success=False, error=f"Unknown agent {req.agent}")

    except Exception as e:
        return MCPResponse(success=False, error=str(e))
