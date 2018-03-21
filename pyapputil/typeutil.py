#!/usr/bin/env python2.7
"""This module provides type/bounds/etc checking helpers for function args or command line args, compatible with argutil/argparse"""

import inspect as _inspect
import re as _re
import socket as _socket

import functools as _functools
from .logutil import GetLogger
from .exceptutil import InvalidArgumentError

def ValidateArgs(args, validators):
    """
    Validate a list of arguments using the supplied validator functions

    Args:
        args:           a dictionary of arg name => arg value (dict)
        validators:     a dictionary of arg name => validator function (dict)

    Returns:
        The validated and type converted arguments
    """
    validated = {}
    errors = []
    for arg_name in validators.keys():
        # Make sure this argument is present
        if arg_name not in args:
            errors.append("Missing argument '{}'".format(arg_name))
        else:
            # Make sure this argument is valid using the supplied validator
            if validators[arg_name]:
                try:
                    valid = validators[arg_name](args[arg_name])
                    # Special case for BoolType, which can return False
                    if getattr(validators[arg_name], "__name__", "") != "BoolType" and valid is False:
                        errors.append("Invalid value for '{}'".format(arg_name))
                    else:
                        validated[arg_name] = valid
                except InvalidArgumentError as e:
                    errors.append("Invalid value for '{}' - {}".format(arg_name, e))
            # Make sure this argument has a value
            # boolean False or empty list is OK, but None or empty string is not
            elif args[arg_name] is None or args[arg_name] == "":
                errors.append("'{}' must have a value".format(arg_name))
    if errors:
        raise InvalidArgumentError("\n".join(errors))

    for argname, argvalue in args.items():
        if argname not in validated.keys():
            validated[argname] = argvalue

    return validated

class ValidateAndDefault(object):
    """
    Decorator to validate, typecheck, and set defaults for function arguments
    """
    def __init__(self, argValidators):
        self.validators = {}
        self.defaults = {}
        for arg_name, (arg_type, arg_default) in argValidators.items():
            self.validators[arg_name] = arg_type
            self.defaults[arg_name] = arg_default

    def __call__(self, func):

        @_functools.wraps(func)
        def wrapper(*args, **kwargs):
            log = GetLogger()
            # Build a dictionary of arg name => default value from the function spec
            spec = _inspect.getargspec(func)
            arg_names = list(spec.args)
            if spec.defaults:
                arg_defaults = list(spec.defaults)
            else:
                arg_defaults = []
            while len(arg_defaults) < len(arg_names):
                arg_defaults.insert(0, None)
            default_args = dict(zip(arg_names, arg_defaults))
            # Replace any defaults with the ones supplied to this decorator
            if self.defaults:
                for arg_name, arg_default in self.defaults.items():
                    default_args[arg_name] = arg_default

            # Combine args and kwargs into a single dictionary of arg name => user supplied value
            user_args = {}
            for idx, user_val in enumerate(args):
                arg_name = arg_names[idx]
                user_args[arg_name] = user_val
            for arg_name, user_val in kwargs.items():
                user_args[arg_name] = user_val

            # Fill in and log the default values being used
            for arg_name, validator in self.validators.items():
                if arg_name not in user_args or user_args[arg_name] == None:
                    log.debug2("  Using default value {}={}".format(arg_name, default_args[arg_name]))
                    user_args[arg_name] = default_args[arg_name]

            # Run each validator against the user input
            errors = []
            valid_args = {}
            for arg_name, validator in self.validators.items():
                if arg_name not in user_args:
                    errors.append("{} must have a value".format(arg_name))
                    continue
                user_val = user_args[arg_name]

                if validator:
                    log.debug2("  Validating {}={} is a {}".format(arg_name, user_val, GetPrettiestTypeName(self.validators[arg_name])))
                    try:
                        valid_val = self.validators[arg_name](user_val)
                        valid_args[arg_name] = valid_val
                    except InvalidArgumentError as ex:
                        errors.append("invalid value for {} - {}".format(arg_name, ex))
                elif user_val is None or user_val == "":
                    errors.append("{} must have a value".format(arg_name))
                else:
                    valid_args[arg_name] = user_val

            # Look for any "extra" args that were passed in
            for arg_name in user_args.keys():
                if arg_name not in self.validators.keys():
                    errors.append("Unknown argument {}".format(arg_name))

            if errors:
                raise InvalidArgumentError("\n".join(errors))

            return func(**valid_args)

        setattr(wrapper, "__innerfunc__", func)
        return wrapper

