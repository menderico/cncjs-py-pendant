#!/usr/bin/python3
# coding: utf-8
"""
This module is designed to read inputs from a gamepad or joystick. 
"""

import asyncio
import inspect
import logging
import os
import pathlib
import struct
import sys
import threading
import time
from typing import Any, Callable, Dict, Optional


_logger = logging.getLogger('cncjs-py-pendant')

class Gamepad:
  EVENT_CODE_BUTTON = 0x01
  EVENT_CODE_AXIS = 0x02
  EVENT_CODE_INIT_BUTTON = 0x80 | EVENT_CODE_BUTTON
  EVENT_CODE_INIT_AXIS = 0x80 | EVENT_CODE_AXIS
  MIN_AXIS = -32767.0
  MAX_AXIS = +32767.0
  EVENT_BUTTON = 'BUTTON'
  EVENT_AXIS = 'AXIS'

  class UpdateThread(threading.Thread):
    """Thread used to continually run the updateState function on a Gamepad in the background

    One of these is created by the Gamepad startBackgroundUpdates function and closed by stopBackgroundUpdates"""

    def __init__(self, gamepad):
      threading.Thread.__init__(self)
      if isinstance(gamepad, Gamepad):
        self.gamepad = gamepad
      else:
        raise ValueError(
          'Gamepad update thread was not created with a valid Gamepad object')
      self.running = True

    def run(self):
      try:
        while self.running:
          self.gamepad.update_state()
        self.gamepad = None
      except:
        self.running = False
        self.gamepad = None
        raise

  def __init__(self, *,
         joystick_path: pathlib.Path = pathlib.Path('/dev/input/js0'),
         button_names: Optional[Dict[int, str]] = None,
         axis_names: Optional[Dict[int, str]] = None):
    self.joystick_path = joystick_path
    self.event_size = struct.calcsize('LhBB')
    self.pressed_map: Dict[int, bool] = {}
    self.was_pressed_map: Dict[int, bool] = {}
    self.was_released_map: Dict[int, bool] = {}
    self.axis_map: Dict[int, Callable[[], None]] = {}
    self.button_names = button_names or {}
    self.button_index: Dict[int, str] = {}
    self.axis_names = axis_names or {}
    self.axis_index: Dict[int, str] = {}
    self.last_timestamp = 0
    self.update_thread: Optional[Any] = None
    self.connected = True
    self.pressed_event_map: Dict[int, Callable[[], None]] = {}
    self.released_event_map: Dict[int, Callable[[], None]] = {}
    self.changed_event_map: Dict[int, Callable[[], None]] = {}
    self.moved_event_map: Dict[int, Callable[[], None]] = {}
    self._setup_reverse_maps()

  def __del__(self):
    try:
      self.joystick_file.close()
    except AttributeError:
      pass

  async def open(self):
    _logger.info(f'Attempting to open joystick {self.joystick_path}')
    while not self.joystick_path.exists():
      _logger.info(f'Joystick {self.joystick_path} not found, retrying in 1 second')
      await asyncio.sleep(1.0)
    self.joystick_file = self.joystick_path.open()
    _logger.info(f'Opened joystick {self.joystick_path}')

  def _setup_reverse_maps(self):
    for index in self.button_names:
      self.button_index[self.button_names[index]] = index
    for index in self.axis_names:
      self.axis_index[self.axis_names[index]] = index

  def _get_next_event_raw(self):
    """Returns the next raw event from the gamepad.

    The return format is:
      timestamp (ms), value, event type code, axis / button number
    Throws an IOError if the gamepad is disconnected"""
    if self.connected:
      try:
        raw_event = self.joystick_file.read(self.event_size)
      except IOError as e:
        self.connected = False
        raise IOError(f'Gamepad {self.joystick_path} disconnected', e)
      if raw_event is None:
        self.connected = False
        raise IOError(f'Gamepad {self.joystick_path} disconnected')
      else:
        return struct.unpack('LhBB', raw_event)
    else:
      raise IOError('Gamepad has been disconnected')

  def get_next_event(self, skip_init=True):
    """Returns the next event from the gamepad.

    The return format is:
      event name, entity name, value

    For button events the event name is BUTTON and value is either True or False.
    For axis events the event name is AXIS and value is between -1.0 and +1.0.

    Names are string based when found in the button / axis decode map.
    When not available the raw index is returned as an integer instead.

    After each call the internal state used by get_pressed and get_axis is updated.

    Throws an IOError if the gamepad is disconnected"""
    self.last_timestamp, value, event_type, index = self._get_next_event_raw()
    skip = False
    event_name = None
    entity_name = None
    final_value = None
    if event_type == Gamepad.EVENT_CODE_BUTTON:
      event_name = Gamepad.EVENT_BUTTON
      if index in self.button_names:
        entity_name = self.button_names[index]
      else:
        entity_name = index
      if value == 0:
        final_value = False
        self.was_released_map[index] = True
        for callback in self.released_event_map[index]:
          callback()
      else:
        final_value = True
        self.was_pressed_map[index] = True
        for callback in self.pressed_event_map[index]:
          callback()
      self.pressed_map[index] = final_value
      for callback in self.changed_event_map[index]:
        callback(final_value)
    elif event_type == Gamepad.EVENT_CODE_AXIS:
      event_name = Gamepad.EVENT_AXIS
      if index in self.axis_names:
        entity_name = self.axis_names[index]
      else:
        entity_name = index
      final_value = value / Gamepad.MAX_AXIS
      self.axis_map[index] = final_value
      for callback in self.moved_event_map[index]:
        callback(final_value)
    elif event_type == Gamepad.EVENT_CODE_INIT_BUTTON:
      event_name = Gamepad.EVENT_BUTTON
      if index in self.button_names:
        entity_name = self.button_names[index]
      else:
        entity_name = index
      if value == 0:
        final_value = False
      else:
        final_value = True
      self.pressed_map[index] = final_value
      self.was_pressed_map[index] = False
      self.was_released_map[index] = False
      self.pressed_event_map[index] = []
      self.released_event_map[index] = []
      self.changed_event_map[index] = []
      skip = skip_init
    elif event_type == Gamepad.EVENT_CODE_INIT_AXIS:
      event_name = Gamepad.EVENT_AXIS
      if index in self.axis_names:
        entity_name = self.axis_names[index]
      else:
        entity_name = index
      final_value = value / Gamepad.MAX_AXIS
      self.axis_map[index] = final_value
      self.moved_event_map[index] = []
      skip = skip_init
    else:
      skip = True

    if skip:
      return self.get_next_event()
    else:
      return event_name, entity_name, final_value

  def update_state(self):
    """Updates the internal button and axis states with the next pending event.

    This call waits for a new event if there are not any waiting to be processed."""
    self.last_timestamp, value, event_type, index = self._get_next_event_raw()
    if event_type == Gamepad.EVENT_CODE_BUTTON:
      if value == 0:
        final_value = False
        self.was_released_map[index] = True
        for callback in self.released_event_map[index]:
          callback()
      else:
        final_value = True
        self.was_pressed_map[index] = True
        for callback in self.pressed_event_map[index]:
          callback()
      self.pressed_map[index] = final_value
      for callback in self.changed_event_map[index]:
        callback(final_value)
    elif event_type == Gamepad.EVENT_CODE_AXIS:
      final_value = value / Gamepad.MAX_AXIS
      self.axis_map[index] = final_value
      for callback in self.moved_event_map[index]:
        callback(final_value)
    elif event_type == Gamepad.EVENT_CODE_INIT_BUTTON:
      if value == 0:
        final_value = False
      else:
        final_value = True
      self.pressed_map[index] = final_value
      self.was_pressed_map[index] = False
      self.was_released_map[index] = False
      self.pressed_event_map[index] = []
      self.released_event_map[index] = []
      self.changed_event_map[index] = []
    elif event_type == Gamepad.EVENT_CODE_INIT_AXIS:
      final_value = value / Gamepad.MAX_AXIS
      self.axis_map[index] = final_value
      self.moved_event_map[index] = []

  def start_background_updates(self, wait_for_ready=True):
    """Starts a background thread which keeps the gamepad state updated automatically.
    This allows for asynchronous gamepad updates and event callback code.

    Do not use with get_next_event"""
    if self.update_thread:
      if self.update_thread.running:
        raise RuntimeError(
          'Called startBackgroundUpdates when the update thread is already running')
    self.update_thread = Gamepad.UpdateThread(self)
    self.update_thread.start()
    if wait_for_ready:
      while not self.is_ready() and self.connected:
        time.sleep(1.0)

  def stop_background_updates(self):
    """Stops the background thread which keeps the gamepad state updated automatically.
    This may be called even if the background thread was never started.

    The thread will stop on the next event after this call was made."""
    if self.update_thread is not None:
      self.update_thread.running = False

  def is_ready(self):
    """Used with update_state to indicate that the gamepad is now ready for use.

    This is usually after the first button press or stick movement."""
    return len(self.axis_map) + len(self.pressed_map) > 1

  def wait_ready(self):
    """Convenience function which waits until the is_ready call is True."""
    self.update_state()
    while not self.is_ready() and self.connected:
      time.sleep(1.0)
      self.update_state()

  def _get_button_index(self, button_name):
    try:
      if button_name in self.button_index:
        return self.button_index[button_name]
      else:
        return int(button_name)
    except ValueError:
      raise ValueError('Button name %s was not found' % button_name)

  def is_pressed(self, button_name):
    """Returns the last observed state of a gamepad button specified by name or index.
    True if pressed, False if not pressed.

    Status is updated by getNextEvent calls.

    Throws ValueError if the button name or index cannot be found."""
    try:
      button_index = self._get_button_index(button_name)
      return self.pressed_map[button_index]
    except KeyError:
      raise ValueError('Button %i was not found' % button_index)

  def been_pressed(self, button_name):
    """Returns True if the button specified by name or index has been pressed since the last beenPressed call.
    Used in conjunction with updateState.

    Throws ValueError if the button name or index cannot be found."""
    try:
      button_index = self._get_button_index(button_name)
      if self.was_pressed_map[button_index]:
        self.was_pressed_map[button_index] = False
        return True
      else:
        return False
    except KeyError:
      raise ValueError('Button %i was not found' % button_index)

  def been_released(self, button_name):
    """Returns True if the button specified by name or index has been released since the last beenReleased call.
    Used in conjunction with updateState.

    Throws ValueError if the button name or index cannot be found."""
    try:
      button_index = self._get_button_index(button_name)
      if self.was_released_map[button_index]:
        self.was_released_map[button_index] = False
        return True
      else:
        return False
    except KeyError:
      raise ValueError('Button %i was not found' % button_index)

  def axis(self, axis_name):
    """Returns the last observed state of a gamepad axis specified by name or index.
    Throws a ValueError if the axis index is unavailable.

    Status is updated by getNextEvent calls.

    Throws ValueError if the button name or index cannot be found."""
    try:
      if axis_name in self.axis_index:
        axis_index = self.axis_index[axis_name]
      else:
        axis_index = int(axis_name)
      return self.axis_map[axis_index]
    except KeyError:
      raise ValueError('Axis %i was not found' % axis_index)
    except ValueError:
      raise ValueError('Axis name %s was not found' % axis_name)

  def available_button_names(self):
    """Returns a list of available button names for this gamepad.
    An empty list means that no button mapping has been provided."""
    return self.button_index.keys()

  def available_axis_names(self):
    """Returns a list of available axis names for this gamepad.
    An empty list means that no axis mapping has been provided."""
    return self.axis_index.keys()

  def is_connected(self):
    """Returns True until reading from the device fails."""
    return self.connected

  def disconnect(self):
    """Cleanly disconnect and remove any threads and event handlers."""
    self.connected = False
    self.stop_background_updates()
    del self.joystick_file

