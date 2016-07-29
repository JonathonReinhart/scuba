# Python 2/3 compatibility

__all__ = ['File', 'StringIO']


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
