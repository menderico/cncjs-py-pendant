import configparser
import dataclasses

import gamepad
import command_mapping

from typing import TextIO, Tuple


class NoValidConfigError(Exception):
  """No valid config present in the config file."""


@dataclasses.dataclass(frozen=True)
class ConfigObjects:
  gamepad: gamepad.Gamepad
  mapped_commands: command_mapping.Tuple[command_mapping.MappedCommand, ...]

# Strings used in the config file
_DEVICE_SECTION = 'device'
_GAMEPAD_CONFIG = 'gamepad'
_CNC_CONFIG = 'cnc machine'

def write_default_config(config_file: TextIO) -> None:
  config = configparser.ConfigParser()
  config[_DEVICE_SECTION] = {}
  config[_DEVICE_SECTION][_GAMEPAD_CONFIG] = 'PS3'
  config[_DEVICE_SECTION][_CNC_CONFIG] = 'Shapeoko'
  config.write(config_file)


def get_config(config_file: TextIO) -> ConfigObjects:
  config = configparser.ConfigParser()
  config.read_file(config_file)
  
  pad = None
  commands = None
  
  if 'device' in config:
    if 'gamepad' in config['device']:
      pad = gamepad.get_gamepad_by_name(config['device']['gamepad'])
      if 'cnc machine' in config['device']:
        commands = command_mapping.get_mapping(
          gamepad=config['controller']['device'],
          cnc=config['controller']['cnc machine'])
  if pad and commands:
    return ConfigObjects(gamepad=pad, mapped_commands=commands)

  raise NoValidConfigError('No valid config found in the config file')