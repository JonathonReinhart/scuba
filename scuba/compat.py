# Python 2/3 compatibility
import subprocess

__all__ = [
    'File',
    'StringIO',
    'check_output',
]


# StringIO
# Python 3 moved it to the 'io' package
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO


# File
# A replacement for 'open' that returns a new-style object,
# so additional attributes can be set on it.
try:
    # Python 2
    # open() returns builtin file object which has no __dict__
    class File(file):
        pass
except NameError:
    # Python 3
    # 'file' type removed, but open() returns _io.TextIOWrapper
    # which has a __dict__
    File = open


# check_output
# A replacement for subprocess.check_output() which doesn't exist in Python 2.6
# https://github.com/python/cpython/blob/v2.7.13/Lib/subprocess.py#L190
try:
    check_output = subprocess.check_output
except AttributeError:
    def check_output(*popenargs, **kwargs):
        if 'stdout' in kwargs:
            raise ValueError('stdout argument not allowed, it will be overridden.')
        process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs, **kwargs)
        output, unused_err = process.communicate()
        retcode = process.poll()
        if retcode:
            cmd = kwargs.get("args")
            if cmd is None:
                cmd = popenargs[0]
            # Python 2.6 CalledProcessError doesn't accept output arg
            raise subprocess.CalledProcessError(retcode, cmd)
        return output
