#!/usr/bin/env python
"""This module provides various utility classes and functions"""

from past.builtins import basestring as _basestring
import calendar as _calendar
import datetime as _datetime
import json as _json
import os as _os
import time as _time


# ===================================================================================================
#  Time manipulation
# ===================================================================================================

class LocalTimezone(_datetime.tzinfo):
    """Class representing the time zone of the machine we are currently running on"""

    def __init__(self):
        super(LocalTimezone, self).__init__()
        self.STDOFFSET = _datetime.timedelta(seconds = -_time.timezone)
        if _time.daylight:
            self.DSTOFFSET = _datetime.timedelta(seconds = -_time.altzone)
        else:
            self.DSTOFFSET = self.STDOFFSET
        self.DSTDIFF = self.DSTOFFSET - self.STDOFFSET

    def utcoffset(self, dt):
        if self._isdst(dt):
            return self.DSTOFFSET
        else:
            return self.STDOFFSET

    def dst(self, dt):
        if self._isdst(dt):
            return self.DSTDIFF
        else:
            return _datetime.timedelta(0)

    def tzname(self, dt):
        return _time.tzname[self._isdst(dt)]

    def _isdst(self, dt):
        """check if this _timezone is in daylight savings _time"""
        tt = (dt.year, dt.month, dt.day,
              dt.hour, dt.minute, dt.second,
              dt.weekday(), 0, 0)
        stamp = _time.mktime(tt)
        tt = _time.localtime(stamp)
        return tt.tm_isdst > 0

#pylint: disable=unused-argument
class UTCTimezone(_datetime.tzinfo):
    """Class representing UTC time"""

    def utcoffset(self, dt):
        return _datetime.timedelta(0)

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return _datetime.timedelta(0)
#pylint: enable=unused-argument

def ParseDateTime(timeString):
    """
    Parse a string into a _datetime

    Args:
        timeString: the string containing a parsable date/time

    Returns:
        A datetime object corresponding to the date/time in the string
    """

    known_formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",    # ISO format with UTC timezone
        "%Y-%m-%dT%H:%M:%SZ",       # ISO format without fractional seconds and UTC timezone
        "%Y%m%dT%H:%M:%SZ",
        "%b %d %H:%M:%S"            # syslog/date format
    ]
    parsed = None
    for fmt in known_formats:
        try:
            parsed = _datetime.datetime.strptime(timeString, fmt)
            break
        except ValueError: pass

    if parsed.year == 1900:
        parsed = parsed.replace(year=_datetime.datetime.now().year)

    return parsed

def ParseTimestamp(timeString):
    """
    Parse a string into a unix timestamp

    Args:
        timeString: the string containing a parsable date/time

    Returns:
        An integer timestamp corresponding to the date/time in the string
    """
    date_obj = ParseDateTime(timeString)
    if (date_obj != None):
        timestamp = _calendar.timegm(date_obj.timetuple())
        if timestamp <= 0:
            timestamp = _calendar.timegm(date_obj.utctimetuple())
        return timestamp
    else:
        return 0

def ParseTimestampHiRes(timeString):
    """
    Parse a string into a unix timestamp with floating point microseconds

    Args:
        timeString: the string containing a parsable date/time

    Returns:
        An floating point timestamp corresponding to the date/time in the string
    """
    date_obj = ParseDateTime(timeString)
    if (date_obj != None):
        return (_calendar.timegm(date_obj.timetuple()) + date_obj.microsecond)
    else:
        return 0

def TimestampToStr(timestamp, formatString = "%Y-%m-%d %H:%M:%S", timeZone = LocalTimezone()):
    """
    Convert a _timestamp to a human readable string

    Args:
        _timeStamp:      the _timestamp to convert
        formatString:   the format to convert to
        _timeZone:       the _time zone to convert to

    Returns:
        A string containing the date/_time in the requested format and _time zone
    """
    display_time = _datetime.datetime.fromtimestamp(timestamp, timeZone)
    return display_time.strftime(formatString)

