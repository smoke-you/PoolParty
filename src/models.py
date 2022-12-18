from pydantic import BaseModel, parse_obj_as
from enum import Enum
from typing import Optional


class ServerOps(str, Enum):
    START = 'start'
    PROGRESS = 'progress'
    FINISH = 'finish'
    ERROR = 'error'
    CANCEL = 'cancel'
    POOL = 'pool'

    @classmethod
    def get(cls, value, default=None):
        if not value:
            return default
        try:
            if value in cls.__members__.values():
                return value
        except:
            pass
        try:
            for v in (v for v in cls.__members__.values() if v.value == value):
                return v
        except:
            pass
        return default


class ServerMessage:
    pass


class ServerStart(ServerMessage, BaseModel):
    op = ServerOps.START
    id: int
    max: int


class ServerProgress(ServerMessage, BaseModel):
    op = ServerOps.PROGRESS
    id: int
    value: int
    max: int


class ServerFinish(ServerMessage, BaseModel):
    op = ServerOps.FINISH
    id: int


class ServerCancel(ServerMessage, BaseModel):
    op = ServerOps.CANCEL
    id: int


class ServerError(ServerMessage, BaseModel):
    op = ServerOps.ERROR
    id: int


class ServerStatus(ServerMessage, BaseModel):
    op = ServerOps.POOL
    completed: int
    active: int
    queued: int


class ClientOps(str, Enum):
    START = 'start'
    CANCEL = 'cancel'

    @classmethod
    def get(cls, value, default=None):
        if not value:
            return default
        try:
            if value in cls.__members__.values():
                return value
        except:
            pass
        try:
            for v in (v for v in cls.__members__.values() if v.value == value):
                return v
        except:
            pass
        return default


class ClientMessage:
    pass


class ClientStart(ClientMessage, BaseModel):
    op = ClientOps.START


class ClientCancel(ClientMessage, BaseModel):
    op = ClientOps.CANCEL
    id: Optional[int]


def __parse_msg(types: list, msg: dict):
    op = msg.get('op', None)
    if not op:
        raise ValueError(f'The argument {msg} does not appear to be a valid message')
    for x in types:
        try:
            if x.__fields__['op'].default.value == op:
                return parse_obj_as(x, msg)
        except:
            pass
    raise ValueError(f"No listed message type matches 'op'='{op}'")


__client_msg_types: tuple[ClientMessage] = (ClientStart, ClientCancel)
__server_msg_types: tuple[ServerMessage] = (ServerCancel, ServerError, ServerFinish, ServerProgress, ServerStart, ServerStatus)


def parse_client_msg(msg: dict) -> ClientMessage:
    return __parse_msg(__client_msg_types, msg)


def parse_server_msg(msg: dict) -> ServerMessage:
    return __parse_msg(__server_msg_types, msg)


