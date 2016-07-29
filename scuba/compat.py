# Python 2/3 compatibility

__all__ = ['StringIO']


# StringIO
# Python 3 moved it to the 'io' package
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
