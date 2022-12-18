import random
import time

from multiprocessing.connection import Connection

# from WorkManager import ServerOps
from models import *  # ServerOps, ServerMessage, ServerCancel, ServerError, ServerFinish, ServerProgress, ServerStart, ServerStatus, ClientCancel


def work(id: int, conn: Connection):
    def check_cancel() -> bool:
        if conn.poll(0):
            msg = conn.recv()
            return isinstance(msg, ClientCancel) and (msg.id == id or msg.id is None)
        return False

    if check_cancel():
        # conn.send(ServerOps.cancel(id))
        conn.send(ServerCancel(id=id))
        return
    lifespan = random.randint(3, 15) * 10
    cnt = 0
    try:
        # conn.send(ServerOps.start(id, lifespan))
        conn.send(ServerStart(id=id, max=lifespan))
        while True:
            if check_cancel():
                # conn.send(ServerOps.cancel(id))
                conn.send(ServerCancel(id=id))
                return
            if cnt >= lifespan:
                # conn.send(ServerOps.progress(id, lifespan, lifespan))
                # conn.send(ServerOps.finish(id))
                conn.send(ServerProgress(id=id, value=lifespan, max=lifespan))
                conn.send(ServerFinish(id=id))
                break
            elif cnt % 10 == 0:
                # conn.send(ServerOps.progress(id, cnt, lifespan))
                conn.send(ServerProgress(id=id, value=cnt, max=lifespan))
            time.sleep(0.1)
            cnt += 1
    except Exception as ex:
        print(ex)
        # conn.send(ServerOps.error(id))
        conn.send(ServerError(id=id))
