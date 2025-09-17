from datetime import datetime, date
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(title="Reminder Agent Mock Backend")


class TaskCreate(BaseModel):
	name: str
	description: Optional[str] = ""
	due_datetime: str
	status: Optional[str] = Field(default="Pending")


class Task(TaskCreate):
	id: int


_tasks: Dict[int, Task] = {}
_next_id: int = 1


def _parse_iso(dt_str: str) -> datetime:
	try:
		return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
	except Exception:
		raise HTTPException(status_code=400, detail="Invalid datetime format; use ISO 8601.")


@app.get("/tasks", response_model=List[Task])
def list_tasks() -> List[Task]:
	return list(_tasks.values())


@app.post("/tasks", response_model=Task)
def create_task(payload: TaskCreate) -> Task:
	global _next_id
	_ = _parse_iso(payload.due_datetime)
	task = Task(id=_next_id, **payload.dict())
	_tasks[_next_id] = task
	_next_id += 1
	return task


@app.put("/tasks/{task_id}", response_model=Task)
def update_task(task_id: int, payload: Dict[str, Any]) -> Task:
	if task_id not in _tasks:
		raise HTTPException(status_code=404, detail="Task not found")

	task = _tasks[task_id]
	if "due_datetime" in payload and payload["due_datetime"]:
		_ = _parse_iso(payload["due_datetime"])  # validate

	for k, v in payload.items():
		if v is not None and hasattr(task, k):
			setattr(task, k, v)

	_tasks[task_id] = task
	return task


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int) -> None:
	if task_id not in _tasks:
		raise HTTPException(status_code=404, detail="Task not found")
	del _tasks[task_id]
	return None


@app.get("/tasks/today", response_model=List[Task])
def tasks_today() -> List[Task]:
	today = date.today()
	result: List[Task] = []
	for t in _tasks.values():
		try:
			dt = _parse_iso(t.due_datetime)
			if dt.date() == today:
				result.append(t)
		except HTTPException:
			continue
	return result


