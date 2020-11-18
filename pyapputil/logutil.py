#!/usr/bin/env python2.7
"""Ready to use logging"""

#pylint: disable=protected-access
from __future__ import print_function
from past.builtins import basestring as _basestring
import functools
import logging
import logging.handlers
import multiprocessing
import os
import platform
import re
import socket
import sys
import threading

class CustomLogLevels(object):
    """ Custom log levels that map to specific formatted and colorized output"""
    PASS, FAIL, RAW, TIME, BANNER, STEP, GRAY, WHITE, YELLOW, RED, GREEN, BLUE, PINK, FAKE, TEST, BLANK = range(101, 117)
    DEBUG2 = 9

class ColorizingStreamHandler(logging.StreamHandler):
    """ Cross-platform colorizor for console logging, multiprocessing safe
    Based on http://plumberjack.blogspot.com/2010/12/colorizing-logging-output-in-terminals.html
    """

    def __init__(self, stream=None):
        logging.StreamHandler.__init__(self, stream)
        self.lock = multiprocessing.RLock()

    # Map of color names to indices
    colorMap = {
        'black': 0,
        'red': 1,
        'green': 2,
        'yellow': 3,
        'blue': 4,
        'magenta': 5,
        'cyan': 6,
        'white': 7,
    }

    # Map of log level to color (background, foreground, bold/intense)
    levelMap = {
        CustomLogLevels.DEBUG2: ('black', 'white', False),
        logging.DEBUG: ('black', 'white', False),
        logging.INFO: ('black', 'white', True),
        logging.WARNING: ('black', 'yellow', True),
        logging.ERROR: ('black', 'red', True),
        logging.CRITICAL: ('red', 'white', True),
        CustomLogLevels.PASS: ('black', 'green', True),
        CustomLogLevels.FAIL: ('red', 'white', True),
        CustomLogLevels.RAW: ('black', 'white', True),
        CustomLogLevels.TIME: ('black', 'cyan', False),
        CustomLogLevels.BANNER: ('black', 'magenta', True),
        CustomLogLevels.STEP: ('black', 'cyan', False),
        CustomLogLevels.WHITE: ('black', 'white', True),
        CustomLogLevels.YELLOW: ('black', 'yellow', True),
        CustomLogLevels.RED: ('black', 'red', True),
        CustomLogLevels.GREEN: ('black', 'green', True),
        CustomLogLevels.BLUE: ('black', 'cyan', True),
        CustomLogLevels.PINK: ('black', 'magenta', True),
        CustomLogLevels.FAKE: ('black', 'cyan', False),
        CustomLogLevels.TEST: ('black', 'cyan', False),
        CustomLogLevels.BLANK: ('black', 'white', True),
    }
    csi = '\x1b['
    reset = '\x1b[0m'

    def isTTY(self):
        isatty = getattr(self.stream, 'isatty', None)
        return isatty and self.stream.isatty()

    def emit(self, record):
        #pylint: disable=bare-except
        try:
            message = self.format(record)
            with self.lock:
                stream = self.stream
                if not self.isTTY():
                    stream.write(message)
                else:
                    self.output_colorized(message)
                stream.write(getattr(self, 'terminator', '\n'))
                self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)
        #pylint: enable=bare-except

    # This if/else defines the output_colorized function differently based on OS
    if os.name != 'nt':
        def output_colorized(self, message):
            """colorize a message on unix"""
            self.stream.write(message)
    else:
        ansiEscapes = re.compile(r'\x1b\[((?:\d+)(?:;(?:\d+))*)m')

        winColorMap = {
            0: 0x00,    # black
            1: 0x04,    # red
            2: 0x02,    # green
            3: 0x06,    # yellow
            4: 0x01,    # blue
            5: 0x05,    # magenta
            6: 0x03,    # cyan
            7: 0x07,    # white
        }

        def output_colorized(self, message):
            """colorize a message on windows"""
            #pylint: disable=import-error
            import win32console
            #pylint: enable=import-error
            fn = getattr(self.stream, 'fileno', None)
            if fn is not None:
                #pylint: disable=not-callable
                fd = fn()
                #pylint: enable=not-callable
                if fd in (1, 2): # stdout or stderr
                    c = win32console.GetStdHandle(-10 - fd)
            parts = self.ansiEscapes.split(message)
            while parts:
                text = parts.pop(0)
                if text:
                    self.stream.write(text)
                if parts:
                    params = parts.pop(0)
                    if c is not None:
                        params = [int(p) for p in params.split(';')]
                        color = 0
                        for p in params:
                            if 40 <= p <= 47:
                                color |= self.winColorMap[p - 40] << 4
                            elif 30 <= p <= 37:
                                color |= self.winColorMap[p - 30]
                            elif p == 1:
                                color |= 0x08 # Foreground intensity on
                            elif p == 0: # Reset to default color
                                color = 0x07
                            else:
                                pass # Unknown color command - ignore it

                        c.SetConsoleTextAttribute(color)

    def colorize(self, message, record):
        """Add console color codes to a message according to the level map"""
        if record.levelno in self.levelMap:
            bg, fg, bold = self.levelMap[record.levelno]
            params = []
            if bg in self.colorMap:
                params.append(str(self.colorMap[bg] + 40))
            if fg in self.colorMap:
                params.append(str(self.colorMap[fg] + 30))
            if bold:
                params.append('1')
            if params:
                message = ''.join((self.csi, ';'.join(params),
                                   'm', message, self.reset))
        return message

    def format(self, record):
        message = logging.StreamHandler.format(self, record)
        if self.isTTY():
            message = self.colorize(message, record)
        return message

