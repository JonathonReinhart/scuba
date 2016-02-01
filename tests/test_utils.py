from __future__ import print_function

from nose.tools import *
from unittest import TestCase

import logging
import shlex
from itertools import chain

from .utils import *

import scuba.utils


class TestUtils(TestCase):

    def _parse_cmdline(self, cmdline):
        # Strip the formatting and whitespace
        lines = [l.rstrip('\\').strip() for l in cmdline.splitlines()]

        # Split each line, and return a flattened list of arguments
        return chain.from_iterable(map(shlex.split, lines))

    def _test_format_cmdline(self, args):

        # Call the unit-under-test to get the formatted command line
        result = scuba.utils.format_cmdline(args)

        # Parse the result back out to a list of arguments
        out_args = self._parse_cmdline(result)

        # Verify that they match
        assert_seq_equal(out_args, args)


    def test_basic(self):
        '''format_cmdline works as expected'''

        self._test_format_cmdline([
            'something',
            '-a',
            '-b',
            '--long', 'option text',
            '-s', 'hort',
            'a very long argument here that will end up on its own line because it is so wide and nothing else will fit at the default width',
            'and now',
            'some', 'more', 'stuff',
            'and even more stuff',
        ])
