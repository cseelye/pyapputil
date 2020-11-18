#!/usr/bin/env python2.7
"""This module provides type/bounds/etc checking helpers for function args or command line args, compatible with argutil/argparse"""

from past.builtins import basestring as _basestring
import inspect as _inspect
import re as _re
import socket as _socket
import string as _string
import sys as _sys

import functools as _functools
from .logutil import GetLogger
from .exceptutil import InvalidArgumentError

# py2 vs py3
if hasattr(_string, "letters"):
    setattr(_string, "ascii_letters", _string.letters) #pylint: disable=no-member

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
        if argname not in list(validated.keys()):
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
            """validate and set defaults"""
            log = GetLogger()
            # Build a dictionary of arg name => default value from the function spec
            spec = _inspect.getargspec(func) #pylint: disable=deprecated-method
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
                if arg_name not in user_args or user_args[arg_name] is None:
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
                    log.debug2("  Skipping validation for {}".format(arg_name))
                    valid_args[arg_name] = user_val

            # Look for any "extra" args that were passed in
            for arg_name in user_args.keys():
                if arg_name not in list(self.validators.keys()):
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

class StrType(object):
    """Type for validating strings"""

    def __init__(self, allowEmpty=False, name=None, invalidCharacters=None, whitelistedCharacters=None, maxLength=None):
        self.allowEmpty = allowEmpty
        self.name = name
        self.invalidCharacters = invalidCharacters
        self.whitelistedCharacters = whitelistedCharacters
        self.maxLength = maxLength

    def __call__(self, inVal):
        if inVal:
            inVal = str(inVal)

        if inVal is None or (inVal == "" and not self.allowEmpty):
            raise InvalidArgumentError("{} must have a value".format(self.name if self.name else "Argument"))

        if self.invalidCharacters:
            m = _re.search(r"([{}]+)".format(self.invalidCharacters), inVal)
            if m:
                raise InvalidArgumentError("{} contains invalid character".format(self.name if self.name else "Argument"))

        if self.whitelistedCharacters:
            if any(c not in self.whitelistedCharacters for c in inVal):
                raise InvalidArgumentError("{} contains invalid character".format(self.name if self.name else "Argument"))

        if self.maxLength:
            if len(inVal) > self.maxLength:
                raise InvalidArgumentError("{} is longer than the maximum {} characters".format(inVal, self.maxLength))

        return inVal

    def __repr__(self):
        return "str"

class NonNumericStringType(StrType):
    """Type for validating strings that cannot be numbers"""

    def __call__(self, inVal):
        inVal = super(NonNumericStringType, self).__call__(inVal)
        valid = False
        for numtype in [int, float]:
            try:
                numtype(inVal)
                valid = True
                break
            except (ValueError, TypeError):
                continue
        if valid:
            raise InvalidArgumentError("{} cannot be a number".format(inVal))
        return inVal

class SelectionType(object):
    """Type for making a choice from a list of options"""

    def __init__(self, choices, itemType=StrType()):
        if not callable(itemType):
            raise ValueError("type must be callable")
        self.choices = choices
        self.itemType = itemType

    def __call__(self, inVal):
        # Verify that the selection is one of the choices
        try:
            sel = self.itemType(inVal)
        except (TypeError, ValueError):
            raise InvalidArgumentError("'{}' is not a valid {}".format(inVal, GetPrettiestTypeName(self.itemType.__name__)))

        if sel not in self.choices:
            raise InvalidArgumentError("'{}' is not a valid choice".format(inVal))

        return sel

    def __repr__(self):
        return "SelectionType({}) [{}]".format(GetPrettiestTypeName(self.itemType), ",".join([str(c) for c in self.choices]))

class ItemList(object):
    """Type for making a list of things"""

    def __init__(self, itemType=StrType(), allowEmpty=False, minLength=0, maxLength=_sys.maxsize):
        if not callable(itemType) and itemType is not None:
            raise ValueError("type must be callable or None")
        self.itemType = itemType
        self.allowEmpty = allowEmpty
        self.minLength = minLength
        self.maxLength = maxLength

    def __call__(self, inVal):
        # Split into individual items
        if inVal is None:
            items = []
        elif isinstance(inVal, _basestring):
            items = [i for i in _re.split(r"[,\s]+", inVal) if i]
        else:
            try:
                items = list(inVal)
            except TypeError:
                items = []
                items.append(inVal)

        # Validate each item is the correct type
        try:
            items = [self.itemType(i) for i in items]
        except (TypeError, ValueError) as ex:
            raise InvalidArgumentError("Invalid {} value: {}".format(GetPrettiestTypeName(self.itemType.__name__), ex))

        # Validate the list is not empty
        if not self.allowEmpty and not items:
            raise InvalidArgumentError("list cannot be empty")

        # Validate min and max length
        if len(items) < self.minLength:
            raise InvalidArgumentError("list must be at least {} elements".format(self.minLength))
        if len(items) > self.maxLength:
            raise InvalidArgumentError("list must be no more than {} elements".format(self.maxLength))

        return items

    def __repr__(self):
        return "list({})".format(GetPrettiestTypeName(self.itemType))

