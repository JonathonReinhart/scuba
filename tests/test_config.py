 # coding=utf-8
from __future__ import print_function

from nose.tools import *
from .utils import *
from unittest import TestCase

import logging
import os
from os.path import join
from tempfile import mkdtemp
from shutil import rmtree

import scuba.config

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

    ######################################################################
    # Find config

    def test_find_config_cur_dir(self):
        '''find_config can find the config in the current directory'''
        with open('.scuba.yml', 'w') as f:
            f.write('image: busybox\n')

        path, rel = scuba.config.find_config()
        assert_paths_equal(path, self.path)
        assert_paths_equal(rel, '')


    def test_find_config_parent_dir(self):
        '''find_config cuba can find the config in the parent directory'''
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
        '''find_config can find the config way up the directory hierarchy'''
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
        '''find_config raises ConfigError if the config cannot be found'''
        assert_raises(scuba.config.ConfigError, scuba.config.find_config)

    ######################################################################
    # Load config

    def test_load_config_empty(self):
        '''load_config raises ConfigError if the config is empty'''
        with open('.scuba.yml', 'w') as f:
            pass

        assert_raises(scuba.config.ConfigError, scuba.config.load_config, '.scuba.yml')

    def test_load_unexpected_node(self):
        '''load_config raises ConfigError on unexpected config node'''
        with open('.scuba.yml', 'w') as f:
            f.write('image: busybox\n')
            f.write('unexpected_node_123456: value\n')

        assert_raises(scuba.config.ConfigError, scuba.config.load_config, '.scuba.yml')

    def test_load_config_minimal(self):
        '''load_config loads a minimal config'''
        with open('.scuba.yml', 'w') as f:
            f.write('image: busybox\n')

        config = scuba.config.load_config('.scuba.yml')
        assert_equals(config.image, 'busybox')

    def test_load_config_with_aliases(self):
        '''load_config loads a config with aliases'''
        with open('.scuba.yml', 'w') as f:
            f.write('image: busybox\n')
            f.write('aliases:\n')
            f.write('  foo: bar\n')
            f.write('  snap: crackle pop\n')

        config = scuba.config.load_config('.scuba.yml')
        assert_equals(config.image, 'busybox')
        assert_equals(len(config.aliases), 2)
        assert_seq_equal(config.aliases['foo'].script, [['bar']])
        assert_seq_equal(config.aliases['snap'].script, [['crackle', 'pop']])

    def test_load_config__no_spaces_in_aliases(self):
        '''load_config refuses spaces in aliases'''
        with open('.scuba.yml', 'w') as f:
            f.write('image: busybox\n')
            f.write('aliases:\n')
            f.write('  this has spaces: whatever\n')

        assert_raises(scuba.config.ConfigError, scuba.config.load_config, '.scuba.yml')

    def test_load_config_image_from_yaml(self):
        '''load_config loads a config using !from_yaml'''
        with open('.gitlab.yml', 'w') as f:
            f.write('image: debian:8.2\n')

        with open('.scuba.yml', 'w') as f:
            f.write('image: !from_yaml .gitlab.yml image\n')

        config = scuba.config.load_config('.scuba.yml')
        assert_equals(config.image, 'debian:8.2')

    def test_load_config_image_from_yaml_nested_keys(self):
        '''load_config loads a config using !from_yaml with nested keys'''
        with open('.gitlab.yml', 'w') as f:
            f.write('somewhere:\n')
            f.write('  down:\n')
            f.write('    here: debian:8.2\n')

        with open('.scuba.yml', 'w') as f:
            f.write('image: !from_yaml .gitlab.yml somewhere.down.here\n')

        config = scuba.config.load_config('.scuba.yml')
        assert_equals(config.image, 'debian:8.2')

    def test_load_config_image_from_yaml_nested_key_missing(self):
        '''load_config raises ConfigError when !from_yaml references nonexistant key'''
        with open('.gitlab.yml', 'w') as f:
            f.write('somewhere:\n')
            f.write('  down:\n')

        with open('.scuba.yml', 'w') as f:
            f.write('image: !from_yaml .gitlab.yml somewhere.NONEXISTANT\n')

        assert_raises(scuba.config.ConfigError, scuba.config.load_config, '.scuba.yml')

    def test_load_config_image_from_yaml_missing_file(self):
        '''load_config raises ConfigError when !from_yaml references nonexistant file'''
        with open('.scuba.yml', 'w') as f:
            f.write('image: !from_yaml .NONEXISTANT.yml image\n')

        assert_raises(scuba.config.ConfigError, scuba.config.load_config, '.scuba.yml')

    def test_load_config_image_from_yaml_unicode_args(self):
        '''load_config raises ConfigError when !from_yaml has unicode args'''
        with open('.scuba.yml', 'w') as f:
            f.write('image: !from_yaml .NONEXISTANT.yml ½\n')

        assert_raises(scuba.config.ConfigError, scuba.config.load_config, '.scuba.yml')

    def test_load_config_image_from_yaml_missing_arg(self):
        '''load_config raises ConfigError when !from_yaml has missing args'''
        with open('.gitlab.yml', 'w') as f:
            f.write('image: debian:8.2\n')

        with open('.scuba.yml', 'w') as f:
            f.write('image: !from_yaml .gitlab.yml\n')

        assert_raises(scuba.config.ConfigError, scuba.config.load_config, '.scuba.yml')

    ######################################################################
    # process_command

    def test_process_command_empty(self):
        '''process_command handles no aliases and an empty command'''
        cfg = scuba.config.ScubaConfig(
                image = 'na',
                )
        result = cfg.process_command([])
        assert_equal(result.script, None)


    def test_process_command_no_aliases(self):
        '''process_command handles no aliases'''
        cfg = scuba.config.ScubaConfig(
                image = 'na',
                )
        result = cfg.process_command(['cmd', 'arg1', 'arg2'])
        assert_equal(result.script, [['cmd', 'arg1', 'arg2']])

    def test_process_command_aliases_unused(self):
        '''process_command handles unused aliases'''
        cfg = scuba.config.ScubaConfig(
                image = 'na',
                aliases = dict(
                    apple = 'banana',
                    cat = 'dog',
                    ),
                )
        result = cfg.process_command(['cmd', 'arg1', 'arg2'])
        assert_equal(result.script, [['cmd', 'arg1', 'arg2']])

    def test_process_command_aliases_used_noargs(self):
        '''process_command handles aliases with no args'''
        cfg = scuba.config.ScubaConfig(
                image = 'na',
                aliases = dict(
                    apple = 'banana',
                    cat = 'dog',
                    ),
                )
        result = cfg.process_command(['apple', 'arg1', 'arg2'])
        assert_equal(result.script, [['banana', 'arg1', 'arg2']])

    def test_process_command_aliases_used_withargs(self):
        '''process_command handles aliases with args'''
        cfg = scuba.config.ScubaConfig(
                image = 'na',
                aliases = dict(
                    apple = 'banana cherry "pie is good"',
                    cat = 'dog',
                    ),
                )
        result = cfg.process_command(['apple', 'arg1', 'arg2'])
        assert_equal(result.script, [['banana', 'cherry', 'pie is good', 'arg1', 'arg2']])

    def test_process_command_multiline_aliases_used(self):
        '''process_command handles multiline aliases'''
        cfg = scuba.config.ScubaConfig(
                image = 'na',
                aliases = dict(
                    apple = dict(script=[
                        'banana cherry "pie is good"',
                        'so is peach',
                    ]),
                    cat = 'dog',
                    ),
                )
        result = cfg.process_command(['apple'])
        assert_equal(result.script, [
            ['banana', 'cherry', 'pie is good'],
            ['so', 'is', 'peach'],
        ])

    def test_process_command_multiline_aliases_forbid_user_args(self):
        '''process_command raises ConfigError when args are specified with multiline aliases'''
        cfg = scuba.config.ScubaConfig(
                image = 'na',
                aliases = dict(
                    apple = dict(script=[
                        'banana cherry "pie is good"',
                        'so is peach',
                    ]),
                    cat = 'dog',
                    ),
                )
        assert_raises(scuba.config.ConfigError, cfg.process_command, ['apple', 'ARGS', 'NOT ALLOWED'])

    def test_process_command_alias_overrides_image(self):
        '''aliases can override the image'''
        cfg = scuba.config.ScubaConfig(
                image = 'default',
                aliases = dict(
                    apple = dict(
                        script = [
                            'banana cherry "pie is good"',
                            'so is peach',
                        ],
                        image = 'overridden',
                    ),
                ),
            )
        result = cfg.process_command(['apple'])
        assert_equal(result.image, 'overridden')


    ############################################################################
    # Hooks

    def test_hooks_mixed(self):
        '''hooks of mixed forms are valid'''
        with open('.scuba.yml', 'w') as f:
            f.write('''
                image: na
                hooks:
                  root:
                    script:
                      - echo "This runs before we switch users"
                      - id
                  user: id
                ''')

        config = scuba.config.load_config('.scuba.yml')

        assert_seq_equal(
            config.hooks.get('root'),
            ['echo "This runs before we switch users"', 'id'])

        assert_seq_equal(
            config.hooks.get('user'),
            ['id'])

    def test_hooks_invalid_list(self):
        '''hooks with list not under "script" key are invalid'''
        with open('.scuba.yml', 'w') as f:
            f.write('''
                image: na
                hooks:
                  user:
                    - this list should be under
                    - a 'script'
                ''')

        assert_raises(scuba.config.ConfigError, scuba.config.load_config, '.scuba.yml')

    # TODO: Any reason this shouldn't be valid?
    def test_hooks_invalid_script_type(self):
        '''hooks with string "script" are invalid'''
        with open('.scuba.yml', 'w') as f:
            f.write('''
                image: na
                hooks:
                  user:
                    script: this should be in a list under script
                ''')

        assert_raises(scuba.config.ConfigError, scuba.config.load_config, '.scuba.yml')

    def test_hooks_missing_script(self):
        '''hooks with dict, but missing "script" are invalid'''
        with open('.scuba.yml', 'w') as f:
            f.write('''
                image: na
                hooks:
                  user:
                    not_script: missing "script" key
                ''')

        assert_raises(scuba.config.ConfigError, scuba.config.load_config, '.scuba.yml')
