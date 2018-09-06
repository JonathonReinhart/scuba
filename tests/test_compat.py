 # coding=utf-8
from __future__ import print_function
from unittest import TestCase

class TestCompat(TestCase):
    def test_StringIO(self):
        from scuba.compat import StringIO
        s = StringIO()

    def test_File(self):
        from scuba.compat import File
        f = File('/etc/passwd', 'rt')
        f.we_can_add_new_attrs = True