class OptionalValueType(object):
    """Type for validating an optional"""

    def __init__(self, itemType=StrType()):
        if not callable(itemType) and itemType is not None:
            raise ValueError("type must be callable or None")
        self.itemType = itemType

    def __call__(self, inVal):
        if inVal is None:
            return None

        if self.itemType is None:
            return inVal

        try:
            item = self.itemType(inVal)
        except (TypeError, ValueError):
            raise InvalidArgumentError("{} is not a valid {}".format(inVal, GetPrettiestTypeName(self.itemType.__name__)))
        return item

    def __repr__(self):
        return "OptionalValueType({})".format(GetPrettiestTypeName(self.itemType))

class MultiType(object):
    """Type for things that can be more than one type"""

    def __init__(self, *allowedTypes):
        self.allowedTypes = allowedTypes
        for atype in self.allowedTypes:
            if not callable(atype):
                raise ValueError("type must be callable")

    def __call__(self, inVal):
        errors = []
        for possibleType in self.allowedTypes:
            try:
                return possibleType(inVal)
            except (TypeError, ValueError, InvalidArgumentError) as ex:
                errors.append("{}: {}".format(GetPrettiestTypeName(possibleType), ex))
                continue
        raise InvalidArgumentError("{} could not be parsed into an allowed type - {}".format(inVal, ", ".join(errors)))

    def __repr__(self):
        return "MultiType({})".format(", ".join([GetPrettiestTypeName(t) for t in self.allowedTypes]))

def AtLeastOneOf(**kwargs):
    """Validate that one or more of the list of items has a value"""
    if not any(kwargs.values()):
        raise InvalidArgumentError("At least one of [{}] must have a value".format(",".join(list(kwargs.keys()))))

class BoolType(object):
    """Type for validating boolean"""

    def __init__(self, name=None):
        self.name = name

    def __call__(self, inVal):
        if isinstance(inVal, bool):
            return inVal

        inVal = str(inVal).lower()
        if inVal in ["f", "false", "0"]:
            return False
        elif inVal in ["t", "true", "1"]:
            return True

        raise InvalidArgumentError("Invalid boolean value{}".format(" for {}".format(self.name) if self.name else ""))

    def __repr__(self):
        return "bool"

class IPv4AddressOnlyType(StrType):
    """Type for validating IP v4 addresses"""

    def __init__(self):
        super(IPv4AddressOnlyType, self).__init__(allowEmpty=False, whitelistedCharacters=_string.digits + ".")

    def __call__(self, inVal):
        inVal = super(IPv4AddressOnlyType, self).__call__(inVal)

        errormsg = "{} is not a valid IP address".format(inVal)
        try:
            _socket.inet_pton(_socket.AF_INET, inVal)
            return inVal
        except AttributeError: # inet_pton not available
            try:
                _socket.inet_aton(inVal)
                return inVal
            except _socket.error:
                raise InvalidArgumentError(errormsg)
        except _socket.error: # not a valid address
            raise InvalidArgumentError(errormsg)

        pieces = inVal.split(".")
        if len(pieces) != 4:
            raise InvalidArgumentError(errormsg)

        try:
            pieces = [int(i) for i in pieces]
        except ValueError:
            raise InvalidArgumentError(errormsg)

        if not all([i >= 0 and i <= 255 for i in pieces]):
            raise InvalidArgumentError(errormsg)

        return inVal

    def __repr__(self):
        return "IPv4Address"

class HostnameType(StrType):
    """Type for validating hostname strings"""

    def __init__(self):
        super(HostnameType, self).__init__(allowEmpty=False, maxLength=253, whitelistedCharacters=_string.ascii_letters + _string.digits + "-.")

    def __call__(self, inVal):
        inVal = super(HostnameType, self).__call__(inVal)
        pieces = inVal.split(".")
        for piece in pieces:
            if len(piece) > 63:
                raise InvalidArgumentError("No piece of a hostname can be > 63 characters: {}".format(piece))
            if piece.startswith("-"):
                raise InvalidArgumentError("No piece of a hostname can start with '-': {}".format(piece))
        return inVal

    def __repr__(self):
        return "Hostname"

