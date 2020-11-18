#!/usr/bin/env python
"""Helper for creating simple command line applications"""

import atexit
from datetime import timedelta
import inspect
import os
from signal import signal, SIGPIPE, SIG_DFL, SIGINT
import sys
import threading
import time
import traceback

from . import appconfig, logutil, threadutil
from .exceptutil import InvalidArgumentError

app_excepthook_threadsafe_locker = threading.RLock()
def SetExcepthook(handler):
    """
    Set a global uncaught exception handler. This must be called from the main thread before creating any other threads

    Args:
        handler:    the function to call when an unhandled exception is thrown
    """

    # Wrapper to make sure the handler is threadsafe
    def wrapper(extype, ex, tb):
        """threadsafe wrapper"""
        with app_excepthook_threadsafe_locker:
            handler(extype, ex, tb)
    sys.excepthook = wrapper

    # Machinations to work around threading module not honoring sys.excepthook
    # This will make sure sys.excepthook is called for any threads that have uncaught exceptions
    #   Replace Thread.__init__ with our own that sets up our wrapped Thread.run
    #   Wrap Thread.run with an exception handler that calls the standard sys.excepthook
    thread_init = threading.Thread.__init__
    def init(self, *args, **kwargs):
        """replacement init function"""
        thread_init(self, *args, **kwargs)
        thread_run = self.run
        def hooked_run(*args, **kw):
            """Replacement function for thread.run"""
            #pylint: disable=bare-except
            try:
                thread_run(*args, **kw)
            except (KeyboardInterrupt, SystemExit):
                # Let these exceptions bubble up in the current thread
                raise
            except:
                # Catch any other exception and call the global excepthook
                sys.excepthook(*sys.exc_info())
            #pylint: enable=bare-except
        self.run = hooked_run
    threading.Thread.__init__ = init

class PythonApp(object):
    """Simple app helper"""

    def __init__(self, main_func, timer=True, require_superuser=False, custom_log_config=None):
        """
        Initialize the application

        Args:
            main_func:          the main entry point to the app. This must a callable, and can either return an integer, which
                                will be used as the exit code, or the return value will be evaluated in boolean context and be
                                converted to an exit code of 0 or 1.  If mainFunc throws an exception, it will be converted to an
                                exit code of 1
            timer:              show the run time of the script when it ends
            require_superuser:  if the app should require superuser privileges before running
            custom_log_config:  a log config dictionary to use when creating the logger for the app
        """
        if not callable(main_func):
            raise TypeError("main_func must be callable")
        self.main = main_func
        self.require_superuser = require_superuser
        self.name = os.path.basename(inspect.stack()[-1][1])
        self.startTime = time.time()

        # Make sure we are a super user.  This should be done before we set up logging because we might need privilege elevation
        # to create the log file, write to syslog, etc
        if self.require_superuser:
            if os.geteuid() != 0:
                sys.stderr.write('Please execute with sudo or as root\n')
                sys.exit(1)

        # Set up logging
        if custom_log_config:
            self.log = logutil.GetLogger(logConfig=custom_log_config)
        else:
            self.log = logutil.GetLogger()

        def UnhandledException(extype, ex, tb):
            """Create a global handler to log any uncaught exceptions from any threads"""
            if extype not in [KeyboardInterrupt, SystemExit]:
                self.log.error("Unexpected exception in thread %s: %s %s\n%s", threading.currentThread().name, extype.__name__, ex, "".join(traceback.format_tb(tb)))
                if threadutil.IsMainProcess() and threadutil.IsMainThread():
                    self.Abort()
                    sys.exit(1)
                else:
                    raise ex
        SetExcepthook(UnhandledException)

        # Create a function to run at exit that will show the run time of the app
        def RunTimer():
            """timer function"""
            delta = timedelta(seconds=time.time() - self.startTime)
            days = delta.days
            hours = 0
            minutes = 0
            seconds = delta.seconds
            if seconds >= 60:
                d,r = divmod(seconds, 60)
                minutes = d
                seconds = r
            if minutes >= 60:
                d,r = divmod(minutes, 60)
                hours = d
                minutes = r
            time_str = "%02d:%02d" % (minutes, seconds)
            if (hours > 0):
                time_str = "%02d:%02d:%02d" % (hours, minutes, seconds)
            if (days > 0):
                time_str = "%d-%02d:%02d:%02d" % (days, hours, minutes, seconds)
            self.log.time("%s total run time %s", self.name, time_str)
        if timer:
            atexit.register(RunTimer)

        # Turn off python's SIGPIPE handling so we get the default signal behavior instead of python exceptions
        # Normally python will catch SIGPIPE and generate an IOError exception instead.  This restores the default SIGPIPE
        # behavior of terminating the application, and allows SIGPIPE to propagate to any subprocesses this app launches
        signal(SIGPIPE, SIG_DFL)

        # Handle signal
        signal(SIGINT, self.Signal)

    def Signal(self, *_):
        self.log.warning("Aborted by user")
        self.Abort()

    def Abort(self):
        """Cleanup and shut down"""
        threadutil.ShutdownGlobalPool()
        sys.exit(1)

    def Run(self, *args, **kwargs):
        """Run the app main function"""

        # Figure out if we got an argparse namespace and convert it to a dict instead
        user_args = {}
        if kwargs:
            user_args = kwargs
        elif args:
            user_args = vars(args[0])

        # Setup debug logging as requested
        debug = user_args.pop("debug", 0)
        self.log.TruncateMessages(True)
        if debug:
            self.log.ShowDebug(level=debug)
            if debug >= 3:
                self.log.TruncateMessages(False)
        else:
            self.log.HideDebug()

        if user_args.get("output_format", None):
            self.log.Silence()

        self.log.debug("Starting %s", sys.argv)
        self.startTime = time.time()

        # Re-import config if the command line option was used to change the user config file
        user_config_file = user_args.pop("user_config", None)
        if user_config_file:
            appconfig.set_user_config_file(user_config_file)

        # Run the main function
        try:
            result = self.main(**user_args)
        except InvalidArgumentError as e:
            self.log.error(e)
            self.Abort()
            sys.exit(1)
        except KeyboardInterrupt:
            self.log.warning("Aborted by user")
            self.Abort()
            sys.exit(1)

        # Determine exit code based on return value. We explicitly use type() vs isinstance() because bool is a child of int
        if type(result) == int:
            sys.exit(result)
        elif result:
            sys.exit(0)
        else:
            sys.exit(1)
