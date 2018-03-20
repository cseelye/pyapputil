#!/usr/bin/env python2.7
"""
This module presents configuration values combined from defaults, user config,
and environment variables

from pyapputil.appconfig import appconfig
appconfig["some_value"]

The default values are stored in "appdefaults.py" in the application's
root directory. This is a pure python file that gets imported, so you it can be
anything from a list of variables/values to any arbitrary code you need to set
up your default values.

The user can optionally provide a "userconfig.yml" file to override
the defaults (the name of this file can be changed in appdefaults.py). This is a
text YAML file that gets loaded after appdefaults.py, and any values in this
file will override values from appdefaults.py. If the user wants to override a
default named some_var, they can simply add an entry to userconfig.yml like this:
some_value: 123

The user can optionally export environment variables to override the defaults or
user config. The prefix used for environment variables is set in appdefaults.py.
If the prefix is set to  "MYAPP_" and the user wants to override a config var
named some_value, they could override it with an environment variable like this:
    export MYAPP_SOME_VALUE=123
"""

import os as _os
import runpy as _runpy
import sys as _sys
import yaml as _yaml


DEFAULTS_FILENAME = "appdefaults.py"                # The name of the file containing all of the app defaults
PREFIX_VAR_NAME = "ENV_CONFIG_PREFIX"               # The name of the variable in the app defaults or userconfig file that sets the prefix to use when looking for environment variables
USER_CONFIG_VAR_NAME = "USER_CONFIG_FILE"           # The name of the variable in the app defaults file that sets the name of the user config file
USER_CONFIG_FILENAME_DEFAULT = "userconfig.yml"     # The name of the file containing the user config, if it is not specified in the app defaults file

def AddDefault(varName, defaultValue):
    """
    Add a default value to the config if it is not already present.
    Using the appdefaults.py file should be preferred over this.

    Args:
        varName:        name of the default to add (str)
        defaultValue:   value to default to
    """
    if varName not in appconfig:
        appconfig[varName] = defaultValue

# Setup base paths
if "pytest" in _sys.modules:
    _sys.argv[0] = ''
if not _sys.argv[0]:
    APP_PATH = _os.path.realpath(_os.getcwd())
else:
    APP_PATH = _os.path.dirname(_os.path.realpath(_sys.argv[0]))

# Try to find a defaults file. Start in APP_PATH and search upward
modifier = ""
while True:
    file_path = _os.path.abspath(APP_PATH + modifier)
    DEFAULTS_FILEPATH = _os.path.join(file_path, DEFAULTS_FILENAME)
    if _os.path.exists(DEFAULTS_FILEPATH):
        break
    if file_path == "/":
        break
    modifier += "/.."

# Import the default values from the app defaults file
appconfig = {}
if _os.path.exists(DEFAULTS_FILEPATH):
    appconfig = _runpy.run_path(DEFAULTS_FILEPATH)
    for _key in appconfig.keys():
        if _key.startswith("_"):
            del appconfig[_key]

# Get the name of the config file and its full path
USER_CONFIG_FILENAME = appconfig.get(USER_CONFIG_VAR_NAME, USER_CONFIG_FILENAME_DEFAULT)
USER_CONFIG_FILEPATH = _os.path.join(APP_PATH, USER_CONFIG_FILENAME)

# Import any values set in the user config file
if _os.path.exists(USER_CONFIG_FILEPATH):
    with open(USER_CONFIG_FILEPATH, "r") as userfile:
        user_config = _yaml.load(userfile)
    appconfig.update(user_config)

# Import any values set in the environment
if PREFIX_VAR_NAME not in appconfig:
    appconfig[PREFIX_VAR_NAME] = "PYAPP_"
for _varname in appconfig.keys():
    if _varname == PREFIX_VAR_NAME:
        continue
    _env_var_name = "{}{}".format(appconfig[PREFIX_VAR_NAME], _varname.upper())
    if _env_var_name in _os.environ:
        appconfig[_varname] = _os.environ[_env_var_name]

