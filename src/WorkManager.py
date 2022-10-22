import asyncio
from concurrent.futures import Future, ProcessPoolExecutor
from enum import Enum
from multiprocessing import Pipe
from multiprocessing.connection import Connection, wait
from typing import Any, Awaitable, Callable

from Producer import ClientOperations, ServerOperations, Producer

class WorkManager(object):

    def __init__(self, poolsz: int, work: Callable[[int, Connection], Any], broadcast: Awaitable[dict]):
        super().__init__()
        self.poolsz = poolsz
        self.pool = ProcessPoolExecutor(self.poolsz)
        self.work = work
        self.broadcast = broadcast
        self.next_work_id = 1
        self.complete_cnt = 0
        self.worklist = WorkList()


    def start(self):
        asyncio.create_task(self.monitor_workers())

    async def monitor_workers(self):
        while True:
            msglist = self.worklist.recv(id=None, timeout=0)
            report = False
            if msglist:
                for m in msglist:
                    msg_op = m.get('op')
                    msg_id = m.get('id')
                    if msg_op == ServerOperations.START.value:
                        self.task_started(msg_id)
                        report = True
                    elif msg_op in (ServerOperations.FINISH.value, ServerOperations.ERROR.value, ServerOperations.CANCEL.value):
                        self.task_finished(msg_op, msg_id)
                        report = True
                    await self.broadcast(m)
                if report:
                    await self.broadcast(self.status())
            else:
                await asyncio.sleep(0.1)

    async def queue_task(self):
        try:
            connA, connB = Pipe(duplex=True)
            self.worklist.append_new(
                id=self.next_work_id, 
                f=self.pool.submit(self.work, self.next_work_id, connB),
                c=connA
                )
            self.next_work_id += 1
            await self.broadcast(self.status())        
        except Exception as ex:
            print(ex)

    async def cancel_task(self, msg: dict):
        msg_id = msg.get('id', None)
        msg_op = msg.get('op', None)
        target = self.worklist.get_id(msg_id)
        if target:
            target.conn.send(msg)
        elif msg_op == ClientOperations.CANCEL.value:
            if msg_id is not None:
                await self.broadcast(Producer.cancel(msg_id))
            else:
                self.worklist.cancel_all()
                self.worklist.broadcast(msg, True)
                await self.broadcast(WorkManager.status())

    def task_started(self, id: int):
        workitem = self.worklist.get_id(id)
        if workitem:
            workitem.state = WorkState.RUNNING

    def task_finished(self, op: str, id: int):
        workitem = self.worklist.get_id(id)
        if workitem:
            if op == ServerOperations.FINISH.value:
                self.complete_cnt += 1
                workitem.state = WorkState.FINISHED
            elif op in (ServerOperations.ERROR.value, ServerOperations.CANCEL.value):
                workitem.state = WorkState.FINISHED
            self.worklist.remove(workitem)

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
    def __init__(self, id: int, f: Future, c: Connection):
        self.id = id
        self.state = WorkState.QUEUED
        self.future = f
        self.conn = c


class WorkList(list[WorkItem]):

    def __init__(self):
        super().__init__()

    def append_new(self, id: int, f: Future, c: Connection):
        super().append(WorkItem(id, f, c))

    def remove_id(self, id: int):
        target = None
        for w in self:
            if w.id == id:
                target = w
                break
        if target:
            super().remove(target)

    def contains_id(self, id: int):
        if id:
            for w in self:
                if w.id == id:
                    return True
        return False

    def get_id(self, id: int):
        if id:
            for w in self:
                if w.id == id:
                    return w
        return None

    def cancel_all(self):
        cancelled = list[WorkItem]()
        for w in self:
            try:
                if w.future.cancel():
                    cancelled.append(w)
            except:
                pass
        for w in cancelled:
            self.remove(w)
    
    def counts(self) -> tuple[int, int]: # queued, running
        pcnt = 0
        acnt = 0
        for w in self:
            if w.state == WorkState.QUEUED:
                pcnt += 1
            elif w.state == WorkState.RUNNING:
                acnt += 1
        return pcnt, acnt

    def send(self, id: int, msg: dict) -> bool:
        w = self.get_id(id)
        if not w:
            return False
        else:
            w.conn.send(msg)
            return True

    def broadcast(self, msg: dict, all: bool = False):
        if not all:
            for w in self:
                if w.state == WorkState.RUNNING:
                    w.conn.send(msg)
        else:
            for w in self:
                w.conn.send(msg)
    
    def recv(self, id: int|None, timeout: float|None = 0) -> list[dict]|None:
        w = self.get_id(id)
        if w:
            c = wait([w.conn], timeout)
            if len(c) > 0:
                return c[0].recv()
        else:
            try:
                # wait for any of the worker connections to contain a message, then return all of those messages :-)
                return [m.recv() for m in wait([w.conn for w in self], timeout)]
            except:
                return None