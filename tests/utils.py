import os
import sys
from os.path import normpath
import tempfile
import shutil
import unittest
import logging
from unittest import mock


def assert_seq_equal(a, b):
    assert list(a) == list(b)

def assert_paths_equal(a, b):
    assert normpath(a) == normpath(b)

def assert_str_equalish(exp, act):
    exp = str(exp).strip()
    act = str(act).strip()
    assert exp == act

def make_executable(path):
    mode = os.stat(path).st_mode
    mode |= (mode & 0o444) >> 2    # copy R bits to X
    os.chmod(path, mode)

def mocked_os_env(**env):
    return mock.patch('os.getenv', side_effect=env.get)


def mock_open():
    real_open = open
    def mocked_open(*args, **kwargs):
        return real_open(*args, **kwargs)

    return mock.patch('builtins.open', side_effect=mocked_open)


# http://stackoverflow.com/a/8389373/119527
class PseudoTTY:
    def __init__(self, underlying):
        self.__underlying = underlying
    def __getattr__(self, name):
        return getattr(self.__underlying, name)
    def isatty(self):
        return True


def skipUnlessTty():
    return unittest.skipUnless(sys.stdin.isatty(),
            "Can't test docker tty if not connected to a terminal")


class InTempDir:
    def __init__(self, suffix='', prefix='tmp', dir=None, delete=True):
        self.delete = delete
        self.temp_path = tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir)

    def __enter__(self):
        self.orig_path = os.getcwd()
        os.chdir(self.temp_path)
        return self

    def __exit__(self, *exc_info):
        # Restore the working dir and cleanup the temp one
        os.chdir(self.orig_path)
        if self.delete:
            shutil.rmtree(self.temp_path)
