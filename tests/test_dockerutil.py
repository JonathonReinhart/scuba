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

    def test_get_images_success__no_images(self):
        '''get_images works when no images are present'''

        def mocked_communicate():
            stdout = b'''\
REPOSITORY                 TAG                 IMAGE ID            CREATED             VIRTUAL SIZE
'''
            return stdout, b''

        def mocked_popen(*_, **__):
            mock_obj = mock.MagicMock()
            mock_obj.returncode = 0
            mock_obj.communicate = mocked_communicate
            return mock_obj

        with mock.patch('scuba.dockerutil.Popen', side_effect=mocked_popen) as popen_mock:
            images = uut.get_images()
            assert_seq_equal(images, [])

    def test_get_images_success__multiple_images(self):
        '''get_images works when many images are present'''
        def mocked_communicate():
            stdout = b'''\
REPOSITORY                 TAG                 IMAGE ID            CREATED             VIRTUAL SIZE
busybox                    latest              9036dcd43f39        5 weeks ago         1.22 MB
debian                     buster              47e3636410d0        7 weeks ago         114.1 MB
debian                     latest              47e3636410d0        7 weeks ago         114.1 MB
<none>                     <none>              eccd470b4841        6 months ago        78.02 MB
ubuntu                     14.04               70ae2f58e361        13 months ago       188.1 MB
ubuntu                     latest              9267595be189        18 months ago       85.85 MB
dzwicker/docker-youtrack   2017.3              207053cbe08d        2 years ago         891.9 MB
mysql                      5.7.17              5f40bbafa11a        3 years ago         400.2 MB
ubuntu-build-image         latest              fd12deb79317        4 years ago         544.8 MB
gitlab-runner-build        cffb5c7             e81d89132343        4 years ago         42.69 MB
gitlab-runner-cache        cffb5c7             2411894973e8        4 years ago         1.114 MB
gitlab-runner-service      cffb5c7             0acfeb10d76a        4 years ago         4.794 MB
debian                     8.2                 140f9bdfeb97        4 years ago         125.1 MB
'''
            return stdout, b''

        def mocked_popen(*_, **__):
            mock_obj = mock.MagicMock()
            mock_obj.returncode = 0
            mock_obj.communicate = mocked_communicate
            return mock_obj

        with mock.patch('scuba.dockerutil.Popen', side_effect=mocked_popen) as popen_mock:
            images = uut.get_images()
            assert_seq_equal(
                images,
                [
                    'busybox', 'debian:buster', 'debian', 'eccd470b4841', 'ubuntu:14.04', 'ubuntu',
                    'dzwicker/docker-youtrack:2017.3', 'mysql:5.7.17', 'ubuntu-build-image',
                    'gitlab-runner-build:cffb5c7', 'gitlab-runner-cache:cffb5c7', 'gitlab-runner-service:cffb5c7',
                    'debian:8.2',
                ]
            )

    def test_get_images__popen_failure(self):
        '''get_images fails because of Popen error'''
        def mocked_communicate():
            return b'', b'This is a pre-canned error'

        def mocked_popen(*_, **__):
            mock_obj = mock.MagicMock()
            mock_obj.returncode = 1
            mock_obj.communicate = mocked_communicate
            return mock_obj

        with self.assertRaises(uut.DockerError):
            with mock.patch('scuba.dockerutil.Popen', side_effect=mocked_popen) as popen_mock:
                uut.get_images()

    def test_get_images__image_parsing_error(self):
        '''get_images fails to parse an image name'''

        def mocked_communicate():
            stdout = b'''\
REPOSITORY                 TAG                 IMAGE ID            CREATED             VIRTUAL SIZE
busybox                    latest              invalid_id          5 weeks ago         1.22 MB
'''
            return stdout, b''

        def mocked_popen(*_, **__):
            mock_obj = mock.MagicMock()
            mock_obj.returncode = 0
            mock_obj.communicate = mocked_communicate
            return mock_obj

        with self.assertRaises(uut.DockerError):
            with mock.patch('scuba.dockerutil.Popen', side_effect=mocked_popen) as popen_mock:
                uut.get_images()

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
