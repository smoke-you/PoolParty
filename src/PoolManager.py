

from abc import abstractmethod
from multiprocessing import Pool, Queue, Manager
from typing import Any, Callable


class PoolManager:

    def __init__(self, poolsz: int, func: Callable[[int, Queue],Any]):
        self.poolsz = poolsz
        self.pool = Pool(self.poolsz)
        self.queue = Manager().Queue(poolsz * 16 + 32)
        self.func = func
        self.next_proc_id = 0
        self.queue_cnt = 0
        self.active_cnt = 0
        self.complete_cnt = 0

    def start(self):
        self.queue_cnt += 1
        self.queue.put(self.status(), False)
        self.pool.apply_async(func=self.func, args=(self.next_proc_id, self.queue))
        self.next_proc_id += 1

    def status(self) -> dict:
        return {'op': 'pool', 'completed': self.complete_cnt, 'active': self.active_cnt, 'queued': self.queue_cnt}

