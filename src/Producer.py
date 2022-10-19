from abc import abstractmethod
from multiprocessing import Queue
import random
import time
from typing import Any

from PoolManager import PoolManager


class Producer():
    @abstractmethod
    def start(id: int, max: int) -> dict:
        return {'op': 'start', 'id': id, 'max': max}

    @abstractmethod
    def progress(id: int, value: int, max: int) -> dict:
        return {'op': 'progress', 'id': id, 'value': value, 'max': max}

    @abstractmethod
    def finish(id: int) -> dict:
        return {'op': 'finish', 'id': id}

    @abstractmethod
    def error(id: int) -> dict:
        return {'op': 'error', 'id': id}

    @abstractmethod
    def process(id: int, q: Queue):
        try:
            lifespan = random.randint(3, 12)
            q.put(Producer.start(id, lifespan), True, 1)
            cnt = 0
            while True:
                q.put(Producer.progress(id, cnt, lifespan), True, 1)
                time.sleep(1)
                cnt += 1
                if cnt >= lifespan:
                    break
        except Exception as ex:
            print(f'wtf?\n===================\n{ex}')
            q.put(Producer.error(id))
        finally:
            q.put(Producer.finish(id))
