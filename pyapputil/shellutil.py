#!/usr/bin/env python
"""
Helpers for running shell commands and manipulating the console/terminal in a cross-platform way
"""

#pylint: disable=bare-except

import os
import shlex
import struct
import platform
import subprocess
import threading
from .logutil import GetLogger

LOCAL_SYS = platform.system()
if LOCAL_SYS == "Windows":
    import ctypes
    from ctypes import windll
else:
    class WindowsError(Exception):
        pass

def GetConsoleSize():
    """
    Get the width and height of the console

    Returns:
        A tuple  of (width, height)
    """
    size = None
    if LOCAL_SYS == 'Windows':
        size = _GetConsoleSizeWindows()
        if size is None:
            size = _GetConsoleSizeTput()
    if LOCAL_SYS in ['Linux', 'Darwin'] or LOCAL_SYS.startswith('CYGWIN'):
        size = _GetConsoleSizeUnix()
    if size is None:
        size = (80, 25)      # default value
    return size

def _GetConsoleSizeWindows():
    """
    Get the width and height of the console on Windows platform

    Returns:
        A tuple  of (width, height)
    """
    try:
        # stdin handle is -10
        # stdout handle is -11
        # stderr handle is -12
        h = windll.kernel32.GetStdHandle(-12)
        csbi = ctypes.create_string_buffer(22)
        res = windll.kernel32.GetConsoleScreenBufferInfo(h, csbi)
        if res:
            (_, _, _, _, _, left, top, right, bottom, _, _) = struct.unpack("hhhhHhhhhhh", csbi.raw)
            sizex = right - left + 1
            sizey = bottom - top + 1
            return (sizex, sizey)
    except:
        return None

def _GetConsoleSizeTput():
    """
    Get the width and height of the console using tput

    Returns:
        A tuple  of (width, height)
    """
    try:
        with open(os.devnull, "w") as DEVNULL:
            cols = int(subprocess.check_call(shlex.split('tput cols'), stderr=DEVNULL))
            rows = int(subprocess.check_call(shlex.split('tput lines'), stderr=DEVNULL))
            return (cols, rows)
    except subprocess.CalledProcessError:
        return None

def _GetConsoleSizeUnix():
    """
    Get the width and height of the console on Unix-like platform

    Returns:
        A tuple  of (width, height)
    """
    def ioctl_GWINSZ(fd):
        """Execute the GWINSZ ioctl"""
        try:
            import fcntl
            import termios
            cr = struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234'))
            return cr
        except:
            pass
    cr = ioctl_GWINSZ(0) or ioctl_GWINSZ(1) or ioctl_GWINSZ(2)

    if not cr:
        try:
            fd = os.open(os.ctermid(), os.O_RDONLY)
            cr = ioctl_GWINSZ(fd)
            os.close(fd)
        except:
            pass

    if not cr:
        cr = _GetConsoleSizeTput()

    if not cr:
        try:
            cr = (os.environ['LINES'], os.environ['COLUMNS'])
        except:
            return None

    try:
        return (int(cr[1]), int(cr[0]))
    except:
        return None

class ShellCommand(object):
    """Cross-platform way to run a shell command with a timeout"""
    def __init__(self, cmd):
        self.cmd = cmd
        self.process = None
        self.stdout = ""
        self.stderr = ""
        self.retcode = None
        self.log = GetLogger()

    def run(self, timeout):
        """run the command"""

        def process_thread():
            """function to be run as a separate thread"""
            self.process = subprocess.Popen(self.cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            self.stdout, self.stderr = self.process.communicate()

        # Start the thread
        self.log.debug2("Executing local command=[{}]".format(self.cmd))
        thread = threading.Thread(target=process_thread)
        thread.daemon = True
        thread.start()

        # Wait 'timeout' seconds for the thread to finish
        thread.join(timeout)

        # Kill the thread if it is still running
        if thread.is_alive() and self.process:
            self.log.debug2("Terminating subprocess [{}] after {} sec".format(self.cmd, timeout))

            # The PID of the subprocess is actually the PID of the shell (/bin/sh or cmd.exe), since we launch with shell=True above.
            # This means that killing this PID leaves the actual process we are interested in still running as an orphaned subprocess
            # So we need to kill all the children of that parent process
            if LOCAL_SYS == "Windows":
                # This will kill everything in this shell as well as the shell itself
                os.system("wmic Process WHERE ParentProcessID={} delete 2>&1 > NUL".format(self.process.pid))
            else:
                os.system("for pid in $(pgrep -P {}); do kill -9 $pid 2>&1 >/dev/null; done".format(self.process.pid))

            # Now we can kill the parent process if it is still running and wait for the thread to finish
            try:
                self.process.kill()
            except WindowsError:
                pass
            thread.join()

        # Return the result of the command
        self.log.debug2("retcode=[{}] stdout=[{}] stderr=[{}]".format(self.process.returncode, self.stdout.rstrip("\n"), self.stderr.rstrip("\n")))
        return self.process.returncode, self.stdout, self.stderr

def Shell(command, timeout=1800):
    """
    Run a shell command and return the result

    Args:
        command:    the command to run
        timeout:    the timeout (in seconds) to wait for the command

    Returns:
        A tuple of (returncode, stdout, stderr)
    """
    return ShellCommand(command).run(timeout)


#pylint: enable=bare-except
