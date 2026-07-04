from task_tracker_api.models import Priority, Task, TaskCreate

tasks: dict[int, Task] = {}
_next_id = 1


def create_task(data: TaskCreate) -> Task:
    global _next_id

    task = Task(
        id=_next_id,
        title=data.title,
        priority=data.priority,
        due_date=data.due_date,
        completed=False,
    )
    tasks[task.id] = task
    _next_id += 1
    return task


_PRIORITY_ORDER = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}


def list_tasks(completed: bool | None = None, sort: str | None = None) -> list[Task]:
    results = list(tasks.values())

    if completed is not None:
        results = [task for task in results if task.completed == completed]

    if sort == "priority":
        results = sorted(results, key=lambda t: _PRIORITY_ORDER[t.priority])

    return results


def get_task(task_id: int) -> Task | None:
    return tasks.get(task_id)


def complete_task(task_id: int) -> Task | None:
    task = tasks.get(task_id)
    if task is None:
        return None
    task.completed = True
    return task


def delete_task(task_id: int) -> bool:
    if task_id not in tasks:
        return False
    del tasks[task_id]
    return True


def reset_store() -> None:
    global _next_id
    tasks.clear()
    _next_id = 1


def clear_all() -> None:
    reset_store()


def stats() -> dict:
    total = len(tasks)
    completed_count = sum(1 for task in tasks.values() if task.completed)
    percent_complete = round(completed_count / total * 100, 1) if total else 0
    return {
        "total": total,
        "completed": completed_count,
        "percent_complete": percent_complete,
    }
