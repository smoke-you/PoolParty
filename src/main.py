import asyncio
import logging
import uvicorn

from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.websockets import WebSocket, WebSocketDisconnect
from pathlib import Path

from ConnectionManager import ConnectionManager
from Worker import work
from WorkManager import WorkManager
from models import parse_client_msg


app = FastAPI()
app_path = Path(__file__).parent
app.mount('/static', StaticFiles(directory=app_path.joinpath('static')), name='static')
sock_mgr = ConnectionManager()
work_mgr = WorkManager(4, work, sock_mgr.broadcast)


@app.get('/')
def get_root(request: Request):
    logging.info(f'HTTP GET from {request.client.host}:{request.client.port}')
    return FileResponse(app_path.joinpath('static/threading.html'))


@app.on_event('startup')
def startup_event():
    try:
        Path.mkdir(app_path.joinpath('../logs/'), parents=True, exist_ok=True)
        logging.basicConfig(
            filename=app_path.joinpath('../logs/pool.log'),
            level=logging.INFO,
            format='%(asctime)s,%(levelname)s,"%(message)s"', 
            datefmt='%Y-%m-%d %H:%M:%S'
            )
    except Exception as ex:
        print(f'Failed to create log file:\n{ex}')
    logging.info('Server started')
    work_mgr.start()


@app.on_event('shutdown')
def shutdown_event():
    work_mgr.stop()
    logging.info('Server shutdown')


@app.websocket('/ws')
async def websocket_endpoint(sock: WebSocket):
    try:
        await sock_mgr.connect(sock)
        logging.info(f'Websocket from {sock.client.host}:{sock.client.port} opened')
        await sock.send_json(work_mgr.status())
        while True:
            try:
                await work_mgr.handle_client_message(
                    parse_client_msg(await asyncio.wait_for(sock.receive_json(), 1))
                    )
            except WebSocketDisconnect:
                raise WebSocketDisconnect
            except:
                pass
    except WebSocketDisconnect:
        logging.info(f'Websocket from {sock.client.host}:{sock.client.port} closed')
        print(f'Client at (\'{sock.client.host}\',{sock.client.port}) disconnected OK')
    except Exception as ex:
        logging.info(f'Websocket from {sock.client.host}:{sock.client.port} crashed')
        print(f'Client at (\'{sock.client.host}\',{sock.client.port}) disconnected unexpectedly:\n{ex}')
    finally:
        sock_mgr.disconnect(sock)


if __name__ == '__main__':
    uvicorn.run('main:app', host='192.168.56.102', port=6999, reload=False)
