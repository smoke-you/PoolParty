import asyncio
from concurrent.futures import Future, ProcessPoolExecutor
from enum import Enum
from multiprocessing import Queue, Manager
from typing import Any, Callable, NamedTuple
from xmlrpc.client import Server

from Producer import ClientOperations, ServerOperations, Producer

class PoolManager(object):

    def __init__(self, poolsz: int, work: Callable[[int, Queue, Queue], Any]):
        super().__init__()
        self.poolsz = poolsz
        self.pool = ProcessPoolExecutor(self.poolsz)
        self.outq = Manager().Queue()
        self.inq = Manager().Queue()
        self.work = work
        self.next_work_id = 1
        self.complete_cnt = 0
        self.worklist = WorkList()
        asyncio.create_task(self.monitor_inq())

    async def monitor_inq(self):
        while True:
            try:
                msg = self.inq.get(False)
                if self.worklist.contains_id(msg.get('id', None)):
                    self.inq.put(msg)
                await asyncio.sleep(0.5)
            except:
                await asyncio.sleep(0.1)

    def queue_task(self):
        try:
            self.worklist.append_new(
                id=self.next_work_id, 
                f=self.pool.submit(self.work, self.next_work_id, self.outq, self.inq)
                )
            self.next_work_id += 1
            self.outq.put(self.status(), False)        
        except Exception as ex:
            print(ex)

    def cancel_task(self, msg: dict):
        msg_id = msg.get('id', None)
        msg_op = msg.get('op', None)
        if self.worklist.contains_id(msg_id):
            self.inq.put(msg)
        elif msg_op == ClientOperations.CANCEL.value:
            if msg_id is not None:
                # report that the id has already been cancelled
                self.outq.put(Producer.cancel(msg_id))
            else:
                # attempt to cancel any cancellable tasks, i.e. remove them from the pool
                self.worklist.cancel_all()
                # send cancel messages to all of the remaining tasks via inq
                for p in self.worklist:
                    self.inq.put({'op': ClientOperations.CANCEL.value, 'id': p.id})
                # report the resulting status change to the clients
                self.outq.put(PoolManager.status())

    def task_started(self, id: int):
        workitem = self.worklist.get_id(id)
        if workitem:
            workitem.state = WorkState.RUNNING
        self.outq.put(self.status(), False)

    def task_finished(self, op: str, id: int):
        self.worklist.remove_id(id)
        workitem = self.worklist.get_id(id)
        if workitem:
            if op == ServerOperations.FINISH.value:
                self.complete_cnt += 1
                workitem.state = WorkState.FINISHED
            elif op in (ServerOperations.ERROR.value, ServerOperations.CANCEL.value):
                workitem.state = WorkState.FINISHED
        self.outq.put(self.status(), False)

    def status(self) -> dict:
        qcnt, rcnt = self.worklist.counts()
        return {
            'op': ServerOperations.POOL.value, 
            'completed': self.complete_cnt, 
            'active': rcnt, 
            'queued': qcnt
            }


class WorkState(Enum):
    QUEUED = 0
    RUNNING = 1
    FINISHED = 2


class WorkItem:
    def __init__(self, id: int, f: Future):
        self.id = id
        self.state = WorkState.QUEUED
        self.future = f


class WorkList(list[WorkItem]):

    def __init__(self):
        super().__init__()

    def append_new(self, id: int, f: Future):
        super().append(WorkItem(id, f))

    def remove_id(self, id: int):
        target = None
        for p in self:
            if p.id == id:
                target = p
                break
        if target:
            super().remove(target)

    def contains_id(self, id: int):
        if id is None:
            return False
        for p in self:
            if p.id == id:
                return True
        return False

    def get_id(self, id: int):
        if id is not None:
            for p in self:
                if p.id == id:
                    return p
        return None

    def cancel_all(self):
        cancelled = list[WorkItem]()
        for p in self:
            try:
                if p.future.cancel():
                    cancelled.append(p)
            except:
                pass
        for p in cancelled:
            self.remove(p)
    
    def counts(self) -> tuple[int, int]: # queued, running
        pcnt = 0
        acnt = 0
        for p in self:
            if p.state == WorkState.QUEUED:
                pcnt += 1
            elif p.state == WorkState.RUNNING:
                acnt += 1
        return pcnt, acnt
