from __future__ import print_function

from nose.tools import *
from unittest import TestCase
try:
    from unittest import mock
except ImportError:
    import mock

import logging
import os
import sys
from os.path import join, normpath
from tempfile import mkdtemp, TemporaryFile
from shutil import rmtree

import scuba.__main__ as main

def assert_str_equalish(exp, act):
    exp = str(exp).strip()
    act = str(act).strip()
    assert_equal(exp, act)

def assert_startswith(s, prefix):
    s = str(s)
    prefix = str(prefix)
    if not s.startswith(prefix):
        raise AssertionError('"{0}" does not start with "{1}"'
                .format(s.encode('string_escape'), prefix))


class BetterAssertRaisesMixin(object):
    def assertRaises2(self, exc_type, func, *args, **kwargs):
        try:
            func(*args, **kwargs)
        except exc_type as e:
            return e
        else:
            self.fail('"{0}" was expected to throw "{1}" exception'
                          .format(func.__name__, exception_type.__name__))


class TestMain(TestCase, BetterAssertRaisesMixin):
    def setUp(self):
        # Run each test in its own temp directory
        self.orig_path = os.getcwd()
        self.path = mkdtemp('scubatest')
        os.chdir(self.path)
        logging.info('Temp path: ' + self.path)


    def tearDown(self):
        # Restore the working dir and cleanup the temp one
        rmtree(self.path)
        self.path = None
        os.chdir(self.orig_path)
        self.orig_path = None


    def run_scuba(self, args, exp_retval=0):
        '''Run scuba, checking its return value

        Returns scuba/docker stdout data.
        '''

        # Capture both scuba and docker's stdout/stderr,
        # just as the user would see it.

        with TemporaryFile(prefix='scubatest-stdout', mode='w+t') as stdout:
            with TemporaryFile(prefix='scubatest-stderr', mode='w+t') as stderr:
                old_stdout = sys.stdout
                old_stderr = sys.stderr

                sys.stdout = stdout
                sys.stderr = stderr

                try:
                    # Call scuba's main(), and expect it to exit() with a given return code.
                    exc = self.assertRaises2(SystemExit, main.main, argv = args)
                    assert_equal(exp_retval, exc.args[0])

                    stdout.seek(0)
                    stderr.seek(0)
                    return stdout.read(), stderr.read()

                finally:
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr


    def test_basic(self):
        '''Verify basic scuba functionality'''

        with open('.scuba.yml', 'w') as f:
            f.write('image: debian:8.2\n')

        args = ['/bin/echo', '-n', 'my output']
        out, _ = self.run_scuba(args)

        assert_str_equalish('my output', out)


    def test_config_error(self):
        '''Verify config errors are handled gracefully'''

        with open('.scuba.yml', 'w') as f:
            f.write('invalid_key: is no good\n')

        # ConfigError -> exit(128)
        self.run_scuba([], 128)


    def test_version(self):
        '''Verify scuba prints its version for -v'''

        _, err = self.run_scuba(['-v'])

        assert_startswith(err, 'scuba')

        ver = err.split()[1]
        assert_equal(ver, main.__version__)
