 # coding=utf-8
from unittest import TestCase
from .utils import RedirStd

import sys
import argparse
from scuba.compat import StringIO

# UUT
from scuba.cmdlineargs import ListOptsAction

class TestConfig(TestCase):

    def __test_ListOptsAction(self, ap, expected_opts):
        # Verify that passing --list-opts will cause all non-suppressed
        # command-line options to be printed to stdout, and sys.exit is called.
        with RedirStd(stdout=StringIO()) as r:
            ap.add_argument('--list-opts', action=ListOptsAction, help=argparse.SUPPRESS)
            self.assertRaises(SystemExit, ap.parse_args, ['--list-opts'])

        opts = r.stdout.getvalue().split()
        self.assertEqual(expected_opts, opts)

    def test_ListOptsAction(self):
        ap = argparse.ArgumentParser()
        ap.add_argument('-n')
        ap.add_argument('-z', '--zzz')
        ap.add_argument('-b', '--bbb')
        ap.add_argument('-a', '--aaa')

        # We expect to see all options, including automatically-added --help.
        # We expect long options if they are present, or short options otherwise.
        expected = ['--aaa', '--bbb', '--help', '-n', '--zzz']
        self.__test_ListOptsAction(ap, expected)

    def test_ListOptsAction_no_opts(self):
        ap = argparse.ArgumentParser()
        ap.add_argument('foo')
        expected = ['--help']
        self.__test_ListOptsAction(ap, expected)
