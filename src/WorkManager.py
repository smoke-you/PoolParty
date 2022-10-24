import asyncio
import datetime
import logging
import time

from concurrent.futures import Future, ProcessPoolExecutor
from concurrent import futures
from enum import Enum
from multiprocessing import Pipe
from multiprocessing.connection import Connection, wait
from typing import Any, Awaitable, Callable


class WorkManager(object):

    def __init__(self, poolsz: int, work: Callable[[int, Connection], Any], broadcast: Awaitable[dict]):
        super().__init__()
        self._poolsz = poolsz
        self._pool = ProcessPoolExecutor(self._poolsz)
        self._started = False
        self._work = work
        self._broadcast = broadcast
        self._next_work_id = 1
        self._complete_cnt = 0
        self._worklist = WorkList()

    def start(self):
        asyncio.create_task(self._monitor_workers())
        self._started = True

    def stop(self):
        self._pool.shutdown(wait=False, cancel_futures=True)

    async def handle_client_message(self, msg: dict):
        if not self._started:
            return
        msg_op = ClientOps.get(msg.get('op', None))
        if msg_op == ClientOps.START:
            await self._queue_work()
        elif msg_op == ClientOps.CANCEL:
            await self._cancel_work(msg)

    async def _monitor_workers(self):
        while True:
            msglist = self._worklist.recv(id=None, timeout=0)
            report = False
            if msglist:
                for m in msglist:
                    msg_op = ServerOps.get(m.get('op'))
                    msg_id = m.get('id')
                    w = self._worklist.get_id(msg_id)
                    if msg_op == ServerOps.START:
                        forward = self._work_started(w)
                    elif msg_op in (ServerOps.PROGRESS, ServerOps.POOL):
                        forward = w != None
                    else:  # implied: FINISH, ERROR, CANCEL
                        forward = self._work_finished(msg_op, w)
                    if forward:
                        report = True
                        await self._broadcast(m)
                if report:
                    await self._broadcast(self.status())
            else:
                await asyncio.sleep(0.1)

    async def _queue_work(self):
        try:
            logging.info(f'Requested work id={self._next_work_id}')
            connA, connB = Pipe(duplex=True)
            self._worklist.append_new(
                id=self._next_work_id, 
                f=self._pool.submit(self._work, self._next_work_id, connB),
                c=connA
                )
            self._next_work_id += 1
            await self._broadcast(self.status())        
        except Exception as ex:
            print(ex)

    async def _cancel_work(self, msg: dict):
        msg_id = msg.get('id', None)
        target = self._worklist.get_id(msg_id)
        if target:
            logging.info(f'Requested cancellation of work id={target.id}')
            target.conn.send(msg)
        elif not msg_id:
            logging.info(f'Requested cancellation of work {list(map(lambda x: x.id, self._worklist))}')
            for w_id in self._worklist.cancel_all():
                await self._broadcast(ServerOps.cancel(w_id))
            self._worklist.broadcast(msg, True)
            await self._broadcast(self.status())

    def _work_started(self, w: 'WorkItem | None') -> bool:
        if w:
            logging.info(f'Work id={w.id} started')
            w.state = WorkState.RUNNING
            return True
        return False

    def _work_finished(self, msg_op: 'ServerOps', w: 'WorkItem | None') -> bool:
        # *only* publish FINISH, ERROR (and CANCEL, but see below) messages if the workitem is queued for processing
        if w:
            if msg_op == ServerOps.FINISH:
                duration = datetime.datetime.now() - w.timestamp
                dur_sus = round(duration.seconds + (duration.microseconds / 1000000), 3)
                logging.info(f'Work id={w.id} finished normally in {dur_sus}s')
                self._complete_cnt += 1
                w.state = WorkState.FINISHED
                self._worklist.remove(w)
                return True
            elif msg_op in (ServerOps.ERROR, ServerOps.CANCEL):
                if msg_op == ServerOps.CANCEL:
                    logging.info(f'Work id={w.id} cancelled')
                else:
                    logging.info(f'Work id={w.id} failed')
                w.state = WorkState.FINISHED
                self._worklist.remove(w)
                return True
        # *always* publish CANCEL messages, even if the workitem is not queued for processing
        elif msg_op == ServerOps.CANCEL:
            return True
        return False

    def status(self) -> dict:
        return ServerOps.status(self._complete_cnt, *self._worklist.counts())


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
        self.timestamp = datetime.datetime.now()
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

    def contains_id(self, id: int) -> bool:
        if id:
            for w in self:
                if w.id == id:
                    return True
        return False

    def get_id(self, id: int) -> WorkItem|None:
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
        if cancelled:
            logging.info(f'Work {list(map(lambda x: x.id, cancelled))} cancelled from queue.')
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
        if w:
            w.conn.send(msg)
            return True
        return False

    def broadcast(self, msg: dict, all: bool = False):
        if all:
            for w in self:
                w.conn.send(msg)
        else:
            for w in self:
                if w.state == WorkState.RUNNING:
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
                pass
        # if timeout, or if one of the monitored connection objects is closed
        return None