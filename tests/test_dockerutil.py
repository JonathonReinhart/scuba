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