class MultiprocessingFileHandler(logging.FileHandler):
    """Multiprocessing-safe version of FileHandler"""

    def __init__(self, filename, mode='a', encoding=None, delay=False):
        super(MultiprocessingFileHandler, self).__init__(filename, mode, encoding, delay)
        self.lock = multiprocessing.Lock()

    def emit(self, record):
        with self.lock:
            super(MultiprocessingFileHandler, self).emit(record)

class MultiFormatter(logging.Formatter):
    """ Custom log statement formatter with different formats for different levels"""

    __defaultFormat = '%(asctime)s: %(levelname)-7s %(message)s'

    def __init__(self, fmt=__defaultFormat):
        self.baseFormat = fmt
        self.rawFormat = '%(message)s'
        self.truncateLongMessages = True
        logging.Formatter.__init__(self, fmt)

    def format(self, record):
        # Trim any trailing whitespace
        if isinstance(record.msg, _basestring):
            record.msg = record.msg.rstrip()
            if not record.msg:
                record.msg = "  <empty msg>"
        # Select the format to use based on level
        if record.levelno == CustomLogLevels.RAW or record.levelno == CustomLogLevels.TIME:
            self._fmt = self.rawFormat

        elif record.levelno == CustomLogLevels.BANNER:
            # Set the banner format based on the current width of the shell
            try:
                _, columns = os.popen('stty size 2>/dev/null', 'r').read().split()
                bannerWidth = int(columns)
            except ValueError:
                bannerWidth = 80
            bannerFormat = '='*bannerWidth + '\n%(message)s\n' + '='*bannerWidth

            # Center the message and make sure it fits within the banner
            modified = []
            for line in record.msg.split('\n'):
                if len(line) > bannerWidth:
                    pieces = self.__SplitMessage(line, bannerWidth)
                else:
                    pieces = [line]
                for piece in pieces:
                    modified.append(piece.center(bannerWidth, ' '))
            record.msg = '\n'.join(modified)
            self._fmt = bannerFormat

        elif record.levelno == CustomLogLevels.STEP:
            record.msg = '>>> ' + record.msg

        elif record.levelno == CustomLogLevels.BLANK:
            self._fmt = self.rawFormat
            record.msg = ""

        else:
            proc = multiprocessing.current_process()
            thr = threading.current_thread()

            # # Add process name/PID and thread name to log message
            # if thr.name != "MainThread":
            #     record.msg = "{} {}".format(thr.name, record.msg)
            # if proc.name != "MainProcess":
            #     record.msg = "{}.{} {}".format(proc.name, os.getpid(), record.msg)

            prefix = GetThreadLogPrefix()
            if prefix and  not record.msg.startswith(prefix):
                record.msg = "{}{}".format(prefix, record.msg)

            # Indent messages if we are a child-thread/process
            if proc.daemon or proc.name != "MainProcess" or thr.daemon or thr.name != "MainThread":
                record.msg = "  " + record.msg

            self._fmt = self.baseFormat

        # Cut debug and debug2 messages to 1024 characters
        if self.truncateLongMessages and record.levelno in (logging.DEBUG, CustomLogLevels.DEBUG2):
            if len(record.msg) > 1024:
                record.msg = record.msg[:1000] + " ...<truncated>"

        # Format the record
        result = logging.Formatter.format(self, record)

        # Restore the formatter
        self._fmt = self.baseFormat

        return result

    def __SplitMessage(self, message, length=1024):
        """Split a message into lines no more than 'length' long"""
        lines = []
        remain = str(message)
        while len(remain) > length:
            index = remain.rfind(' ', 0, length)
            if index <= 0:
                index = length - 1
            lines.append(remain[:index])
            remain = remain[index:]
        lines.append(remain)
        return lines