def SecondsToElapsedStr(seconds):
    """
    Convert an integer number of seconds into elapsed time format (D-HH:MM:SS)

    Args:
        seconds:    the total number of seconds (int)

    Returns:
        A formatted elapsed time (str)
    """
    if isinstance(seconds, _basestring):
        return seconds

    delta = _datetime.timedelta(seconds=seconds)
    return TimeDeltaToStr(delta)

def TimeDeltaToStr(timeDelta):
    """
    Convert a timedelta object to an elapsed time format (D-HH:MM:SS)

    Args:
        timeDelta:  a timedelta object containing the total time (datetime.timedelta)

    Returns:
         Formatted elapsed time (str)
    """
    days = timeDelta.days
    hours = 0
    minutes = 0
    seconds = timeDelta.seconds
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

    return time_str

# ===================================================================================================
#  Pretty formatting
# ===================================================================================================

def HumanizeBytes(totalBytes, precision=1, suffix=None):
    """
    Convert a number of bytes into the appropriate pretty kiB, MiB, etc.

    Args:
        totalBytes: the number to convert
        precision:  how many decimal numbers of precision to preserve
        suffix:     use this suffix (kiB, MiB, etc.) instead of automatically determining it

    Returns:
        The prettified string version of the input
    """
    if (totalBytes == None):
        return "0 B"

    converted = float(totalBytes)
    suffix_index = 0
    suffix_list = ['B', 'kiB', 'MiB', 'GiB', 'TiB']

    while (abs(converted) >= 1000):
        converted /= 1024.0
        suffix_index += 1
        if suffix_list[suffix_index] == suffix:
            break

    return "{0:.{1}f} {2}".format(converted, precision, suffix_list[suffix_index])

def HumanizeDecimal(number, precision=1, suffix=None):
    """
    Convert a number into the appropriate pretty k, M, G, etc.

    Args:
        totalBytes: the number to convert
        precision:  how many decimal numbers of precision to preserve
        suffix:     use this suffix (k, M, etc.) instead of automatically determining it

    Returns:
        The prettified string version of the input
    """
    if (number == None):
        return "0"

    if (abs(number) < 1000):
        return str(number)

    converted = float(number)
    suffix_index = 0
    suffix_list = [' ', 'k', 'M', 'G', 'T']

    while (abs(converted) >= 1000):
        converted /= 1000.0
        suffix_index += 1
        if suffix_list[suffix_index] == suffix: break

    return "{:.{}f {}}".format(converted, precision, suffix_list[suffix_index])

def HumanizeWWN(hexWWN):
    """Convert a hex WWN (0x10000090fa34ad72) to a pretty format (10:00:00:90:fa:34:ad:72)

    Args:
        hexWWN: the WWN in hex format

    Returns:
        The prettified string version of the input
    """
    pretty = ''
    if hexWWN.startswith('0x'):
        start_index = 2
    else:
        start_index = 0
    for i in range(start_index, 2*8+2, 2):
        pretty += ':' + hexWWN[i:i+2]
    return pretty.strip(":")

def PrettyJSON(obj):
    """
    Get a pretty printed representation of an object

    Args:
        obj:    a dictionary to pretty-fy (dict)

    Returns:
        A string of pretty JSON (str)
    """
    return _json.dumps(obj, indent=2, sort_keys=True)

# ===================================================================================================
#  Misc
# ===================================================================================================

def GetFilename(baseName):
    """
    Get a unique filename that does not already exist. The name is generated by appending a number to the end of baseName

    Args:
        baseName:   the name to start from
    """
    filename = baseName
    idx = 0
    while _os.path.exists(filename):
        idx += 1
        filename = "{}.{}".format(baseName, idx)
    return filename

def EnsureKeys(dictionary, keyList, defaultValue=None):
    """
    Ensure that the given dictionary contains the given keys.
    If the dict does not have the key, create it with the given default value

    Args:
        dictionary:     the dict to operate on (dict)
        keyList:        the keys to ensure (list of str)
        defaultValue    the default value to set if the key does not exist
    """
    for keyname in keyList:
        if keyname not in dictionary:
            dictionary[keyname] = defaultValue
