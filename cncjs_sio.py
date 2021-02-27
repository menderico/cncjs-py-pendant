import asyncio
import json
import logging
from typing import Any, Callable, List, TextIO

import jwt
import socketio


def debug_log_handler_factory(prefix: str) -> Callable[..., None]:
    def debug_log_handler(*args) -> None:
        logging.debug(f'{prefix}: {args}')
    return debug_log_handler


def generate_access_token_from_cncrc(cncrc: TextIO) -> str:
    config = json.loads(cncrc.read())
    token = jwt.encode(
        payload={'id': '', 'name': 'cncjs-py-pendant'},
        key=config['secret'],
        algorithm='HS256')
    # Token can be either byte or string, depend on the implementation.
    return token if isinstance(token, str) else token.decode()


class CNCjs_SIO:
    """Socket IO object with pre-defined methods to communicate with CNCjs.

    """

    def __init__(self):
        self.client = socketio.AsyncClient()
        self.connected = asyncio.Event()

        self.client.on('connect', self._connect_handler)
        self.client.on('disconnect', self._disconnect_handler)
        for handler in ('serialport:read', 'serialport:write'):
            self._set_debug_handler(handler)

    def _set_debug_handler(self, handler: str):
        self.client.on(handler, debug_log_handler_factory(handler))

    async def connect(self, address: str, token: str):
        full_address = fr'ws://{address}/socket.io/\?token={token}'
        logging.info(f'Attempting to connect to {full_address}')
        while True:
            try:
                await self.client.connect(full_address)
                break
            except socketio.exceptions.ConnectionError:
                logging.warning('Unable to connect, will retry in 1 second')
                await asyncio.sleep(1)
        logging.info('Connection requested, waiting for confirmation')
        await self.connected.wait()
        logging.info(f'Connected')

    async def _connect_handler(self):
        logging.info('Server reported connection')
        self.connected.set()

    async def _disconnect_handler(self):
        logging.info('Server reported disconnection')
        self.connected.clear()
