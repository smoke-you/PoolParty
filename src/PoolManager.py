from abc import abstractmethod
import asyncio
from concurrent.futures import Future, ProcessPoolExecutor
from multiprocessing import Queue, Manager
from typing import Any, Callable

from Producer import ClientOperations, ServerOperations, Producer

class PoolManager(object):

    def __init__(self, poolsz: int, work: Callable[[int, Queue, Queue], Any]):
        super().__init__()
        self.poolsz = poolsz
        self.pool = ProcessPoolExecutor(self.poolsz)
        self.outq = Manager().Queue()
        self.inq = Manager().Queue()
        self.work = work
        self.next_proc_id = 1
        self.complete_cnt = 0
        self.active_procs = ActiveProcessList()
        asyncio.create_task(self.monitor_inq())

    def __del__(self):
        self.pool.shutdown(wait=False, cancel_futures=True)
        super().__del__()

    async def monitor_inq(self):
        while True:
            try:
                msg = self.inq.get(False)
                if self.active_procs.contains_id(msg.get('id', None)):
                    self.inq.put(msg)
                await asyncio.sleep(0.5)
            except BaseException:
                await asyncio.sleep(0.1)

    def queue_task(self):
        try:
            self.active_procs.append((
                self.next_proc_id, 
                self.pool.submit(self.work, self.next_proc_id, self.outq, self.inq)
                ))
            self.next_proc_id += 1
            self.outq.put(self.status(), False)        
        except Exception as ex:
            print(ex)

    def cancel_task(self, msg: dict):
        msg_id = msg.get('id', None)
        msg_op = msg.get('op', None)
        if self.active_procs.contains_id(msg_id):
            self.inq.put(msg)
        elif msg_op == ClientOperations.CANCEL.value:
            if msg_id is not None:
                # report that the id has already been cancelled
                self.outq.put(Producer.cancel(msg_id))
            else:
                # cancel all queued tasks, remove them from active_procs
                cancelled = []
                for p in self.active_procs:
                    try:
                        if p[1].cancel():
                            cancelled.append(p)
                    except:
                        pass
                for p in cancelled:
                    self.active_procs.remove(p)
                # send cancel messages to all of the remaining tasks via inq
                for p in self.active_procs:
                    self.inq.put({'op': ClientOperations.CANCEL.value, 'id': p[0]})
                # report the resulting status change to the clients
                self.outq.put(PoolManager.status())

    def task_started(self, id: int):
        self.outq.put(self.status(), False)

    def task_finished(self, op: str, id: int):
        self.active_procs.remove_id(id)
        if op == ServerOperations.FINISH.value:
            self.complete_cnt += 1
        self.outq.put(self.status(), False)

    def status(self) -> dict:
        pcnt, acnt = self.active_procs.counts()
        return {
            'op': ServerOperations.POOL.value, 
            'completed': self.complete_cnt, 
            'active': acnt, 
            'queued': pcnt
            }


class ActiveProcessList(list[tuple[int, Future]]):
    def __init__(self):
        super().__init__()

    def remove_id(self, id: int):
        target = None
        for p in self:
            if p[0] == id:
                target = p
                break
        if target:
            super().remove(target)

    def contains_id(self, id: int):
        if id is None:
            return False
        for p in self:
            if p[0] == id:
                return True
        return False
    
    def gen_pending(self) -> tuple[int, Future]:
        for p in self:
            if not any((p[1].running, p[1].cancelled, p[1].done)):
                yield p

    def pending(self) -> list[int, Future]:
        return [self.gen_pending()]

    def counts(self) -> tuple[int, int]: # pending, active
        pcnt = 0
        acnt = 0
        for p in self:
            r = p[1].running
            c = p[1].cancelled
            d = p[1].done
            if r:
                acnt += 1
            elif not(r and c and d):
                pcnt += 1
        return pcnt, acnt
        
        
