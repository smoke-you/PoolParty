from abc import abstractmethod
from enum import Enum
from multiprocessing import Queue
import queue
import random
import time
from typing import Any, Optional

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

    @classmethod
    def start(cls, id: int, max: int) -> dict:
        return {'op': ServerOperations.START.value, 'id': id, 'max': max}

    @classmethod
    def progress(cls, id: int, value: int, max: int) -> dict:
        return {'op': ServerOperations.PROGRESS.value, 'id': id, 'value': value, 'max': max}

    @classmethod
    def finish(cls, id: int) -> dict:
        return {'op': ServerOperations.FINISH.value, 'id': id}

    @classmethod
    def cancel(cls, id: int) -> dict:
        return {'op': ServerOperations.CANCEL.value, 'id': id}

    @classmethod
    def error(cls, id: int) -> dict:
        return {'op': ServerOperations.ERROR.value, 'id': id}

    @classmethod
    def process(cls, id: int, outq: Queue, inq: Queue):
        def safesend(q: queue, msg: dict, interval: Optional[float] = None):
            if interval:
                while True:
                    try:
                        q.put(msg)
                        break
                    except:
                        time.sleep(interval)
            else:
                try:
                    q.put(msg)
                except:
                    pass

        lifespan = random.randint(15, 30) * 10
        cnt = 0
        try:
            safesend(outq, Producer.start(id, lifespan), 0.01)
            while True:
                try:
                    msg = inq.get_nowait()
                    if msg.get('id', None) != id:
                        safesend(inq, msg, 0.01)
                    else:
                        if msg.get('op', None) == ClientOperations.CANCEL.value:
                            safesend(outq, Producer.cancel(id), 0.01)
                            return
                except (queue.Empty, TypeError):
                    pass
                except BaseException as ex:
                    print(ex)
                if cnt >= lifespan:
                    safesend(outq, Producer.progress(id, lifespan, lifespan))
                    break
                elif cnt % 10 == 0:
                    safesend(outq, Producer.progress(id, cnt, lifespan))
                time.sleep(0.1)
                cnt += 1
            safesend(outq, Producer.finish(id), 0.01)
        except BaseException as ex:
            print(ex)
            safesend(outq, Producer.error(id), 0.01)
