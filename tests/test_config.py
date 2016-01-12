from __future__ import print_function

from nose.tools import *
from unittest import TestCase

import logging
import os
from os.path import join, normpath
from tempfile import mkdtemp
from shutil import rmtree

import scuba.config

def assert_paths_equal(a, b):
    assert_equals(normpath(a), normpath(b))

class TestConfig(TestCase):
    def setUp(self):
        self.orig_path = os.getcwd()

        self.path = mkdtemp('scubatest')
        os.chdir(self.path)
        logging.info('Temp path: ' + self.path)

    def tearDown(self):
        rmtree(self.path)
        self.path = None

        os.chdir(self.orig_path)
        self.orig_path = None

    def test_find_config_cur_dir(self):
        with open('.scuba.yml', 'w') as f:
            f.write('image: busybox\n')

        path, rel = scuba.config.find_config()
        assert_paths_equal(path, self.path)
        assert_paths_equal(rel, '')


    def test_find_config_parent_dir(self):
        with open('.scuba.yml', 'w') as f:
            f.write('image: busybox\n')

        os.mkdir('subdir')
        os.chdir('subdir')

        # Verify our current working dir
        assert_paths_equal(os.getcwd(), join(self.path, 'subdir'))

        path, rel = scuba.config.find_config()
        assert_paths_equal(path, self.path)
        assert_paths_equal(rel, 'subdir')

    def test_find_config_way_up(self):
        with open('.scuba.yml', 'w') as f:
            f.write('image: busybox\n')

        subdirs = ['foo', 'bar', 'snap', 'crackle', 'pop']

        for sd in subdirs:
            os.mkdir(sd)
            os.chdir(sd)

        # Verify our current working dir
        assert_paths_equal(os.getcwd(), join(self.path, *subdirs))

        path, rel = scuba.config.find_config()
        assert_paths_equal(path, self.path)
        assert_paths_equal(rel, join(*subdirs))

    def test_find_config_nonexist(self):
        with assert_raises(scuba.config.ConfigError):
            scuba.config.find_config()

