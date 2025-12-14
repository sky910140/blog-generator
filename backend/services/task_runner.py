import concurrent.futures
from typing import Callable, Dict, Optional


class TaskRunner:
    """
    Lightweight in-process task runner using ThreadPoolExecutor.
    """

    def __init__(self, max_workers: int = 3):
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self.tasks: Dict[str, concurrent.futures.Future] = {}

    def submit(self, task_id: str, fn: Callable, *args, **kwargs) -> concurrent.futures.Future:
        future = self.executor.submit(fn, *args, **kwargs)
        self.tasks[task_id] = future
        return future

    def get_future(self, task_id: str) -> Optional[concurrent.futures.Future]:
        return self.tasks.get(task_id)
