from abc import abstractmethod
from enum import Enum
from multiprocessing import Queue
import queue
import random
import time
from typing import Any

class ServerOperations(Enum):
    START = 'start'
    PROGRESS = 'progress'
    FINISH = 'finish'
    ERROR = 'error'
    CANCEL = 'cancel'
    POOL = 'pool'


class ClientOperations(Enum):
    START = 'start'
    CANCEL = 'cancel'


class Producer():

    @abstractmethod
    def start(id: int, max: int) -> dict:
        return {'op': ServerOperations.START.value, 'id': id, 'max': max}

    @abstractmethod
    def progress(id: int, value: int, max: int) -> dict:
        return {'op': ServerOperations.PROGRESS.value, 'id': id, 'value': value, 'max': max}

    @abstractmethod
    def finish(id: int) -> dict:
        return {'op': ServerOperations.FINISH.value, 'id': id}

    @abstractmethod
    def cancel(id: int) -> dict:
        return {'op': ServerOperations.CANCEL.value, 'id': id}

    @abstractmethod
    def error(id: int) -> dict:
        return {'op': ServerOperations.ERROR.value, 'id': id}

    @abstractmethod
    def process(id: int, outq: Queue, inq: Queue):
        try:
            lifespan = random.randint(3, 12) * 10
            outq.put(Producer.start(id, lifespan), True, 1)
            cnt = 0
            while True:
                try:
                    msg = inq.get(False)
                    op_id = msg.get('id', None)
                    if not op_id:
                        pass
                    elif op_id != id:
                        inq.put(msg)
                    else:
                        op = msg.get('op', None)
                        if op == ClientOperations.CANCEL.value:
                            outq.put(Producer.cancel(id), True, 1)
                            return
                except queue.Empty:
                    pass
                if cnt >= lifespan:
                    break
                if cnt % 10 == 0:
                    outq.put(Producer.progress(id, cnt, lifespan), True, 1)
                time.sleep(0.1)
                cnt += 1
            outq.put(Producer.finish(id))
        except Exception as ex:
            print(f'wtf?\n===================\n{ex}')
            outq.put(Producer.error(id))
