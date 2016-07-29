 # coding=utf-8
from __future__ import print_function
from unittest import TestCase

class TestCompat(TestCase):
    def test_StringIO(self):
        from scuba.compat import StringIO
        s = StringIO()
