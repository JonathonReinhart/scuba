# Python 2/3 compatibility
import subprocess
import sys

__all__ = [
    'builtins_module_name',
    'File',
    'StringIO',
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


# https://stackoverflow.com/a/9047762
if sys.version_info >= (3,):
    builtins_module_name = 'builtins'
else:
    builtins_module_name = '__builtin__'
