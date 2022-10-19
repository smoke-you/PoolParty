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
from PoolManager import PoolManager
from Producer import Producer


app = FastAPI()
app_path = Path(__file__).parent
app.mount('/static', StaticFiles(directory=app_path.joinpath('static')), name='static')
app_templates = Jinja2Templates(directory=app_path.joinpath('templates'))
sock_mgr = ConnectionManager()
# the pool manager (and other multiprocessing objects, including Pool and 
# Queue) *cannot* be initialized until fastAPI has started
pool_mgr: PoolManager


@app.get('/')
def get_root(request: Request):
    return app_templates.TemplateResponse('threading2.html', {'request': request})


async def consumer(q: Queue):
    while True:
        try:
            msg = q.get(False)
            await sock_mgr.broadcast(msg)
            op = msg.get('op', None)
            if op == 'start':
                pool_mgr.active_cnt += 1
                pool_mgr.queue_cnt -= 1
            elif op == 'finish':
                pool_mgr.complete_cnt += 1
                pool_mgr.active_cnt -= 1
            if op == 'start' or op == 'finish':
                await sock_mgr.broadcast(pool_mgr.status())
        except queue.Empty:
            await asyncio.sleep(0.1)


@app.on_event('startup')
async def startup_event():
    global pool_mgr
    pool_mgr = PoolManager(4, Producer.process)
    asyncio.create_task(consumer(pool_mgr.queue))


@app.websocket('/ws')
async def websocket_endpoint(sock: WebSocket):
    try:
        await sock_mgr.connect(sock)
        await sock.send_json(pool_mgr.status())
        while True:
            try:
                msg = await asyncio.wait_for(sock.receive_json(), 1)
                op = msg.get('op', None)
                if op == 'start':
                    pool_mgr.start()
            except WebSocketDisconnect:
                raise WebSocketDisconnect
            except:
                pass
    except WebSocketDisconnect:
        print(f'Client at (\'{sock.client.host}\',{sock.client.port}) disconnected OK')
    except Exception as ex:
        print(f'Client at (\'{sock.client.host}\',{sock.client.port}) disconnected unexpectedly:\n{ex}')
    finally:
        sock_mgr.disconnect(sock)


if __name__ == '__main__':
    uvicorn.run('main:app', host='192.168.56.102', port=7000, reload=True)
