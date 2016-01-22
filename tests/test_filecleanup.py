from __future__ import print_function

from nose.tools import *
from unittest import TestCase
try:
    from unittest import mock
except ImportError:
    import mock

from scuba.filecleanup import FileCleanup

def assert_set_equal(a, b):
    assert_equal(set(a), set(b))


class TestFilecleanup(TestCase):

    @mock.patch('os.remove')
    def test_files_tracked(self, os_remove_mock):
        '''FileCleanup.files works'''

        fc = FileCleanup()
        fc.register('foo.txt')
        fc.register('bar.bin')

        assert_set_equal(fc.files, ['foo.txt', 'bar.bin'])
        

    @mock.patch('os.remove')
    def test_basic_usage(self, os_remove_mock):
        '''FileCleanup removes one file'''

        fc = FileCleanup()
        fc.register('foo.txt')
        fc.cleanup()

        os_remove_mock.assert_any_call('foo.txt') 

    
    @mock.patch('os.remove')
    def test_multiple_files(self, os_remove_mock):
        '''FileCleanup removes multiple files'''

        fc = FileCleanup()
        fc.register('foo.txt')
        fc.register('bar.bin')
        fc.register('/something/snap.crackle')
        fc.cleanup()

        os_remove_mock.assert_any_call('bar.bin') 
        os_remove_mock.assert_any_call('foo.txt') 
        os_remove_mock.assert_any_call('/something/snap.crackle')


    @mock.patch('os.remove')
    def test_multiple_files(self, os_remove_mock):
        '''FileCleanup ignores os.remove() errors'''

        def os_remove_se(path):
            if path == 'INVALID':
                raise OSError('path not found')

        os_remove_mock.side_effect = os_remove_se

        fc = FileCleanup()
        fc.register('foo.txt')
        fc.register('bar.bin')
        fc.register('INVALID')
        fc.cleanup()

        os_remove_mock.assert_any_call('bar.bin') 
        os_remove_mock.assert_any_call('foo.txt') 

        assert_set_equal(fc.files, [])
