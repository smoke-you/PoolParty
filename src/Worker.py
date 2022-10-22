from enum import Enum
from multiprocessing.connection import Connection
import random
import time

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


class Worker():

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
    def process(cls, id: int, conn: Connection):
        def check_cancel() -> bool:
            if conn.poll(0):
                msg = conn.recv()
                msg_op = msg.get('op')
                msg_id = msg.get('id')
                return msg_op == ClientOperations.CANCEL.value and (msg_id == id or msg_id is None)
            return False

        if check_cancel():
            conn.send(Worker.cancel(id))
            return
        lifespan = random.randint(3, 15) * 10
        cnt = 0
        try:
            conn.send(Worker.start(id, lifespan))
            while True:
                if check_cancel():
                    conn.send(Worker.cancel(id))
                    return
                if cnt >= lifespan:
                    conn.send(Worker.progress(id, lifespan, lifespan))
                    conn.send(Worker.finish(id))
                    break
                elif cnt % 10 == 0:
                    conn.send(Worker.progress(id, cnt, lifespan))
                time.sleep(0.1)
                cnt += 1
        except:
            conn.send(Worker.error(id))
