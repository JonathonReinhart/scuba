import os
from nose.tools import *
from os.path import normpath
import tempfile
import shutil

def assert_set_equal(a, b):
    assert_equal(set(a), set(b))

def assert_seq_equal(a, b):
    assert_equals(list(a), list(b))

def assert_paths_equal(a, b):
    assert_equals(normpath(a), normpath(b))

def assert_str_equalish(exp, act):
    exp = str(exp).strip()
    act = str(act).strip()
    assert_equal(exp, act)

def assert_startswith(s, prefix):
    s = str(s)
    prefix = str(prefix)
    if not s.startswith(prefix):
        raise AssertionError('"{0}" does not start with "{1}"'
                .format(escape_str(s), prefix))

def escape_str(s):
    # Python 3 won't let us use s.encode('string_escape') :-(
    replacements = [
        ('\a', '\\a'),
        ('\b', '\\b'),
        ('\f', '\\f'),
        ('\n', '\\n'),
        ('\r', '\\r'),
        ('\t', '\\t'),
        ('\v', '\\v'),
    ]

    for r in replacements:
        s = s.replace(*r)
    return s

def make_executable(path):
    mode = os.stat(path).st_mode
    mode |= (mode & 0o444) >> 2    # copy R bits to X
    os.chmod(path, mode)


# http://stackoverflow.com/a/8389373/119527
class PseudoTTY(object):
    def __init__(self, underlying):
        self.__underlying = underlying
    def __getattr__(self, name):
        return getattr(self.__underlying, name)
    def isatty(self):
        return True


class InTempDir(object):
    def __init__(self, suffix='', prefix='tmp', delete=True):
        self.delete = delete
        self.temp_path = tempfile.mkdtemp(suffix=suffix, prefix=prefix)

    def __enter__(self):
        self.orig_path = os.getcwd()
        os.chdir(self.temp_path)
        return self

    def __exit__(self, *exc_info):
        # Restore the working dir and cleanup the temp one
        os.chdir(self.orig_path)
        if self.delete:
            shutil.rmtree(self.temp_path)
