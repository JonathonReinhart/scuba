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

    def test_check_output_works(self):
        from scuba.compat import check_output
        msg = 'hello world'
        out = check_output(['/bin/echo', '-n', msg])
        out = out.decode()
        self.assertEqual(out, msg)

    def test_check_output_raises(self):
        from scuba.compat import check_output
        from subprocess import CalledProcessError

        def do_it():
            check_output(['/bin/false'])
        self.assertRaises(CalledProcessError, do_it)
