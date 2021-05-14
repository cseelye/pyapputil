#!/usr/bin/env python
"""
Helpers for network tasks
"""
import dns
import os
import platform
import posixpath
import requests
try:
    from urlparse import urlsplit
    from urllib import unquote
except ImportError: # Python 3
    from urllib.parse import urlsplit, unquote

from .exceptutil import ApplicationError
from .logutil import GetLogger
from . import shellutil

LOCAL_SYS = platform.system()

LOCAL_SYS = platform.system()

class HostNotFoundError(ApplicationError):
    """Exception for NXDOMAIN errors"""

class ServfailError(ApplicationError):
    """Exception for SERVFAIL errors"""

def ResolveHostname(hostname, nameserver):
    """
    Attempt to lookup a hostname to IP mapping

    Args:
        hostname:       the hostname to resolve
        nameserver:     the DNS server to query

    Returns:
        A list of IP addresses the hostname resolves to (list of str)
    """
    res = dns.resolver.Resolver()
    res.nameservers = [nameserver]
    try:
        ans = res.query(hostname)
        return [record.address for record in ans]
    except dns.resolver.NXDOMAIN as ex:
        raise HostNotFoundError("Host {} not found".format(hostname), innerException=ex)
    except dns.exception.DNSException as ex:
        raise ServfailError("Error querying DNS: {}".format(ex), innerException=ex)

def Ping(address):
    """
    Ping a host

    Args:
        address:    an IP address or resolvable hostname to ping

    Returns:
        Boolean true if the address can be pinged, false if not
    """
    if LOCAL_SYS == "Windows":
        command = "ping -n 2 {}".format(address)
    elif LOCAL_SYS == "Darwin":
        command = "ping -i 1 -c 3 -W 2000 {}".format(address)
    else:
        command = "ping -i 0.2 -c 5 -W 2 {}".format(address)

    retcode, _, _ = shellutil.Shell(command)
    if retcode == 0:
        return True
    else:
        return False

def GetUrlFilename(url):
    """
    Get the filename component of a URL

    Args:
        url:    the URL to get filename from (str)

    Returns:
        The filename (str)
    """
    urlpath = urlsplit(url).path
    basename = posixpath.basename(unquote(urlpath))
    if (os.path.basename(basename) != basename or
        unquote(posixpath.basename(urlpath)) != basename):
        raise ValueError  # reject '%2f' or 'dir%5Cbasename.ext' on Windows
    return basename

def DownloadFile(url, localPath=None, username=None, password=None, timeout=300):
    """
    Download a file from a given URL

    Args:
        url:        remote path of the file to download (str)
        localPath:  path/filename to save the remote file to (str)
        username:   username if authentication is required (str)
        password:   password if authentication is required (str)
        timeout:    timeout in seconds for the download process (int)
    """
    log = GetLogger()
    if not localPath:
        localPath = GetUrlFilename(url)
    auth = None
    if username and password:
        auth = (username, password)
    log.debug("Downloading file [{}] to [{}]".format(url, localPath))
    with requests.get(url, auth=auth, timeout=timeout, stream=True) as req:
        with open(localPath, "wb") as fh:
            for chunk in req.iter_content(chunk_size=16384):
                if chunk:
                    fh.write(chunk)
