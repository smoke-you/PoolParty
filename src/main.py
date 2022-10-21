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
from multiprocessing import Queue
from pathlib import Path

from ConnectionManager import ConnectionManager
from PoolManager import PoolManager
from Producer import ClientOperations, Producer, ServerOperations


app = FastAPI()
app_path = Path(__file__).parent
app.mount('/static', StaticFiles(directory=app_path.joinpath('static')), name='static')
app_templates = Jinja2Templates(directory=app_path.joinpath('templates'))
sock_mgr = ConnectionManager()
# the pool manager (and other multiprocessing objects, including Pool and 
# Queue) *cannot* be initialized until *after* fastAPI has started
pool_mgr: PoolManager


@app.get('/')
def get_root(request: Request):
    return app_templates.TemplateResponse('threading2.html', {'request': request})


async def consumer(outq: Queue):
    while True:
        try:
            msg = outq.get(False)
            await sock_mgr.broadcast(msg)
            op = msg.get('op', None)
            id = msg.get('id', None)
            if op == ServerOperations.START.value:
                pool_mgr.task_started(id)
            elif op in (ServerOperations.FINISH.value, ServerOperations.ERROR.value, ServerOperations.CANCEL.value):
                pool_mgr.task_finished(op, id)
        except queue.Empty:
            await asyncio.sleep(0.1)


@app.on_event('startup')
async def startup_event():
    global pool_mgr
    pool_mgr = PoolManager(4, Producer.process)
    asyncio.create_task(consumer(pool_mgr.outq))


@app.on_event('shutdown')
async def shutdown_event():
    global pool_mgr
    pool_mgr.pool.shutdown()


@app.websocket('/ws')
async def websocket_endpoint(sock: WebSocket):
    try:
        await sock_mgr.connect(sock)
        await sock.send_json(pool_mgr.status())
        while True:
            try:
                msg = await asyncio.wait_for(sock.receive_json(), 1)
                op = msg.get('op', None)
                if op == ClientOperations.START.value:
                    pool_mgr.queue_task()
                elif op == ClientOperations.CANCEL.value:
                    pool_mgr.cancel_task(msg)
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
    uvicorn.run('main:app', host='192.168.56.102', port=6999, reload=True)
