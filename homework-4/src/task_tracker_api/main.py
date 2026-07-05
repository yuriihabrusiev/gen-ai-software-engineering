import hmac
import os

from fastapi import FastAPI, Header, HTTPException, Response

from task_tracker_api.models import Task, TaskCreate
from task_tracker_api.store import (
    clear_all,
    complete_task,
    create_task,
    delete_task,
    get_task,
    list_tasks,
    stats,
)

app = FastAPI(
    title="Task Tracker API",
    version="0.1.0",
    description="A small in-memory REST API for tracking tasks.",
)

ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "dev-local-admin-key-000")


@app.post("/tasks", response_model=Task, status_code=201)
def post_task(payload: TaskCreate) -> Task:
    return create_task(payload)


@app.get("/tasks", response_model=list[Task])
def get_tasks(completed: bool | None = None, sort: str | None = None) -> list[Task]:
    return list_tasks(completed=completed, sort=sort)


@app.get("/tasks/stats")
def get_stats() -> dict:
    return stats()


@app.get("/tasks/{task_id}", response_model=Task)
def get_task_by_id(task_id: int) -> Task:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.patch("/tasks/{task_id}/complete", response_model=Task)
def patch_task_complete(task_id: int) -> Task:
    task = complete_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task_by_id(task_id: int) -> Response:
    if not delete_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return Response(status_code=204)


@app.delete("/admin/tasks", status_code=204)
def delete_all_tasks(x_admin_key: str = Header(...)) -> Response:
    if hmac.compare_digest(x_admin_key, ADMIN_API_KEY):
        clear_all()
        return Response(status_code=204)
    else:
        raise HTTPException(status_code=403, detail="Forbidden")
