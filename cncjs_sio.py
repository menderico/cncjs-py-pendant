import asyncio
import logging
import socketio

from typing import Callable, List, Any

def debug_log_handler_factory(prefix: str) -> Callable[..., None]:
  def debug_log_handler(*args) -> None:
    logging.debug(f'{prefix}: {args}')
  return debug_log_handler


class CNCjs_SIO:
  """Socket IO object with pre-defined methods to communicate with CNCjs.
  
  """
  def __init__(self):
    self.client = socketio.AsyncClient()
    self.connected = asyncio.Event()
    self.client.on('connect', self._connect_handler)
    self.client.on('disconnect', self._disconnect_handler)
    for handler in ('serialport:read', 'serialport_write'):
      self._set_debug_handler(handler)

  def _set_debug_handler(self, handler: str):
    self.client.on(handler, debug_log_handler_factory(handler))

  async def connect(self, address: str, token: str):
    full_address = fr'ws://{address}/socket.io/\?token={token}'
    logging.info(f'Attempting to connect to {full_address}')
    await self.client.connect(full_address)
    logging.info('Connection requested, waiting for confirmation')
    await self.connected.wait()
    logging.info(f'Connected, SID: {self.client.get_sid()}')

  async def _connect_handler(self):
    logging.info('Server reported connection')
    self.connected.set()

  async def _disconnect_handler(self):
    logging.info('Server reported disconnection')
    self.connected.clear()