class FormatOptions(object):
    """Enumerated list of formatting options"""
    NONE, TIME, LEVEL = (2**x for x in range(3))

    # Map format enums to format strings
    formatMap = {
        TIME : '%(asctime)s: ',
        LEVEL : '%(levelname)-7s ',
    }

class PrintLogger(object):
    """Logger class that can be passed to functions that want a valid log object
    Every function call to an instance of this class is routed to the printer function
    For simple debugging, mocking, etc."""

    #pylint: disable=unused-argument
    def printer(self, *args, **kwargs):
        if args:
            print(args[0])
    #pylint: enable=unused-argument
    def __getattr__(self, name):
        return self.printer

class NullLogger(object):
    """Logger class that can be passed to functions that want a valid log object
    Every function call to an instance of this class is routed to the nothing function
    For simple debugging, mocking, etc."""

    def nothing(self, *args, **kwargs):
        pass
    def __getattr__(self, name):
        return self.nothing

def SetThreadLogPrefix(prefix):
    """
    Set a hint to the logger to add a prefix to log messages from this thread

    Args:
        prefix:     the prefix to add to log messages
    """
    threading.current_thread().name = "LOGPREFIX:{}".format(prefix)

def GetThreadLogPrefix():
    """
    Get the hinted log prefix

    Returns:
        A string prefix (str)
    """
    thr = threading.current_thread()
    if thr.name.startswith("LOGPREFIX"):
        pieces = thr.name.split(":")
        if len(pieces) >= 2:
            return "  {}: ".format(pieces[1])

