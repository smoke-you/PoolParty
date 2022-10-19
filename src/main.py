from abc import abstractmethod
import asyncio
import queue
import random
import time
import uvicorn

from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.websockets import WebSocket, WebSocketDisconnect
from multiprocessing import Pool, Manager, Queue
from pathlib import Path

from ConnectionManager import ConnectionManager


app = FastAPI()
app_path = Path(__file__).parent
app.mount('/static', StaticFiles(directory=app_path.joinpath('static')), name='static')
app_templates = Jinja2Templates(directory=app_path.joinpath('templates'))
sock_mgr = ConnectionManager()
proc_pool: Pool
proc_queue: Queue
proc_cnt = 0


@app.get('/')
def get_root(request: Request):
    # return FileResponse(app_path.joinpath('threading.html'))
    return app_templates.TemplateResponse('threading.html', {'request': request})


class ProducerMessage():
    @abstractmethod
    def start(id: int, max: int) -> dict:
        return {'op': 'start', 'id': id, 'max': max}

    @abstractmethod
    def progress(id: int, value: int) -> dict:
        return {'op': 'progress', 'id': id, 'value': value}

    @abstractmethod
    def finish(id: int) -> dict:
        return {'op': 'finish', 'id': id}

    @abstractmethod
    def error(id: int) -> dict:
        return {'op': 'error', 'id': id}



def producer(id: int, q: Queue):
    lifespan = random.randint(3, 12)
    q.put(ProducerMessage.start(id, lifespan))
    cnt = 0
    while True:
        q.put(ProducerMessage.progress(id, cnt))
        time.sleep(1)
        cnt += 1
        if cnt >= lifespan:
            q.put(ProducerMessage.finish(id))
            return


async def consumer(q: Queue):
    while True:
        try:
            await sock_mgr.broadcast(q.get(False, 1))
        except queue.Empty:
            await asyncio.sleep(1)


@app.on_event('startup')
async def startup_event():
    global proc_pool, proc_queue
    pcnt = 4
    proc_queue = Manager().Queue()
    proc_pool = Pool(pcnt)
    asyncio.create_task(consumer(proc_queue))


@app.websocket('/ws')
async def websocket_endpoint(sock: WebSocket):
    global proc_pool, proc_cnt, proc_queue
    try:
        await sock_mgr.connect(sock)
        while True:
            try:
                msg = await asyncio.wait_for(sock.receive_json(), 1)
                op = msg.get('op', None)
                if op == 'start':
                    proc_pool.apply_async(func=producer, args=(proc_cnt, proc_queue))
                    proc_cnt += 1
            except WebSocketDisconnect:
                raise WebSocketDisconnect
            except:
                pass
    except WebSocketDisconnect:
        pass
    except Exception as ex:
        print(f'WebSocket disconnected unexpectedly:\n{ex}')
    finally:
        sock_mgr.disconnect(sock)


if __name__ == '__main__':
    uvicorn.run('main:app', host='192.168.56.102', port=7000, reload=True)
