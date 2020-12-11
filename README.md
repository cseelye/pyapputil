# pyapputil

[![](https://badge.fury.io/py/pyapputil.svg)](https://badge.fury.io/py/pyapputil)

Python module to simplify building CLI applications. Includes simple helpers for
building an app, validating arguments, configfiles/default values, logging,
global exception catching, privilege escalation, signal handling,
time/timezones, multithreading...

Python 2 and 3 compatible.

appframework
============

This wrapper takes care of signal handling, uncaught exceptions, exit codes, and a host of other
things so you don't have to. It integrates with appconfig, argutil to provide argument parsing with config file support,
overidable default values, and user friendly help, plus typeutil to provide easy, strong argument
validation while maintaining duck typing.

```python
from pyapputil.appframework import PythonApp
from pyapputil.appconfig import appconfig
from pyapputil.argutil import ArgumentParser
from pyapputil.typeutil import ValidateAndDefault, OptionalValueType, StrType

@ValidateAndDefault({
    # "arg_name" : (arg_type, arg_default)
    "arg1" : (OptionalValueType(StrType(allowEmpty=False)), appconfig["arg1"]),
    "arg2" : (float, 0),
})
def main(arg1, arg2):
    pass

if __name__ == '__main__':
    parser = ArgumentParser(description="My cool commandline app")
    parser.add_argument("-a", "--arg1", type=StrType(allowEmpty=False), default=appconfig["arg1"], help="the first argument")
    parser.add_argument("-b", "--arg2", type=float, help="the second argument")
    args = parser.parse_args_to_dict()

    app = PythonApp(main, args)
    app.Run(**args)
```

appconfig
=========

This module presents configuration values combined from defaults, user config,
and environment variables.

To get a configuration variable named ``some_value``:

```python
    from pyapputil.appconfig import appconfig
    appconfig["some_value"]
```
The default values are stored in ``appdefaults.py`` in the application's
root directory. This is a pure python file that gets imported, so you it can be
anything from a list of variables/values to any arbitrary code you need to set
up your default values.

The user can optionally provide a ``userconfig.yml`` file to override
the defaults. This is a text YAML file that gets loaded after appdefaults.py,
and any values in this file will override values from appdefautls.
If the user wants to override a default named some_var, they can simply add an
entry to userconfig.yml like this:
some_value: 123

The user can optionally export environment variables to override the defaults or
user config. The prefix used for environment variables is set in appdefaults.py.
If the prefix is set to  "MYAPP\_" and the user wan't to override a config var
named some_value, they could override it with an environment varible like this:


```
    export MYAPP_SOME_VALUE=123
```

argutil
=======
This is a forked version of python's argparse, that is integrated with appconfig
so that command line arguments can automatically set default values from
appconfig, and the help display will show the default value as well as the name
of the ENV variable that can be used to override it.

typeutil
========
Collection of type validators that can be used with argparse/argutil, and
decorators and util functions for using the same validators on functions

exceptutil
==========

logutil
=======

shellutil
=========

threadutil
==========
