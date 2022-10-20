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
        lifespan = random.randint(3, 12) * 10
        cnt = 0
        try:
            outq.put(Producer.start(id, lifespan))
            while True:
                try:
                    msg = inq.get_nowait()
                    op_id = msg.get('id', None)
                    if op_id and op_id != id:
                        inq.put(msg)
                    else:
                        op = msg.get('op', None)
                        if op == ClientOperations.CANCEL.value:
                            outq.put(Producer.cancel(id))
                            return
                except (queue.Empty, TypeError):
                    pass
                except BaseException as ex:
                    print(ex)
                if cnt >= lifespan:
                    break
                if cnt % 10 == 0:
                    outq.put(Producer.progress(id, cnt, lifespan))
                time.sleep(0.1)
                cnt += 1
            outq.put(Producer.finish(id))
            return
        except BaseException as ex:
            outq.put(Producer.error(id))
