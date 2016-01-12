import os
import atexit

__all__ = ['files', 'register', 'skip']

_rmfiles = []
_skip = False

def register(path):
    '''Register a file to be removed at exit'''
    _rmfiles.append(path)

def skip(skip=True):
    '''Don't actually cleanup'''
    global _skip
    _skip = skip

def files():
    '''Get files registered for cleanup'''
    return iter(_rmfiles)

def __cleanup():
    if _skip:
        return

    for f in _rmfiles:
        try:
            os.remove(f)
        except OSError:
            pass

atexit.register(__cleanup)