class ResolvableHostnameType(HostnameType):
    """Type for validating a string is a resolvable hostname"""

    def __call__(self, inVal):
        inVal = super(ResolvableHostnameType, self).__call__(inVal)

        try:
            _socket.gethostbyname(inVal)
        except _socket.gaierror: #Unable to resolve host name
            raise InvalidArgumentError("{} is not a resolvable hostname".format(inVal))
        return inVal

    def __repr__(self):
        return "ResolvableHostname"

class IPv4AddressType(MultiType):
    """Type for validating IPv4 address or resovable hostname"""

    def __init__(self):
        super(IPv4AddressType, self).__init__(IPv4AddressOnlyType(), ResolvableHostnameType())

    def __repr__(self):
        return "IPv4AddressOrHostname"

class IPv4SubnetType(StrType):
    """Type for validating subnets, either CIDR or network/netmask"""

    def __init__(self):
        super(IPv4SubnetType, self).__init__(allowEmpty=False, whitelistedCharacters=_string.digits + "./")

    def __call__(self, inVal):
        inVal = super(IPv4SubnetType, self).__call__(inVal)

        if "/" not in inVal:
            raise InvalidArgumentError("missing CIDR bits or netmask")

        network, mask = inVal.split("/")
        # Validate the network is a valid IP address
        network = IPv4AddressOnlyType()(network)

        # Validate the mask is either a valid IP, or an integer between 0 and 32
        if "." in mask:
            mask = IPv4AddressOnlyType()(mask)
        else:
            mask = IntegerRangeType(minValue=0, maxValue=32)(mask)

        return "{}/{}".format(network, mask)

    def __repr__(self):
        return "IPv4Subnet"

class IntegerRangeType(object):
    """Type for validating an integer within a range of values, inclusive"""

    def __init__(self, minValue=None, maxValue=None):
        self.minValue = None
        self.maxValue = None

        if minValue is not None:
            self.minValue = int(minValue)
        if maxValue is not None:
            self.maxValue = int(maxValue)

    def __call__(self, inVal):

        try:
            number = int(inVal)
        except (TypeError, ValueError):
            raise InvalidArgumentError("{} is not a valid integer".format(inVal))

        if self.minValue is not None and number < self.minValue:
            raise InvalidArgumentError("{} must be >= {}".format(number, self.minValue))

        if self.maxValue is not None and number > self.maxValue:
            raise InvalidArgumentError("{} must be <= {}".format(number, self.maxValue))

        return number

    def __repr__(self):
        return "int"

class CountType(IntegerRangeType):
    """Type for validating a count of something"""

    def __init__(self, allowZero=False):
        super(CountType, self).__init__(minValue=0 if allowZero else 1)

class PositiveIntegerType(IntegerRangeType):
    """Type for validating integers"""

    def __init__(self):
        super(PositiveIntegerType, self).__init__(minValue=0)

class PositiveNonZeroIntegerType(IntegerRangeType):
    """Type for validating integers"""

    def __init__(self):
        super(PositiveNonZeroIntegerType, self).__init__(minValue=1)

class VLANTagType(IntegerRangeType):
    """Type for validating VLAN tags"""

    def __init__(self):
        super(VLANTagType, self).__init__(minValue=1, maxValue=4095)

    def __repr__(self):
        return "VLANTag"

class MACAddressType(StrType):
    """Type for validating MAC address"""

    def __init__(self):
        super(MACAddressType, self).__init__(allowEmpty=False)

    def __call__(self, inVal):
        inVal = super(MACAddressType, self).__call__(inVal)
        inVal = inVal.lower()
        if not _re.match("[0-9a-f]{2}([-:])[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", inVal):
            raise InvalidArgumentError("{} is not a valid MAC address".format(inVal))
        return inVal

    def __repr__(self):
        return "MACAddress"

class RegExType(object):
    """Type for validating regexes"""

    def __call__(self, inVal):
        try:
            _re.compile(inVal)
        except _re.error:
            raise InvalidArgumentError("Invalid regex")
        return inVal

    def __repr__(self):
        return "RegEx"


def GetPrettiestTypeName(typeToName):
    """Get the best human representation of a type"""
    if typeToName is None:
        return "Any"
    typename = repr(typeToName)
    # Hacky
    if typename.startswith("<"):
        typename = getattr(typeToName, "__name__", str(typeToName))
    return typename
