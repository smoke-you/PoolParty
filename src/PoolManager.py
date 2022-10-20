from abc import abstractmethod
import asyncio
from multiprocessing import Pool, Queue, Manager
import queue
from typing import Any, Callable

from Producer import ClientOperations, ServerOperations, Producer

class PoolManager:

    def __init__(self, poolsz: int, func: Callable[[int, Queue, Queue],Any]):
        self.poolsz = poolsz
        self.pool = Pool(processes=self.poolsz)
        self.outq = Manager().Queue()
        self.inq = Manager().Queue()
        self.func = func
        self.next_proc_id = 1
        self.queued_cnt = 0
        self.active_cnt = 0
        self.complete_cnt = 0
        self.active_procs = set[int]()
        asyncio.create_task(self.monitor_inq())

    async def monitor_inq(self):
        while True:
            try:
                msg = self.inq.get(False)
                msg_id = msg.get('id', None)
                if msg_id in self.active_procs:
                    self.inq.put(msg)
                await asyncio.sleep(0.5)
            except BaseException:
                await asyncio.sleep(0.1)

    def queue_task(self):
        self.queued_cnt += 1
        self.outq.put(self.status(), False)
        self.pool.apply_async(
            func=self.func, 
            args=(self.next_proc_id, self.outq, self.inq)
            )

    def cancel_task(self, msg: dict):
        msg_id = msg.get('id', None)
        msg_op = msg.get('op', None)
        if msg_id in self.active_procs:
            self.inq.put(msg)
        elif msg_op == ClientOperations.CANCEL.value:
            if msg_id in self.active_procs:
                pass
            elif msg_id is not None:
                # report that the id has already been cancelled
                self.outq.put(Producer.cancel(msg_id))
            elif self.queued_cnt > 0:
                # if there are queued tasks, we can't get rid of them :-( so... destroy!!!
                self.pool.close()
                self.queued_cnt = 0
                # report queued tasks as cancelled
                for p in self.active_procs:
                    self.outq.put(Producer.cancel(p))
                self.active_procs.clear()
                # rebuild!!!
                self.pool = Pool(self.poolsz)
                self.outq.put(PoolManager.status())
            else:
                # if there are no queued tasks, just cancel the running ones
                for p in self.active_procs:
                    self.inq.put({'op': ClientOperations.CANCEL.value, 'id': p})


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


