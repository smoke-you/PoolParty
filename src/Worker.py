import random
import time

from multiprocessing.connection import Connection

from WorkManager import ClientOps, ServerOps


def work(id: int, conn: Connection):
    def check_cancel() -> bool:
        if conn.poll(0):
            msg = conn.recv()
            msg_op = ClientOps.get(msg.get('op'))
            msg_id = msg.get('id')
            return msg_op == ClientOps.CANCEL and (msg_id == id or msg_id is None)
        return False

    if check_cancel():
        conn.send(ServerOps.cancel(id))
        return
    lifespan = random.randint(3, 15) * 10
    cnt = 0
    try:
        conn.send(ServerOps.start(id, lifespan))
        while True:
            if check_cancel():
                conn.send(ServerOps.cancel(id))
                return
            if cnt >= lifespan:
                conn.send(ServerOps.progress(id, lifespan, lifespan))
                conn.send(ServerOps.finish(id))
                break
            elif cnt % 10 == 0:
                conn.send(ServerOps.progress(id, cnt, lifespan))
            time.sleep(0.1)
            cnt += 1
    except Exception as ex:
        print(ex)
        conn.send(ServerOps.error(id))
