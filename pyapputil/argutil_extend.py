#!/usr/bin/env python2.7
"""
This module is an extension of argparse that integrates with appconfig.
Default values for command line arguments can be automatically set from
appconfig, and the help display for the argument will show the default
value as well as the ENV variable that can be used to override it.

from pyapputil.argutil import ArgumentParser

parser = ArgumentParser(description="This is my cool app")
parser.add_argument("-m", --my-arg", required=True, metavar="THING" use_appconfig=True, help="the argument my app needs")
args = parser.parse_args()

The new keyword argument use_appconfig means that the default value for the arg will be set form appconfig, and the
help text for that arg will show that default and include the name of the ENBV variable that can be used to set it.

usage: myscript.py [-h] -m THING

This is my cool app

Options:
  -m THING, --my-arg THING  the argument my app needs (default: foo) (env: MYAPP_MY_ARG)
"""

# Import all of argparse so this module can be used as a direct replacement for it
#pylint: disable=wildcard-import
#pylint: disable=unused-wildcard-import
from argparse import *
#pylint: enable=wildcard-import
#pylint: enable=unused-wildcard-import
import argparse as _argparse

import os as _os
from .appconfig import appconfig as _appconfig
from .shellutil import GetConsoleSize

STD_EPILOG = ("Options with an env: in the description can be specified with the corresponding environment variable "
              "instead of the command line argument. If both the env variable are set and the command line argument "
                 "specified, the command line will take precedence.")


def GetFirstLine(text):
    """
    Get the first line or first sentence of text, whichever is shorter.

    Args:
        text:   the text to search

    Returns:
        A string containing the first line of text
    """
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        break
    for sentence in text.split("\n"):
        sentence = sentence.strip()
        if not sentence:
            continue
        break
    if line and len(line) < sentence:
        return line
    if sentence:
        return sentence
    return ""

#pylint: disable=function-redefined
class HelpFormatter(_argparse.HelpFormatter):
    """Identical to argparse HelpFormatter except that the width of the help text will scale to the terminal"""

    FALLBACK_WIDTH=120

    def __init__(self, prog, indent_increment=2, max_help_position=24, width=None):
        super(HelpFormatter, self).__init__(prog,
                                            indent_increment=indent_increment,
                                            max_help_position=max_help_position,
                                            width=width)
        if width is None:
            self._width = int(_os.environ.get("COLUMNS", min(HelpFormatter.FALLBACK_WIDTH, GetConsoleSize())))

class ArgumentDefaultsHelpFormatter(_argparse.ArgumentDefaultsHelpFormatter):
    """Add to the end of the help text the ENV variable that can be used to set the default for the arg"""

    def _get_help_string(self, action):
        help_string = super(ArgumentDefaultsHelpFormatter, self)._get_help_string(action)

        # Add environment variable override to help string
        if getattr(action, "use_appconfig", False):
            help_str += " (env: {})".format(_appconfig["ENV_CONFIG_PREFIX"] + action.dest.upper())

        return help_str

class Action(_argparse.Action):
    """Add a new keyword argument to the Action class to integrate with appconfig"""

    def __init__(self,
                 option_strings,
                 dest,
                 nargs=None,
                 const=None,
                 default=None,
                 type=None,
                 choices=None, 
                 required=False,
                 help=None,
                 metavar=None,
                 use_appconfig=False):
        super(Action, self).__init__(option_strings=option_strings,
                                     dest=dest,
                                     nargs=nargs,
                                     const=const,
                                     default=default,
                                     type=type,
                                     choices=choices,
                                     required=required,
                                     help=help,
                                     metavar=metavar)
        self.use_appconfig = use_appconfig
        if self.use_appconfig:
            self.default = _appconfig.get(self.dest, None)

class _StoreAction(_argparse._StoreAction, Action):
    """Add a new keyword argument to integrate with appconfig"""

    def __init__(self,
                 option_strings,
                 dest,
                 nargs=None,
                 const=None,
                 default=None,
                 type=None,
                 choices=None, 
                 required=False,
                 help=None,
                 metavar=None,
                 use_appconfig=False):
        super(_StoreAction, self).__init__(option_strings=option_strings,
                                     dest=dest,
                                     nargs=nargs,
                                     const=const,
                                     default=default,
                                     type=type,
                                     choices=choices,
                                     required=required,
                                     help=help,
                                     metavar=metavar)
        self.use_appconfig = use_appconfig
        if self.use_appconfig:
            self.default = _appconfig.get(self.dest, None)

class _ActionsContainer(_argparse._ActionsContainer):
    
    def __init__(self,
                 description,
                 prefix_chars,
                 argument_default, 
                 conflict_handler):
        super(_ActionsContainer, self).__init__(description,
                                                prefix_chars,
                                                argument_default,
                                                conflict_handler)

        print "Registering store={}".format(_StoreAction)
        self.register('action', 'list', _ListAction)

class ArgumentParser(_argparse.ArgumentParser):

    def __init__(self,
                 prog=None,
                 usage=None,
                 description=None,
                 epilog=STD_EPILOG,
                 version=None,
                 parents=None, 
                 formatter_class=HelpFormatter,
                 prefix_chars='-',
                 fromfile_prefix_chars=None,
                 argument_default=None,
                 conflict_handler='error',
                 add_help=True,
                 add_debug=True):
        parents = parents or []
        super(ArgumentParser, self).__init__(prog=prog,
                                             usage=usage,
                                             description=description,
                                             epilog=epilog,
                                             version=version,
                                             parents=parents,
                                             formatter_class=formatter_class,
                                             prefix_chars=prefix_chars,
                                             fromfile_prefix_chars=fromfile_prefix_chars,
                                             argument_default=argument_default,
                                             conflict_handler=conflict_handler,
                                             add_help=add_help)

        default_prefix = '-' if '-' in prefix_chars else prefix_chars[0]

        # Add debug option
        if add_debug:
            self.add_argument(default_prefix+"d",
                              default_prefix*2+"debug",
                              action="count",
                              default=0,
                              help="display more verbose messages")

    def parse_args_to_dict(self, args=None, namespace=None, allowExtraArgs=False, extraArgsKey="extra_args"):
        if allowExtraArgs:
            parsed, extras = self.parse_known_args(args=args, namespace=namespace)
            if hasattr(parsed, extraArgsKey):
                raise ArgumentError("Conflicting extra args key '{}'".format(extraArgsKey))
            if extras:
                setattr(parsed, extraArgsKey, extras)
        else:
            parsed = self.parse_args(args=args, namespace=namespace)
        return { key : value for key, value in vars(parsed).iteritems() if value != None }

#pylint: enable=function-redefined



class _ListAction(Action):
    """argparse action class for a comma delimited list of strings"""

    def __call__(self, parser, namespace, values, option_string):
        # Split on any number of ',' or whitespace and remove empty entries
        a = [i for i in _re.split(r"[,\s]+", values) if i]
        setattr(namespace, self.dest, a)

