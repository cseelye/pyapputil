#!/usr/bin/env python
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
the defaults (the default name of this file can be changed in appdefaults.py,
and it can be changed at run time by calling set_user_config_file). This is a text
YAML file that gets loaded after appdefaults.py, and any values in this file will
override values from appdefaults.py. If the user wants to override a default
named some_value, they can simply add an entry to userconfig.yml like this:
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
from .logutil import GetLogger

DEFAULTS_FILENAME = "appdefaults.py"                # The name of the file containing all of the app defaults
PREFIX_VAR_NAME = "ENV_CONFIG_PREFIX"               # The name of the variable in the app defaults or userconfig file that sets the prefix to use when looking for environment variables
PREFIX_DEFAULT = "PYAPP_"
USER_CONFIG_VAR_NAME = "USER_CONFIG"      # The name of the variable in the app defaults file that sets the name of the user config file
USER_CONFIG_DEFAULT = "userconfig.yml"         # The name of the file containing the user config, if it is not specified in the app defaults file

class ConfigValues(dict):
    """Dict-like object that contains configuration values merged from defaults,
       user config files and environment variables"""

    def import_defaults(self):
        """Load the default values for config values"""
        # Try to find a defaults file. Start in APP_PATH and search upward
        defaults_filepath = DEFAULTS_FILENAME
        modifier = ""
        while True:
            file_path = _os.path.abspath(APP_PATH + modifier)
            defaults_filepath = _os.path.join(file_path, defaults_filepath)
            if _os.path.exists(defaults_filepath):
                break
            if file_path == "/":
                break
            modifier += "/.."

        self.clear()
        # Import the default values from the app defaults file
        if _os.path.exists(defaults_filepath):
            self.update(_runpy.run_path(defaults_filepath))
            for _key in self.keys():
                if _key.startswith("_"):
                    del self[_key]

        # Make sure critical values are set
        if PREFIX_VAR_NAME not in self:
            self[PREFIX_VAR_NAME] = PREFIX_DEFAULT
        if USER_CONFIG_VAR_NAME not in self:
            self[USER_CONFIG_VAR_NAME] = USER_CONFIG_DEFAULT

    def import_user_config(self, user_config_file=None):
        """Load the user configured values from config file"""
        # Import any values set in the user config file
        config_file = user_config_file or self.get(USER_CONFIG_VAR_NAME, USER_CONFIG_DEFAULT)
        if not _os.path.exists(config_file) and not _os.path.isabs(config_file):
            config_file = _os.path.join(APP_PATH, config_file)
        self[USER_CONFIG_VAR_NAME] = config_file
        self._load(config_file)

    def import_environment(self):
        """Load the user configured values from the environment"""
        # Import any values set in the environment
        for _varname in self.keys():
            if _varname == PREFIX_VAR_NAME:
                continue
            _env_var_name = "{}{}".format(self[PREFIX_VAR_NAME], _varname.upper())
            if _env_var_name in _os.environ:
                self[_varname] = _os.environ[_env_var_name]

    def _load(self, user_config_file):
        """Internal function to load from a YAML config file"""
        GetLogger().debug2("Loading config file {}".format(user_config_file))
        blacklisted_vars = (USER_CONFIG_VAR_NAME)
        self[USER_CONFIG_VAR_NAME] = user_config_file
        if _os.path.exists(user_config_file):
            with open(user_config_file, "r") as userfile:
                user_config = _yaml.load(userfile)
            for keyname in blacklisted_vars:
                user_config.pop(keyname, None)
            if user_config:
                self.update(user_config)

def add_default(var_name, default_value):
    """
    Add a default value to the config if it is not already present.
    Using the appdefaults.py file should be preferred over this.

    Args:
        var_name:        name of the default to add (str)
        default_value:   value to default to
    """
    if var_name not in appconfig:
        appconfig[var_name] = default_value

def set_user_config_file(config_file_path):
    """
    Set the path to the user config file to use and reload values

    Args:
        config_file_path:   the path to the config file
    """
    appconfig.import_user_config(config_file_path)


# Setup base paths
if "pytest" in _sys.modules:
    _sys.argv[0] = ''
if not _sys.argv[0]:
    APP_PATH = _os.path.realpath(_os.getcwd())
else:
    APP_PATH = _os.path.dirname(_os.path.realpath(_sys.argv[0]))

appconfig = ConfigValues()
appconfig.import_defaults()
user_config_filename = _os.environ.get(appconfig[PREFIX_VAR_NAME] + USER_CONFIG_VAR_NAME.upper(), appconfig[USER_CONFIG_VAR_NAME])
appconfig.import_user_config(user_config_filename)
appconfig.import_environment()
