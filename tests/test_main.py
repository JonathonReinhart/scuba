from __future__ import print_function

from nose.tools import *
from .utils import *
from unittest import TestCase
try:
    from unittest import mock
except ImportError:
    import mock

import logging
import os
import sys
from tempfile import mkdtemp, TemporaryFile
from shutil import rmtree

import scuba.__main__ as main

DOCKER_IMAGE = 'debian:8.2'

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
        # Also mock atexit.register(), so we can simulate file cleanup.

        atexit_funcs = []
        def atexit_reg(cb, *args, **kw):
            atexit_funcs.append((cb, args, kw))

        with TemporaryFile(prefix='scubatest-stdout', mode='w+t') as stdout:
            with TemporaryFile(prefix='scubatest-stderr', mode='w+t') as stderr:
                with mock.patch('atexit.register', side_effect=atexit_reg) as atexit_reg_mock:
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
                        for f, args, kw in atexit_funcs:
                            f(*args, **kw)


    def test_basic(self):
        '''Verify basic scuba functionality'''

        with open('.scuba.yml', 'w') as f:
            f.write('image: {0}\n'.format(DOCKER_IMAGE))

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

        out, err = self.run_scuba(['-v'])


        # Argparse in Python < 3.4 printed version to stderr, but
        # changed that to stdout in 3.4. We don't care where it goes.
        # https://bugs.python.org/issue18920
        check = out or err

        assert_startswith(check, 'scuba')

        ver = check.split()[1]
        assert_equal(ver, main.__version__)


    def test_no_docker(self):
        '''Verify scuba gracefully handles docker not being installed'''

        with open('.scuba.yml', 'w') as f:
            f.write('image: {0}\n'.format(DOCKER_IMAGE))

        args = ['/bin/echo', '-n', 'my output']

        old_PATH = os.environ['PATH']
        os.environ['PATH'] = ''

        try:
            _, err = self.run_scuba(args, 2)
        finally:
            os.environ['PATH'] = old_PATH

    @mock.patch('subprocess.call')
    def test_dry_run(self, subproc_call_mock):
        '''Verify scuba handles --dry-run and --verbose'''

        with open('.scuba.yml', 'w') as f:
            f.write('image: {0}\n'.format(DOCKER_IMAGE))

        args = ['--dry-run', '--verbose', '/bin/false']

        _, err = self.run_scuba(args, 42)

        assert_false(subproc_call_mock.called)

        #TODO: Assert temp files are not cleaned up?
