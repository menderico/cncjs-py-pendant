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
  address: str
  cnc_port: str
  baudrate: int
  controller_type: str

# Strings used in the config file
_SERVER_SECTION = 'server'
_DEVICE_SECTION = 'device'
_ADDRESS_OPTION = 'address'
_CNC_PORT_OPTION = 'cnc port'
_BAUDRATE_OPTION = 'baudrate'
_CONTROLLER_TYPE_OPTION = 'device type'
_GAMEPAD_OPTION = 'gamepad'
_CNC_OPTION = 'cnc machine'

def write_default_config(config_file: TextIO) -> None:
  config = configparser.ConfigParser()
  config[_SERVER_SECTION] = {}
  config[_SERVER_SECTION][_ADDRESS_OPTION] = '127.0.0.1:8080'
  config[_SERVER_SECTION][_CNC_PORT_OPTION] = '/dev/ttyACM0'
  config[_SERVER_SECTION][_BAUDRATE_OPTION] = '115200'
  config[_SERVER_SECTION][_CONTROLLER_TYPE_OPTION] = 'Grbl'
  config[_DEVICE_SECTION] = {}
  config[_DEVICE_SECTION][_GAMEPAD_OPTION] = 'PS3'
  config[_DEVICE_SECTION][_CNC_OPTION] = 'Shapeoko'
  config.write(config_file)


def get_config(config_file: TextIO) -> ConfigObjects:
  config = configparser.ConfigParser()
  config.read_file(config_file)
  
  pad = None
  commands = None

  if _DEVICE_SECTION in config:
    device = config[_DEVICE_SECTION]
    if _GAMEPAD_OPTION in device:
      pad = gamepad.get_gamepad_by_name(device[_GAMEPAD_OPTION])
      if 'cnc machine' in device:
        commands = command_mapping.get_mapping(
          gamepad=device[_GAMEPAD_OPTION],
          cnc=device[_CNC_OPTION])
  if pad and commands and _SERVER_SECTION in config:
    server_section = config[_SERVER_SECTION]
    return ConfigObjects(
      gamepad=pad, 
      mapped_commands=commands,
      address=server_section[_ADDRESS_OPTION],
      cnc_port=server_section[_ADDRESS_OPTION],
      baudrate=server_section.getint(_BAUDRATE_OPTION),
      controller_type=server_section[_CONTROLLER_TYPE_OPTION])

  raise NoValidConfigError('No valid config found in the config file')