def IsSet(value, name=None):
    """
    Validate that the value is not None or an empty string
    Boolean false or an empty list are OK
    """
    if value is None or value == "":
        if name:
            raise InvalidArgumentError("{} must have a value".format(name))
        else:
            raise InvalidArgumentError("Argument must have a value")
    return value

def StrType(string, allowEmpty=False, name=None):
    """Type for validating strings"""
    if string:
        string = str(string)

    if string is None or (string == "" and not allowEmpty):
        if name:
            raise InvalidArgumentError("{} must have a value".format(name))
        else:
            raise InvalidArgumentError("Argument must have a value")

    return string

class SelectionType(object):
    """Type for making a choice from a list of options"""

    def __init__(self, choices, itemType=StrType):
        if not callable(itemType):
            raise ValueError("type must be callable")
        self.choices = choices
        self.itemType = itemType

    def __call__(self, string):
        # Verify that the selection is one of the choices
        try:
            sel = self.itemType(string)
        except (TypeError, ValueError):
            raise InvalidArgumentError("'{}' is not a valid {}".format(string, self.itemType.__name__))

        if sel not in self.choices:
            raise InvalidArgumentError("'{}' is not a valid choice".format(string))

        return sel

    def __repr__(self):
        return "SelectionType({}) [{}]".format(GetPrettiestTypeName(self.itemType), ",".join([str(c) for c in self.choices]))

class ItemList(object):
    """Type for making a list of things"""

    def __init__(self, itemType=str, allowEmpty=False):
        if not callable(itemType):
            raise ValueError("type must be callable")
        self.itemType = itemType
        self.allowEmpty = allowEmpty

    def __call__(self, string):
        # Split into individual items
        if string is None:
            items = []
        elif isinstance(string, basestring):
            items = [i for i in _re.split(r"[,\s]+", string) if i]
        else:
            try:
                items = list(string)
            except TypeError:
                items = []
                items.append(string)

        # Validate each item is the correct type
        try:
            items = [self.itemType(i) for i in items]
        except (TypeError, ValueError):
            raise InvalidArgumentError("Invalid {} value".format(self.itemType.__name__))

        # Validate the list is not empty
        if not self.allowEmpty and not items:
            raise InvalidArgumentError("list cannot be empty")

        return items

    def __repr__(self):
        return "list({})".format(GetPrettiestTypeName(self.itemType))

class OptionalValueType(object):
    """Type for validating an optional"""

    def __init__(self, itemType=str):
        if not callable(itemType) and itemType is not None:
            raise ValueError("type must be callable")
        self.itemType = itemType

    def __call__(self, string):
        if string is None:
            return None

        if self.itemType is None:
            return string

        try:
            item = self.itemType(string)
        except (TypeError, ValueError):
            raise InvalidArgumentError("{} is not a valid {}".format(string, self.itemType.__name__))
        return item

    def __repr__(self):
        return "OptionalValueType({})".format(GetPrettiestTypeName(self.itemType))

def AtLeastOneOf(**kwargs):
    """Validate that one or more of the list of items has a value"""
    if not any(kwargs.values()):
        raise InvalidArgumentError("At least one of [{}] must have a value".format(",".join(kwargs.keys())))

def BoolType(string, name=None):
    """Type for validating boolean"""
    if isinstance(string, bool):
        return string

    string = str(string).lower()
    if string in ["f", "false"]:
        return False
    elif string in ["t", "true"]:
        return True

    if name:
        raise InvalidArgumentError("Invalid boolean value for {}".format(name))
    else:
        raise InvalidArgumentError("Invalid boolean value")

def IPv4AddressType(addressString, allowHostname=True):
    """Type for validating IP v4 addresses"""

    if allowHostname:
        errormsg = "{} is not a resolvable hostname or valid IP address".format(addressString)
    else:
        errormsg = "{} is not a valid IP address".format(addressString)

    if not addressString:
        raise InvalidArgumentError("missing value")

    # Check for resolvable hostname
    if any (c.isalpha() for c in addressString):
        if allowHostname:
            return ResolvableHostname(addressString)
        else:
            raise InvalidArgumentError("{} is not a valid IP address".format(addressString))

    try:
        _socket.inet_pton(_socket.AF_INET, addressString)
        return addressString
    except AttributeError: # inet_pton not available
        try:
            _socket.inet_aton(addressString)
            return addressString
        except _socket.error:
            raise InvalidArgumentError(errormsg)
    except _socket.error: # not a valid address
        raise InvalidArgumentError(errormsg)

    pieces = addressString.split(".")
    if len(pieces) != 4:
        raise InvalidArgumentError(errormsg)

    try:
        pieces = [int(i) for i in pieces]
    except ValueError:
        raise InvalidArgumentError(errormsg)

    if not all([i >= 0 and i <= 255 for i in pieces]):
        raise InvalidArgumentError(errormsg)

    return addressString

