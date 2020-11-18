#!/usr/bin/env python
"""This module provides utility classes and functions for threading/multiprocessing"""

import fcntl as _fcntl
import functools as _functools
import multiprocessing as _multiprocessing
import multiprocessing.pool as _multiprocessing_pool
import sys as _sys
import threading as _threading
import traceback as _traceback
from io import open

from .logutil import GetLogger
from .appconfig import appconfig, add_default
from .exceptutil import ApplicationError, TimeoutExpiredError

# Helpful multiprocessing debug for threadpools
# from logging import DEBUG as _DEBUG_LEVEL
# import multiprocessing.util as _multiprocessing_util
# _multiprocessing_util.log_to_stderr(_DEBUG_LEVEL)

CPU_THREADS = _multiprocessing.cpu_count()

add_default("use_multiprocessing", False)

_globalPool = None
_globalPoolLock = _multiprocessing.Lock()
def GlobalPool():
    """ Get the singleton global thread pool """
    #pylint: disable=global-statement
    global _globalPool
    #pylint: enable=global-statement
    with _globalPoolLock:
        if not _globalPool:
            _globalPool = ThreadPool()
    return _globalPool

def ShutdownGlobalPool():
    """Shutdown the global threadpool singleton"""
    with _globalPoolLock:
        if _globalPool:
            _globalPool.Shutdown()

def IsMainThread():
    """
    Check if the current thread is the main thread

    Returns:
        Boolean true if this is the main thread, false otherwise
    """
    return _threading.current_thread().name == "MainThread"

def IsMainProcess():
    """
    Check if the current process is the main process

    Returns:
        Boolean true if this is the main process, false otherwise
    """
    #pylint: disable=not-callable
    return _multiprocessing.current_process().name == "MainProcess"
    #pylint: enable=not-callable

class AsyncResult(object):
    """Result object from posting to a ThreadPool"""

    def __init__(self, result):
        self.result = result

    def Get(self, timeout=None):
        """
        Wait for and return the result of the thread. If the timeout expires before the thread is finished, throw TimeoutExpiredError

        Args:
            timeout:    how long to wait for the thread to finish (float)

        Returns:
            The return value of the thread
        """
        if timeout is None:
            timeout = 0xFFFF
        try:
            return self.result.get(timeout)
        except _multiprocessing.TimeoutError:
            raise TimeoutExpiredError("The timeout expired before the thread completed")

    def Wait(self, timeout):
        """
        Wait for the thread to complete

        Args:
            timeout:    how long to wait before giving up, in seconds (float)

        Returns:
            Boolean true if the thread is ready or false if the timeout expired (bool)
        """
        self.result.wait(timeout)
        return self.result.ready()

    def Ready(self):
        """
        Test if the thread has completed and a result is ready

        Returns:
            True if the thread is compelte, False if it is not (bool)
        """
        return self.result.ready()

def _initworkerprocess():
    """
    Initialization function for workers in a process pool.
    This turns off SIGINT handling in sub-processes
    """
    import signal
    signal.signal(signal.SIGINT, signal.SIG_IGN)

class ThreadPool(object):
    """Helper to manage status and lifetime of threads/processes"""

    def __init__(self, maxThreads=CPU_THREADS, useMultiprocessing=appconfig["use_multiprocessing"]):
        if useMultiprocessing:
            self.threadPool = _multiprocessing.Pool(processes=maxThreads, initializer=_initworkerprocess)
        else:
            self.threadPool = _multiprocessing_pool.ThreadPool(processes=maxThreads)
        self.results = []

    def Post(self, threadFunc, *args, **kwargs):
        """
        Add a new work item

        Args:
            threadFunc:     the function to be run as a thread
            args:           args to pass to the thread function
            kwargs:         keyword args to pass to the thread function

        Returns:
            AsyncResult object
        """
        raw_result = self.threadPool.apply_async(threadFunc, args, kwargs)
        res = AsyncResult(raw_result)
        self.results.append(res)
        return res

    def Wait(self):
        """
        Wait for all threads to finish and collect the results

        Returns:
            Boolean true if all threads succeeded, False if one or more failed
        """
        return WaitForThreads(self.results)

    def Shutdown(self):
        """
        Abort any running processes and shut down the pool
        """
        self.threadPool.close()
        self.threadPool.terminate()

def WaitForThreads(asyncResults):
    """
    Wait for a list of threads to finish and collect the results

    Args:
        asyncResults:    a list of async results to wait for (multiprocessing.pool.AsyncResult)

    Returns:
        Boolean true if all threads succeeded, False if one or more failed
    """
    log = GetLogger()
    allgood = True
    for item in asyncResults:
        # If the result is not True, or if there is an exception, this thread failed
        try:
            result = item.Get()
            if result is False:
                allgood = False
        except ApplicationError as e:
            log.error(e)
            allgood = False

    return allgood

def threadwrapper(func):
    """Decorator for functions to be run as threads"""

    @_functools.wraps(func)
    def __wrapper(*args, **kwargs):
        orig_name = _threading.current_thread().name
        try:
            return func(*args, **kwargs)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            # For exceptions from child threads/processes, we want to extract and store the original traceback, otherwise it may
            # be lost to multiprocessing/pickling and inaccessible when the exception gets rethrown in the parent process
            # For convenience, we also convert all exceptions into our rooted exception hierarchy
            ex_type, ex_val, ex_tb = _sys.exc_info()
            str_tb = "".join(_traceback.format_tb(ex_tb))
            if isinstance(ex_val, ApplicationError):
                ex_val.originalTraceback = str_tb
                raise
            log = GetLogger()
            log.debug2(str_tb)
            raise ApplicationError("{}: {}".format(ex_type.__name__, ex_val), str_tb, ex_val)
        finally:
            _threading.current_thread().name = orig_name

    return __wrapper

class LockFile(object):
    """Wrapper for using an OS lockfile for coordination"""

    def __init__(self, lockname):
        self.lockFile = "/var/tmp/{}.lockfile".format(lockname)
        self.fd = open(self.lockFile, "w")

    def __enter__(self):
        self.Lock()

    def __exit__(self, extype, exval, tb):
        self.Unlock()

    def __del__(self):
        """Make sure the lock gets unlocked when we exit"""
        self.Unlock()
        self.fd.close()

    def Lock(self):
        """Lock"""
        _fcntl.flock(self.fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)

    def Unlock(self):
        """Unlock"""
        _fcntl.flock(self.fd, _fcntl.LOCK_UN)
