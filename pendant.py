#!/usr/bin/python3

import asyncio
import collections
import datetime
import dataclasses
import json
import jwt
import logging
import pathlib
import sys

import gamepad
import cncjs_sio
import command_mapping
import config_manager

from typing import Tuple, Dict

@dataclasses.dataclass
class Move:
  direction: int = 0
  magnitude_axis: command_mapping.MagnitudeAxis = command_mapping.MagnitudeAxis()


def get_commands(config: config_manager.ConfigObjects) -> Tuple[command_mapping.Command, ...]:
  moves: Dict[command_mapping.MovementAxis, Move] = collections.defaultdict(Move)

  for action in config.mapped_commands:
    if action.button:
      pressed = (config.gamepad.is_pressed(action.button) if action.repeat_if_pressed
             else config.gamepad.been_pressed(action.button))
      if pressed:
        if action.commands:
          return action.commands
        if action.movement_axis and action.direction:
          moves[action.movement_axis].direction += action.direction.value
          moves[action.movement_axis].magnitude_axis = action.magnitude_axis

    if action.axis:
      axis_value = config.gamepad.axis(action.axis.label)
      if action.axis.has_triggered(axis_value):
        moves[action.movement_axis].direction += (
          int(axis_value / abs(axis_value)) * action.axis_direction_multiplier())
        moves[action.movement_axis].magnitude_axis = action.axis

  # Process movement requests.
  gcode_moves = []
  for axis, move in moves.items():
    if move.direction:
      distance = move.magnitude_axis.travel_distance(
        config.gamepad.axis(move.magnitude_axis.label))
      gcode_moves.append(f'{axis.value}{distance * move.direction}')
  if gcode_moves:
    # Set G-code prefixes for the move
    gcode_moves = ['G91'] + gcode_moves
    return (command_mapping.Command(('gcode', ' '.join(gcode_moves)),),
        command_mapping.Command(('gcode', 'G90'),))

  return ()


async def main():
  # Set up logging
  file_handler = logging.FileHandler(filename='tmp.log')
  stdout_handler = logging.StreamHandler()
  handlers = [file_handler, stdout_handler]

  logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s',
    handlers=handlers
  )

  # Open config files
  config_path = pathlib.Path('~/.cncjs_py_pendant_config').expanduser().resolve()
  if not config_path.exists():
    with config_path.open('w') as config_file:
      config_manager.write_default_config(config_file)

  with config_path.open('r') as config_file:
    config = config_manager.get_config(config_file) 

  cncrc_config = pathlib.Path('~/.cncrc').expanduser().resolve()
  with cncrc_config.open('r') as f:
    token = cncjs_sio.generate_access_token_from_cncrc(f)

  sio = cncjs_sio.CNCjs_SIO()
  await sio.connect(config.address, token)
  await sio.client.emit('open', (config.cnc_port, {'baudrate': config.baudrate, 'controllerType': config.controller_type}))
  if not gamepad.available():
    print('Please connect your gamepad...')
    while not gamepad.available():
      await asyncio.sleep(1.0)

  config.gamepad.start_background_updates()
  while await sio.connected.wait():
    commands = get_commands(config)
    if commands:
      for command in commands:
        await sio.client.emit('command', (config.cnc_port,) + command.arguments)
    await sio.client.sleep(0.1)

if __name__ == '__main__':
  asyncio.run(main())
