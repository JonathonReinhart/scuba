 # coding=utf-8
from nose.tools import *
from .utils import *
from unittest import TestCase
from unittest import mock

import subprocess

import scuba.dockerutil as uut

class TestDockerutil(TestCase):
    def test_get_image_command_success(self):
        '''get_image_command works'''
        assert_true(uut.get_image_command('debian:8.2'))

    def test_get_image_command_bad_image(self):
        '''get_image_command raises an exception for a bad image name'''
        with self.assertRaises(uut.DockerError):
            uut.get_image_command('nosuchimageZZZZZZZZ')

    def test_get_image_no_docker(self):
        '''get_image_command raises an exception if docker is not installed'''

        real_Popen = subprocess.Popen
        def mocked_popen(popen_args, *args, **kw):
            assert_equal(popen_args[0], 'docker')
            popen_args[0] = 'dockerZZZZ'
            return real_Popen(popen_args, *args, **kw)

        with mock.patch('subprocess.Popen', side_effect=mocked_popen) as popen_mock:
            with self.assertRaises(uut.DockerError):
                uut.get_image_command('n/a')


    def _test_get_images(self, stdout, returncode=0):
        def mocked_run(*args, **kwargs):
            mock_obj = mock.MagicMock()
            mock_obj.returncode = returncode
            mock_obj.stdout = stdout
            return mock_obj

        with mock.patch('scuba.dockerutil.run', side_effect=mocked_run) as run_mock:
            return uut.get_images()


    def test_get_images_success__no_images(self):
        '''get_images works when no images are present'''
        images = self._test_get_images('')
        assert_seq_equal(images, [])

    def test_get_images_success__multiple_images(self):
        '''get_images works when many images are present'''
        output = '''\
busybox
busybox:latest
debian
debian:buster
debian:latest
scuba/scratch
scuba/scratch:latest
'''
        images = self._test_get_images(output)
        assert_seq_equal(
                images,
                [
                    'busybox',
                    'busybox:latest',
                    'debian',
                    'debian:buster',
                    'debian:latest',
                    'scuba/scratch',
                    'scuba/scratch:latest',
                ]
            )

    def test_get_images__failure(self):
        '''get_images fails because of error'''
        with self.assertRaises(uut.DockerError):
            self._test_get_images('This is a pre-canned error', 1)


    def test__get_image_command__pulls_image_if_missing(self):
        '''get_image_command pulls an image if missing'''
        image = 'busybox:latest'

        # First remove the image
        subprocess.call(['docker', 'rmi', image])

        # Now try to get the image's Command
        result = uut.get_image_command(image)

        # Should return a non-empty string
        self.assertTrue(result)

    def test_get_image_entrypoint(self):
        '''get_image_entrypoint works'''
        result = uut.get_image_entrypoint('scuba/entrypoint-test')
        self.assertEqual(1, len(result))
        assert_str_equalish('/entrypoint.sh', result[0])

    def test_get_image_entrypoint__none(self):
        '''get_image_entrypoint works for image with no entrypoint'''
        result = uut.get_image_entrypoint('debian')
        self.assertEqual(None, result)


    def test_make_vol_opt_no_opts(self):
        assert_equal(
                uut.make_vol_opt('/hostdir', '/contdir'),
                '--volume=/hostdir:/contdir'
                )

    def test_make_vol_opt_one_opt(self):
        assert_equal(
                uut.make_vol_opt('/hostdir', '/contdir', 'ro'),
                '--volume=/hostdir:/contdir:ro'
                )

    def test_make_vol_opt_multi_opts(self):
        assert_equal(
                uut.make_vol_opt('/hostdir', '/contdir', ['ro', 'z']),
                '--volume=/hostdir:/contdir:ro,z'
                )