def logargs(func):
    """Decorator to log the arguments of a function"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        log = GetLogger()
        msg="{}(".format(func.__name__)
        if args:
            msg += ", ".join([str(a) for a in args])
        if args and kwargs:
            msg += ", "
        if kwargs:
            msg += ", ".join(["{}={}".format(name, val) for name, val in kwargs.items()])
        msg += ")"
        log.debug2(msg)
        return func(*args, **kwargs)

    setattr(wrapper, "__innerfunc__", func)
    return wrapper

def GetDefaultConfig():
    """ Get a dictionary representing the default logging configuration

    Returns:
        A dictionary of config options
    """
    return {
        'enableConsole' : True,             # Send log messages to the console
        'consoleColor' : True,              # Colorize console log messages
        'consoleLevel' : logging.INFO,      # Minimum level to show on the console
        'prefix' : FormatOptions.TIME | FormatOptions.LEVEL,      # Prefix to show before the log message.  Multiple options can be combined with |
        'enableSyslog' : True,              # Send log messages to local syslog
        'syslogFacility' : 1,               # syslog facility to log to [1 = user]
        'enableFile' : False,               # Send log messages to a file
        'logFile' : None,                   # The file to log to. Using None will generate a file name based on the logger name
    }

def GetLogger(name="myapp", logConfig=None):
    """Get a logger instance with the specified configuration

    Arguments:
        name:        The name of this logger
        logConfig:   None to use the defaults, or a dictionary of config options to override

    Returns:
        A ready to use logging.Logger object
    """

    # Build a complete config object by combining the user supplied options with the defaults
    defaultConfig = GetDefaultConfig()
    if not logConfig:
        logConfig = defaultConfig
    else:
        for key, value in defaultConfig.items():
            if key not in list(logConfig.keys()):
                logConfig[key] = value

    logging.raiseExceptions = False
    logging._srcfile = None
    logging.logThreads = 1
    logging.logProcesses = 1
    mylog = logging.getLogger(name)

    # If the logger is already initialized, just return it
    if len(mylog.handlers) > 0:
        return mylog

    # Add the custom log levels to the logger
    for name, level in vars(CustomLogLevels).items():
        if name.startswith("_"):
            continue
        logging.addLevelName(name, level)
    mylog.setLevel(CustomLogLevels.DEBUG2)

    # Create convenience functions for the custom log levels
    logging.Logger.debug2 = lambda self, message, *args, **kwargs: self._log(CustomLogLevels.DEBUG2, message, args, **kwargs)
    logging.Logger.passed = lambda self, message, *args, **kwargs: self._log(CustomLogLevels.PASS, message, args, **kwargs)
    logging.Logger.fail = lambda self, message, *args, **kwargs: self._log(CustomLogLevels.FAIL, message, args, **kwargs)
    logging.Logger.raw = lambda self, message, *args, **kwargs: self._log(CustomLogLevels.RAW, message, args, **kwargs)
    logging.Logger.time = lambda self, message, *args, **kwargs: self._log(CustomLogLevels.TIME, message, args, **kwargs)
    logging.Logger.banner = lambda self, message, *args, **kwargs: self._log(CustomLogLevels.BANNER, message, args, **kwargs)
    logging.Logger.step = lambda self, message, *args, **kwargs: self._log(CustomLogLevels.STEP, message, args, **kwargs)
    logging.Logger.gray = lambda self, message, *args, **kwargs: self._log(CustomLogLevels.GRAY, message, args, **kwargs)
    logging.Logger.white = lambda self, message, *args, **kwargs: self._log(CustomLogLevels.WHITE, message, args, **kwargs)
    logging.Logger.yellow = lambda self, message, *args, **kwargs: self._log(CustomLogLevels.YELLOW, message, args, **kwargs)
    logging.Logger.red = lambda self, message, *args, **kwargs: self._log(CustomLogLevels.RED, message, args, **kwargs)
    logging.Logger.green = lambda self, message, *args, **kwargs: self._log(CustomLogLevels.GREEN, message, args, **kwargs)
    logging.Logger.blue = lambda self, message, *args, **kwargs: self._log(CustomLogLevels.BLUE, message, args, **kwargs)
    logging.Logger.pink = lambda self, message, *args, **kwargs: self._log(CustomLogLevels.PINK, message, args, **kwargs)
    logging.Logger.fake = lambda self, message, *args, **kwargs: self._log(CustomLogLevels.FAKE, message, args, **kwargs)
    logging.Logger.test = lambda self, message, *args, **kwargs: self._log(CustomLogLevels.TEST, message, args, **kwargs)
    logging.Logger.blankline = lambda self, *args, **kwargs: self._log(CustomLogLevels.BLANK, "", args, **kwargs)

    # Create convenience functions to turn on/off output and debug at runtime
    def _ShowDebug(self, level=1):
        """Show debug level log statements on the console"""
        if level >= 2:
            lev = CustomLogLevels.DEBUG2
        else:
            lev = logging.DEBUG
        for handler in self.handlers:
            if handler.get_name() == 'console':
                handler.setLevel(lev)
    def _HideDebug(self):
        """Hide debug level log statements on the console"""
        for handler in self.handlers:
            if handler.get_name() == 'console':
                handler.setLevel(logging.INFO)
    def _Silence(self):
        """Turn off all logging to the console"""
        for handler in self.handlers:
            if handler.get_name() == 'console':
                handler.setLevel(999)
    def _TruncateLongMessages(self, truncate):
        """Truncate long log messages before displaying them"""
        for handler in self.handlers:
            setattr(handler.formatter, "truncateLongMessages", truncate)
    logging.Logger.ShowDebug = _ShowDebug
    logging.Logger.HideDebug = _HideDebug
    logging.Logger.Silence = _Silence
    logging.Logger.TruncateMessages = _TruncateLongMessages

    # Add syslog logging
    if logConfig['enableSyslog']:
        if platform.system().lower().startswith('win'):
            #pylint: disable=import-error
            import pywintypes
            #pylint: enable=import-error
            try:
                eventlogFormatter = logging.Formatter('%(levelname)s %(message)s')
                eventlog = logging.handlers.NTEventLogHandler(name)
                eventlog.setLevel(logging.DEBUG)
                eventlog.setFormatter(eventlogFormatter)
                eventlog.set_name('eventlog')
                mylog.addHandler(eventlog)
            except pywintypes.error:
                # Probably not running as administrator
                pass
        else:
            fmt = '%(name)s[%(process)d]: %(levelname)s %(message)s'
            syslogFormatter = logging.Formatter(fmt)
            syslog = None
            # Try to connect to syslog on the local unix socket
            syslogAddress = '/dev/log'
            if 'darwin' in platform.system().lower():
                syslogAddress='/var/run/syslog'
            try:
                syslog = logging.handlers.SysLogHandler(address=syslogAddress, facility=logConfig['syslogFacility'])
            except socket.error:
                # Try again with UDP
                syslog = logging.handlers.SysLogHandler(address=('localhost', 514), facility=logConfig['syslogFacility'])
            syslog.setLevel(logging.DEBUG)
            syslog.setFormatter(syslogFormatter)
            syslog.set_name('syslog')
            mylog.addHandler(syslog)

    # Add file logging
    if logConfig['enableFile']:
        logFile = logConfig['logFile'] or '{}.log'.format(name)
        fileFormatter = logging.Formatter('%(asctime)s: %(name)s[%(process)d]: %(levelname)s %(message)s')
        fileLogger = logging.FileHandler(logFile)
        fileLogger.setLevel(CustomLogLevels.DEBUG2)
        fileLogger.setFormatter(fileFormatter)
        fileLogger.set_name('file')
        mylog.addHandler(fileLogger)

    # Add console logging
    if logConfig['enableConsole']:
        fmt = ''
        for option in FormatOptions.formatMap.keys():
            if logConfig['prefix'] & option == option:
                fmt += FormatOptions.formatMap[option]
        fmt += '%(message)s'
        console_formatter = MultiFormatter(fmt)
        if logConfig['consoleColor']:
            console = ColorizingStreamHandler(stream=sys.stdout)
        else:
            console = logging.StreamHandler(stream=sys.stdout)
        console.setLevel(logConfig['consoleLevel'])
        console.setFormatter(console_formatter)
        console.set_name('console')
        mylog.addHandler(console)

    return mylog
