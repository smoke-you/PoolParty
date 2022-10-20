from abc import abstractmethod
import asyncio
from multiprocessing import Pool, Queue, Manager
import queue
from typing import Any, Callable

from Producer import ServerOperations


class PoolManager:

    def __init__(self, poolsz: int, func: Callable[[int, Queue],Any]):
        self.poolsz = poolsz
        self.pool = Pool(self.poolsz)
        self.outq = Manager().Queue()
        self.inq = Manager().Queue()
        self.func = func
        self.next_proc_id = 0
        self.queued_cnt = 0
        self.active_cnt = 0
        self.complete_cnt = 0
        self.active_procs = set[int]()
        asyncio.create_task(self.monitor_inq())

    async def monitor_inq(self):
        while True:
            try:
                msg = self.inq.get(False)
                if self.active_procs.__contains__(msg.get('id', None)):
                    self.inq.put(msg)
                await asyncio.sleep(0.5)
            except queue.Empty:
                await asyncio.sleep(0.1)

    def queue_task(self):
        self.queued_cnt += 1
        self.outq.put(self.status(), False)
        self.pool.apply_async(
            func=self.func, 
            args=(self.next_proc_id, self.outq, self.inq)
            )
        self.next_proc_id += 1

    def cancel_task(self, msg: dict):
        if self.active_procs.__contains__(msg.get('id', None)):
            self.inq.put(msg)

    def task_started(self, id: int):
        self.active_procs.add(id)
        self.active_cnt += 1
        self.queued_cnt -= 1
        self.outq.put(self.status(), False)

    def task_finished(self, id: int):
        try:
            self.active_procs.remove(id)
        except KeyError:
            pass
        self.active_cnt -= 1
        self.complete_cnt += 1
        self.outq.put(self.status(), False)

    def status(self) -> dict:
        return {
            'op': ServerOperations.POOL.value, 
            'completed': self.complete_cnt, 
            'active': self.active_cnt, 
            'queued': self.queued_cnt
            }

