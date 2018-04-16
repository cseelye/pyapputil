=========
pyapputil
=========
Python module to simplify building CLI applications. Includes simple helpers for
building an app, validating arguments, configfiles/default values, logging,
global exception catching, privilege escalation, signal handling,
time/timezones, multithreading...

Currently python 2.7 compatible, py3 in progress...

Documentation in progress...

appframework
============

appconfig
=========

This module presents configuration values combined from defaults, user config,
and environment variables.

To get a configuration variable named ``some_value``:

.. code:: python

    from pyapputil.appconfig import appconfig
    appconfig["some_value"]

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

.. code::

    export MYAPP_SOME_VALUE=123

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

