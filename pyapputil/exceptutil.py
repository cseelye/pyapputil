#!/usr/bin/env python2.7
"""This module provides utility classes and functions for exceptions"""
import copy
import json

class ApplicationError(Exception):
    """Base class for all exceptions thrown by this app. This provides the starting point for a rooted exception hierarchy"""

    def __init__(self, message, originalTraceback=None, innerException=None):
        super(ApplicationError, self).__init__(message)
        self.originalTraceback = originalTraceback
        self.innerException = innerException

    def IsRetryable(self):
        return False

    def ToDict(self):
        """Convert this exception to a dictionary"""
        return {k:copy.deepcopy(v) for k,v in vars(self).iteritems() if not k.startswith('_')}

    def ToJSON(self):
        """Convert this exception to a JSON string"""
        return json.dumps(self.ToDict())

class InvalidArgumentError(ApplicationError):
    """Exception raised when invalid arguments are passed to a function or invalid type conversion is attempted"""

class TimeoutExpiredError(ApplicationError):
    """Exception raised when a timeout expires"""

class LocalEnvironmentError(ApplicationError):
    """Exception raised when something goes wrong on the local system, outside of python.
    This is basically a wrapper for python's EnvironmentError that is rooted in our app exception hierarchy"""

    def __init__(self, innerException):
        """
        Initialize this exception with an existing exception

        Arguments:
            innerException:     the exception to wrap. It must be an exception from the EnvironmentError hierarchy (IOError, OSError)
        """

        # Make sure the input at least looks like an EnvironmentError
        assert(hasattr(innerException, 'errno'))
        assert(hasattr(innerException, 'strerror'))

        self.args = (innerException)

        if innerException.strerror:
            self.message = innerException.strerror.strip()
        else:
            self.message = str(innerException).strip()
        super(LocalEnvironmentError, self).__init__(self.message)
        self.innerException = innerException
        self.errno = innerException.errno