def IPv4AddressOnlyType(addressString):
    """Type for validating IPv4 addresses"""
    return IPv4AddressType(addressString, allowHostname=False)

def ResolvableHostname(hostnameString):
    """Type for validating a string is a resolvable hostname"""

    hostnameString = StrType(hostnameString)

    if not hostnameString:
        raise InvalidArgumentError("missing value")

    try:
        _socket.gethostbyname(hostnameString)
    except _socket.gaierror: #Unable to resolve host name
        raise InvalidArgumentError("{} is not a resolvable hostname".format(hostnameString))

    return hostnameString

def IPv4SubnetType(subnetString):
    """Type for validating subnets, either CIDR or network/netmask"""
    if not subnetString:
        raise InvalidArgumentError("missing value")

    if "/" not in subnetString:
        raise InvalidArgumentError("missing CIDR bits or netmask")

    network, mask = subnetString.split("/")

    # Validate the network is a valid IP address
    IPv4AddressType(network, allowHostname=False)

    # Validate the mask is either a valid IP, or an integer between 0 and 32
    try:
        IPv4AddressType(mask, allowHostname=False)
        return subnetString
    except InvalidArgumentError:
        pass

    try:
        IntegerRangeType(0, 32)(mask)
        return subnetString
    except InvalidArgumentError:
        pass

    raise InvalidArgumentError("invalid CIDR bits or netmask")

class CountType(object):
    """Type for validating a count of something"""

    def __init__(self, allowZero=False):
        if allowZero:
            self.minval = 0
        else:
            self.minval = 1

    def __call__(self, string):
        return IntegerRangeType(self.minval)(string)

class IntegerRangeType(object):
    """Type for validating an integer within a range of values, inclusive"""

    def __init__(self, minValue=None, maxValue=None):
        self.minValue = None
        self.maxValue = None

        if minValue is not None:
            self.minValue = int(minValue)
        if maxValue is not None:
            self.maxValue = int(maxValue)

    def __call__(self, string):

        try:
            number = int(string)
        except (TypeError, ValueError):
            raise InvalidArgumentError("{} is not a valid integer".format(string))

        if self.minValue is not None and number < self.minValue:
            raise InvalidArgumentError("{} must be >= {}".format(number, self.minValue))

        if self.maxValue is not None and number > self.maxValue:
            raise InvalidArgumentError("{} must be <= {}".format(number, self.maxValue))

        return number

def PositiveIntegerType(string):
    """Type for validating integers"""

    errormsg = "{} is not a positive integer".format(string)

    try:
        number = int(string)
    except (TypeError, ValueError):
        raise InvalidArgumentError(errormsg)

    if number < 0:
        raise InvalidArgumentError(errormsg)
    return number

def PositiveNonZeroIntegerType(string):
    """Type for validating integers"""

    errormsg = "{} is not a positive non-zero integer".format(string)

    try:
        number = int(string)
    except (TypeError, ValueError):
        raise InvalidArgumentError(errormsg)

    if number <= 0:
        raise InvalidArgumentError(errormsg)
    return number

def VLANTagType(string):
    """Type for validating VLAN tags"""

    errormsg = "{} is not a valid VLAN tag".format(string)

    try:
        tag = int(string)
    except (TypeError, ValueError):
        raise InvalidArgumentError(errormsg)
    if tag < 1 or tag > 4095:
        raise InvalidArgumentError(errormsg)
    return tag

def MACAddressType(string):
    """Type for validating MAC address"""

    errormsg = "{} is not a valid MAC address".format(string)

    if not _re.match("[0-9a-f]{2}([-:])[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", string):
        raise InvalidArgumentError(errormsg)
    return string.lower()

def RegexType(string):
    """Type for validating regexes"""

    try:
        _re.compile(string)
    except _re.error:
        raise InvalidArgumentError("Invalid regex")
    return string

def GetPrettiestTypeName(typeToName):
    """Get the best human representation of a type"""
    typename = repr(typeToName)
    # Hacky
    if typename.startswith("<"):
        typename = getattr(typeToName, "__name__", str(typeToName))
    return typename
