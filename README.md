# cncjs-py-pendant
CNCjs pendant to control CNC machines using joysticks. Written in Python.

# Compatibility
The following combinations have been tested and verified to work

| Controller device | CNC      | Joystick |
|-------------------|----------|----------|
| Raspberry Pi      | Shapeoko | PS3      |

# Installation

The pendant requires Python 3.7+ to work, and has been tested on Linux only. Make sure this is installed in your controller device. You also need a joystick to use as a pendant, so far only PS3 joysticks have been tested. Make sure the Joystick can connect to your controller.

When these are done, clone the repository using your favorite `git clone` command.

If you are using poetry, you can install the dependencies by running inside the repository folder

```
$ poetry update
```

Otherwise, you need to install the library dependencies manually:

```
pip3 install PyJWT python-socketio[asyncio_client]==4.6.2
```

# Running the pendant

You can run the pendant by executing the `pendant.py` file inside the repository. A config file will be created the first time the script is executed.

# Running at startup

We recommend using crontab to start the script after reboot. If you are using the `pi` user of a Raspberry Pi, just run `crontab -e` and add the following line to it. 

```
@reboot /home/pi/cncjs-py-pendant/pendant.py >>/home/pi/pendant.log 2>&1
```

Any other method like creating a daemon and starting it also work. Just make sure whichever user is running it has access to the joystick files, in Linux these are `/dev/input/js*`

# Licenses
Joystick control code based on piborg/Gamepad (http://github.com/piborg/Gamepad)
