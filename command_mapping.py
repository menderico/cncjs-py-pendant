#!/usr/bin/python3

import dataclasses
import enum

from typing import Tuple


@dataclasses.dataclass(frozen=True)
class Command:
    """An individual command to be sent to CNCjs.

       Commands are sequence of arguments (strings) to be sent to the CNCjs server
       using the "emit" message type.

       Attributes:
         arguments: a tuple of arguments to be sent to the server, ordered
    """
    arguments: Tuple[str]


class MovementAxis(enum.Enum):
    """Axis/Plane of movement."""
    X = 'X'
    Y = 'Y'
    Z = 'Z'


class Direction(enum.Enum):
    """Direction of the movement (increasing or decreasing"""
    POSITIVE = 1
    NEGATIVE = -1


@dataclasses.dataclass(frozen=True)
class MagnitudeAxis:
    """Describes how to convert an axis input into movement steps

    Attributes:
      label: axis label on the joystick.
      slow_move_step: amount to be moved in case there is just a small press
        or movement on the joystick axis
      mid_move_step: amount to be moved for intermediate press or movements
      fast_move_ste: amount to be moved for large press or movement of the
        joystick axis (i.e., close to fully pressed)
      slow_when_below: consider the axis to have just a "small press" if
        the input is below this threshold.
      fast_when_above: consider the axis to be "fully pressed" if the input is above
        this threshold
      trigger_if_above: consider the axis to have been moved / triggered if the value is
        above this threshold. If unset, the axis will always be considered "triggered", and
        another method is needed to verify that is has been pressed (for instance, check button
        press)
      use_absolute_input: if set the input will always be considered by its absolute
        value. Should be set for directional axis, where the signal is used to indicate
        the direction of the movement and the value represents the "intensity" of the
        movement.
    """
    label: str
    slow_move_step: float = 0.1
    mid_move_step: float = 1
    fast_move_step: float = 10
    slow_when_below: float = 0.0
    fast_when_above: float = 0.8
    trigger_if_above: float = None
    use_absolute_input: bool = False

    def has_triggered(self, input: float) -> bool:
      """Determines whether the axis has triggered.

         Args:
           input: numerical value returned by the joystick axis.
      """
      if self.use_absolute_input:
        input = abs(input)
      # Note 0.0 is a valid limit for triggering (not useful, but valid), so
      # we need to check for None explicitly.
      if self.trigger_if_above == None:
        return True
      return input > self.trigger_if_above

    def travel_distance(self, input: float) -> float:
      """Transforms Joystick axis input into the travel distance for the CNC head.

         Args:
           input: numerical value returned by the joystick axis.
      """
      if self.use_absolute_input:
          input = abs(input)
      if input < self.slow_when_below:
          return self.slow_move_step
      if input > self.fast_when_above:
          return self.fast_move_step
      return self.mid_move_step


@dataclasses.dataclass(frozen=True)
class MappedCommand:
  """A command mapped to inputs from the joystick.

  Attributes:
    button: joystick button mapped to the command.
    axis: joystick axis mapped to the command
    reverse_axis_direction: if set, inverts the signal of the axis movement
    commands: list of command returned by this button. If set, do not check
      for moves associated with this mapping
    direction: Direction of movement when pressing the button. Ignored for axis
      commands
    movement_axis: direction the CNC head moves when this button or axis is 
      triggered
    repeat_if_pressed: whether the button should trigger while pressed or only
      once when pressed, requiring it to be lifted. Use it for commands that might
      be dangerous or undesired to trigger multiple times, like homing.
    magnitude_axis: Axis associated with this command that translate axis inputs
      into CNC head movement. For both buttons and axis this can be a separate
      axis for the intensity, while the button or axis determines the direction
      of the movement. For axis, you can set both axis to the same joystick
      axis to make it a "force sensitive axis"
  """ 
  button: str = ''
  axis: MagnitudeAxis = None
  reverse_axis_direction: bool = False
  commands: Tuple[Command] = ()
  direction: Direction = None
  movement_axis: MovementAxis = None
  repeat_if_pressed: bool = False
  magnitude_axis: MagnitudeAxis = None

  def axis_direction_multiplier(self) -> int:
    """Returns the axis direction multiplier based on whether the movement is inverted or not.""" 
    return -1 if self.reverse_axis_direction else 1
