import asyncio

from concurrent.futures import Future, ProcessPoolExecutor
from enum import Enum
from multiprocessing import Pipe
from multiprocessing.connection import Connection, wait
from typing import Any, Awaitable, Callable


class WorkManager(object):

    def __init__(self, poolsz: int, work: Callable[[int, Connection], Any], broadcast: Awaitable[dict]):
        super().__init__()
        self.__poolsz = poolsz
        self.__pool = ProcessPoolExecutor(self.__poolsz)
        self.__started = False
        self.__work = work
        self.__broadcast = broadcast
        self.__next_work_id = 1
        self.__complete_cnt = 0
        self.__worklist = WorkList()


    def start(self):
        asyncio.create_task(self.monitor_workers())
        self.__started = True

    def stop(self):
        self.__pool.shutdown(wait=False, cancel_futures=True)

    async def monitor_workers(self):
        while True:
            msglist = self.__worklist.recv(id=None, timeout=0)
            report = False
            if msglist:
                for m in msglist:
                    msg_op = ServerOps.get(m.get('op'))
                    msg_id = m.get('id')
                    if msg_op == ServerOps.START:
                        self.work_started(msg_id)
                        report = True
                    elif msg_op in (ServerOps.FINISH, ServerOps.ERROR, ServerOps.CANCEL):
                        self.work_finished(msg_op, msg_id)
                        report = True
                    await self.__broadcast(m)
                if report:
                    await self.__broadcast(self.status())
            else:
                await asyncio.sleep(0.1)

    async def handle_client_message(self, msg: dict):
        if not self.__started:
            return
        msg_op = ClientOps.get(msg.get('op', None))
        if msg_op == ClientOps.START:
            await self.queue_work()
        elif msg_op == ClientOps.CANCEL:
            await self.cancel_work(msg)

    async def queue_work(self):
        try:
            connA, connB = Pipe(duplex=True)
            self.__worklist.append_new(
                id=self.__next_work_id, 
                f=self.__pool.submit(self.__work, self.__next_work_id, connB),
                c=connA
                )
            self.__next_work_id += 1
            await self.__broadcast(self.status())        
        except Exception as ex:
            print(ex)

    async def cancel_work(self, msg: dict):
        msg_id = msg.get('id', None)
        target = self.__worklist.get_id(msg_id)
        if target:
            target.conn.send(msg)
        elif not msg_id:
            for w_id in self.__worklist.cancel_all():
                await self.__broadcast(ServerOps.cancel(w_id))
            self.__worklist.broadcast(msg, True)
            await self.__broadcast(self.status())

    def work_started(self, id: int):
        workitem = self.__worklist.get_id(id)
        if workitem:
            workitem.state = WorkState.RUNNING

    def work_finished(self, msg_op: 'ServerOps', id: int):
        workitem = self.__worklist.get_id(id)
        if workitem:
            if msg_op == ServerOps.FINISH:
                self.__complete_cnt += 1
                workitem.state = WorkState.FINISHED
            elif msg_op in (ServerOps.ERROR, ServerOps.CANCEL):
                workitem.state = WorkState.FINISHED
            self.__worklist.remove(workitem)

    def status(self) -> dict:
        return ServerOps.status(self.__complete_cnt, *self.__worklist.counts())


class ServerOps(Enum):
    START = 'start'
    PROGRESS = 'progress'
    FINISH = 'finish'
    ERROR = 'error'
    CANCEL = 'cancel'
    POOL = 'pool'

    @classmethod
    def get(cls, value: str|None) -> str|None:
        if not value:
            return None
        try:
            for v in cls.__members__.values():
                if v.value == value:
                    return v
        except:
            pass
        return None

    @classmethod
    def start(cls, id: int, max: int) -> dict:
        return {'op': cls.START.value, 'id': id, 'max': max}

    @classmethod
    def progress(cls, id: int, value: int, max: int) -> dict:
        return {'op': cls.PROGRESS.value, 'id': id, 'value': value, 'max': max}

    @classmethod
    def finish(cls, id: int) -> dict:
        return {'op': cls.FINISH.value, 'id': id}

    @classmethod
    def cancel(cls, id: int) -> dict:
        return {'op': cls.CANCEL.value, 'id': id}

    @classmethod
    def error(cls, id: int) -> dict:
        return {'op': cls.ERROR.value, 'id': id}

    @classmethod
    def status(cls, completed: int, queued: int, active: int):
        return {'op': cls.POOL.value, 'completed': completed, 'active': active, 'queued': queued}


class ClientOps(Enum):
    START = 'start'
    CANCEL = 'cancel'

    @classmethod
    def get(cls, value: str|None) -> str|None:
        if not value:
            return None
        try:
            for v in cls.__members__.values():
                if v.value == value:
                    return v
        except:
            pass
        return None


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

    def cancel_all(self) -> list[int]:
        cancelled = list[WorkItem]()
        for w in self:
            try:
                if w.future.cancel():
                    cancelled.append(w)
            except:
                pass
        for w in cancelled:
            self.remove(w)
        return [w.id for w in cancelled]
    
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
                # if timeout, or if one of the monitored connection objects is closed
                return None