# Factories for common joysticks

_GAMEPADS: Dict[str, Callable[[], Gamepad]] = {}

def _gamepad_factory(factory: Callable[[], Gamepad]) -> Callable[[], Gamepad]:
  _GAMEPADS[factory.__name__] = factory
  return factory

def get_gamepad_by_name(device_name: str) -> Gamepad:
  return _GAMEPADS[device_name]()

@_gamepad_factory
def PS3() -> Gamepad:
  return Gamepad(
    axis_names={
      0: 'LEFT-X',
      1: 'LEFT-Y',
      2: 'L2',
      3: 'RIGHT-X',
      4: 'RIGHT-Y',
      5: 'R2'
    },
    button_names={
      0:  'CROSS',
      1:  'CIRCLE',
      2:  'TRIANGLE',
      3:  'SQUARE',
      4:  'L1',
      5:  'R1',
      6:  'L2',
      7:  'R2',
      8:  'SELECT',
      9:  'START',
      10: 'PS',
      11: 'L3',
      12: 'R3',
      13: 'DPAD-UP',
      14: 'DPAD-DOWN',
      15: 'DPAD-LEFT',
      16: 'DPAD-RIGHT'
    })


@_gamepad_factory
def PS4() -> Gamepad:
  return Gamepad(
    axis_names={
      0: 'LEFT-X',
      1: 'LEFT-Y',
      2: 'L2',
      3: 'RIGHT-X',
      4: 'RIGHT-Y',
      5: 'R2',
      6: 'DPAD-X',
      7: 'DPAD-Y'
    },
    button_names={
      0:  'CROSS',
      1:  'CIRCLE',
      2:  'TRIANGLE',
      3:  'SQUARE',
      4:  'L1',
      5:  'R1',
      6:  'L2',
      7:  'R2',
      8:  'SHARE',
      9:  'OPTIONS',
      10: 'PS',
      11: 'L3',
      12: 'R3'
    }
  )


@_gamepad_factory
def Xbox360() -> Gamepad:
  return Gamepad(axis_names={
    0: 'LEFT-X',
    1: 'LEFT-Y',
    2: 'LT',
    3: 'RIGHT-X',
    4: 'RIGHT-Y',
    5: 'RT'
  },
    button_names={
    0:  'A',
    1:  'B',
    2:  'X',
    3:  'Y',
    4:  'LB',
    5:  'RB',
    6:  'BACK',
    7:  'START',
    8:  'XBOX',
    9:  'LA',
    10: 'RA'
  })


@_gamepad_factory
def MMP1251() -> Gamepad:
  return Gamepad(
    axis_names={
      0: 'LEFT-X',
      1: 'LEFT-Y',
      2: 'L2',
      3: 'RIGHT-X',
      4: 'RIGHT-Y',
      5: 'R2',
      6: 'DPAD-X',
      7: 'DPAD-Y'
    },
    button_names={
      0:  'A',
      1:  'B',
      2:  'X',
      3:  'Y',
      4:  'L1',
      5:  'R1',
      6:  'SELECT',
      7:  'START',
      8:  'HOME',
      9:  'L3',
      10: 'R3'
    }
  )
