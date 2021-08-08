 # coding=utf-8
from .utils import *
import pytest

import logging
import os
from os.path import join
from shutil import rmtree
import shlex

import scuba.config


class TestCommonScriptSchema:
    def test_simple(self):
        '''Simple form: value is a string'''
        node = 'foo'
        result = scuba.config._process_script_node(node, 'dontcare')
        assert result == ['foo']

    def test_script_key_string(self):
        '''Value is a mapping: script is a string'''
        node = dict(
            script = 'foo',
            otherkey = 'other',
        )
        result = scuba.config._process_script_node(node, 'dontcare')
        assert result == ['foo']

    def test_script_key_list(self):
        '''Value is a mapping: script is a list'''
        node = dict(
            script = [
                'foo',
                'bar',
            ],
            otherkey = 'other',
        )
        result = scuba.config._process_script_node(node, 'dontcare')
        assert result == ['foo', 'bar']

    def test_script_key_mapping_invalid(self):
        '''Value is a mapping: script is a mapping (invalid)'''
        node = dict(
            script = dict(
                whatisthis = 'idontknow',
            ),
        )
        with pytest.raises(scuba.config.ConfigError):
            scuba.config._process_script_node(node, 'dontcare')


@pytest.mark.usefixtures("in_tmp_path")
class TestConfig:

    ######################################################################
    # Find config

    def test_find_config_cur_dir(self, in_tmp_path):
        '''find_config can find the config in the current directory'''
        with open('.scuba.yml', 'w') as f:
            f.write('image: busybox\n')

        path, rel, _ = scuba.config.find_config()
        assert_paths_equal(path, in_tmp_path)
        assert_paths_equal(rel, '')


    def test_find_config_parent_dir(self, in_tmp_path):
        '''find_config cuba can find the config in the parent directory'''
        with open('.scuba.yml', 'w') as f:
            f.write('image: busybox\n')

        os.mkdir('subdir')
        os.chdir('subdir')

        # Verify our current working dir
        assert_paths_equal(os.getcwd(), in_tmp_path.joinpath('subdir'))

        path, rel, _ = scuba.config.find_config()
        assert_paths_equal(path, in_tmp_path)
        assert_paths_equal(rel, 'subdir')

    def test_find_config_way_up(self, in_tmp_path):
        '''find_config can find the config way up the directory hierarchy'''
        with open('.scuba.yml', 'w') as f:
            f.write('image: busybox\n')

        subdirs = ['foo', 'bar', 'snap', 'crackle', 'pop']

        for sd in subdirs:
            os.mkdir(sd)
            os.chdir(sd)

        # Verify our current working dir
        assert_paths_equal(os.getcwd(), in_tmp_path.joinpath(*subdirs))

        path, rel, _ = scuba.config.find_config()
        assert_paths_equal(path, in_tmp_path)
        assert_paths_equal(rel, join(*subdirs))

    def test_find_config_nonexist(self):
        '''find_config raises ConfigError if the config cannot be found'''
        with pytest.raises(scuba.config.ConfigError):
            scuba.config.find_config()

    ######################################################################
    # Load config

    def _invalid_config(self, match=None):
        with pytest.raises(scuba.config.ConfigError, match=match) as e:
            scuba.config.load_config('.scuba.yml')

    def test_load_config_no_image(self):
        '''load_config raises ConfigError if the config is empty and image is referenced'''
        with open('.scuba.yml', 'w') as f:
            pass

        config = scuba.config.load_config('.scuba.yml')
        with pytest.raises(scuba.config.ConfigError):
            img = config.image

    def test_load_unexpected_node(self):
        '''load_config raises ConfigError on unexpected config node'''
        with open('.scuba.yml', 'w') as f:
            f.write('image: busybox\n')
            f.write('unexpected_node_123456: value\n')

        self._invalid_config()

    def test_load_config_minimal(self):
        '''load_config loads a minimal config'''
        with open('.scuba.yml', 'w') as f:
            f.write('image: busybox\n')

        config = scuba.config.load_config('.scuba.yml')
        assert config.image == 'busybox'

    def test_load_config_with_aliases(self):
        '''load_config loads a config with aliases'''
        with open('.scuba.yml', 'w') as f:
            f.write('image: busybox\n')
            f.write('aliases:\n')
            f.write('  foo: bar\n')
            f.write('  snap: crackle pop\n')

        config = scuba.config.load_config('.scuba.yml')
        assert config.image == 'busybox'
        assert len(config.aliases) == 2
        assert config.aliases['foo'].script == ['bar']
        assert config.aliases['snap'].script == ['crackle pop']

    def test_load_config__no_spaces_in_aliases(self):
        '''load_config refuses spaces in aliases'''
        with open('.scuba.yml', 'w') as f:
            f.write('image: busybox\n')
            f.write('aliases:\n')
            f.write('  this has spaces: whatever\n')

        self._invalid_config()

    def test_load_config_image_from_yaml(self):
        '''load_config loads a config using !from_yaml'''
        with open('.gitlab.yml', 'w') as f:
            f.write('image: debian:8.2\n')

        with open('.scuba.yml', 'w') as f:
            f.write('image: !from_yaml .gitlab.yml image\n')

        config = scuba.config.load_config('.scuba.yml')
        assert config.image == 'debian:8.2'

    def test_load_config_image_from_yaml_nested_keys(self):
        '''load_config loads a config using !from_yaml with nested keys'''
        with open('.gitlab.yml', 'w') as f:
            f.write('somewhere:\n')
            f.write('  down:\n')
            f.write('    here: debian:8.2\n')

        with open('.scuba.yml', 'w') as f:
            f.write('image: !from_yaml .gitlab.yml somewhere.down.here\n')

        config = scuba.config.load_config('.scuba.yml')
        assert config.image == 'debian:8.2'

    def test_load_config_image_from_yaml_nested_keys_with_escaped_characters(self):
        '''load_config loads a config using !from_yaml with nested keys containing escaped '.' characters'''
        with open('.gitlab.yml', 'w') as f:
            f.write('.its:\n')
            f.write('  somewhere.down:\n')
            f.write('    here: debian:8.2\n')

        with open('.scuba.yml', 'w') as f:
            f.write('image: !from_yaml .gitlab.yml "\\.its.somewhere\\.down.here"\n')

        config = scuba.config.load_config('.scuba.yml')
        assert config.image == 'debian:8.2'

    def test_load_config_from_yaml_cached_file(self):
        '''load_config loads a config using !from_yaml from cached version'''
        with open('.gitlab.yml', 'w') as f:
            f.write('one: debian:8.2\n')
            f.write('two: debian:9.3\n')
            f.write('three: debian:10.1\n')

        with open('.scuba.yml', 'w') as f:
            f.write('image: !from_yaml .gitlab.yml one\n')
            f.write('aliases:\n')
            f.write('  two:\n')
            f.write('    image:  !from_yaml .gitlab.yml two\n')
            f.write('    script: ugh\n')
            f.write('  three:\n')
            f.write('    image:  !from_yaml .gitlab.yml three\n')
            f.write('    script: ugh\n')


        with mock_open() as m:
            config = scuba.config.load_config('.scuba.yml')

        # Assert that .gitlab.yml was only opened once
        assert m.mock_calls == [
            mock.call('.scuba.yml', 'r'),
            mock.call('.gitlab.yml', 'r'),
        ]

    def test_load_config_image_from_yaml_nested_key_missing(self):
        '''load_config raises ConfigError when !from_yaml references nonexistant key'''
        with open('.gitlab.yml', 'w') as f:
            f.write('somewhere:\n')
            f.write('  down:\n')

        with open('.scuba.yml', 'w') as f:
            f.write('image: !from_yaml .gitlab.yml somewhere.NONEXISTANT\n')

        self._invalid_config()

    def test_load_config_image_from_yaml_missing_file(self):
        '''load_config raises ConfigError when !from_yaml references nonexistant file'''
        with open('.scuba.yml', 'w') as f:
            f.write('image: !from_yaml .NONEXISTANT.yml image\n')

        self._invalid_config()

    def test_load_config_image_from_yaml_unicode_args(self):
        '''load_config !from_yaml works with unicode args'''
        with open('.gitlab.yml', 'w') as f:
            f.write('𝕦𝕟𝕚𝕔𝕠𝕕𝕖: 𝕨𝕠𝕣𝕜𝕤:𝕠𝕜\n')

        with open('.scuba.yml', 'w') as f:
            f.write('image: !from_yaml .gitlab.yml 𝕦𝕟𝕚𝕔𝕠𝕕𝕖\n')

        config = scuba.config.load_config('.scuba.yml')
        assert config.image == '𝕨𝕠𝕣𝕜𝕤:𝕠𝕜'

    def test_load_config_image_from_yaml_missing_arg(self):
        '''load_config raises ConfigError when !from_yaml has missing args'''
        with open('.gitlab.yml', 'w') as f:
            f.write('image: debian:8.2\n')

        with open('.scuba.yml', 'w') as f:
            f.write('image: !from_yaml .gitlab.yml\n')

        self._invalid_config()


    def __test_load_config_safe(self, bad_yaml_path):
        with open(bad_yaml_path, 'w') as f:
            f.write('danger:\n')
            f.write('  - !!python/object/apply:print [Danger]\n')
            f.write('  - !!python/object/apply:sys.exit [66]\n')

        pat = "could not determine a constructor for the tag.*python/object/apply"
        with pytest.raises(scuba.config.ConfigError, match=pat) as ctx:
            scuba.config.load_config('.scuba.yml')

    def test_load_config_safe(self):
        '''load_config safely loads yaml'''
        self.__test_load_config_safe('.scuba.yml')

    def test_load_config_safe_external(self):
        '''load_config safely loads yaml from external files'''
        with open('.scuba.yml', 'w') as f:
            f.write('image: !from_yaml .external.yml danger\n')

        self.__test_load_config_safe('.external.yml')

    ######################################################################
    # process_command

    def test_process_command_image(self):
        '''process_command returns the image and entrypoint'''
        image_name = 'test_image'
        entrypoint = 'test_entrypoint'

        cfg = scuba.config.ScubaConfig(
                image = image_name,
                entrypoint = entrypoint,
                )
        result = cfg.process_command([])
        assert result.image == image_name
        assert result.entrypoint == entrypoint

    def test_process_command_empty(self):
        '''process_command handles no aliases and an empty command'''
        cfg = scuba.config.ScubaConfig(
                image = 'na',
                )
        result = cfg.process_command([])
        assert result.script == None


    def test_process_command_no_aliases(self):
        '''process_command handles no aliases'''
        cfg = scuba.config.ScubaConfig(
                image = 'na',
                )
        result = cfg.process_command(['cmd', 'arg1', 'arg2'])
        assert [shlex.split(s) for s in result.script] == [
            ['cmd', 'arg1', 'arg2'],
        ]

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
        assert [shlex.split(s) for s in result.script] == [
            ['cmd', 'arg1', 'arg2'],
        ]

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
        assert [shlex.split(s) for s in result.script] == [
            ['banana', 'arg1', 'arg2'],
        ]

    def test_process_command_aliases_used_withargs(self):
        '''process_command handles aliases with args'''
        cfg = scuba.config.ScubaConfig(
                image = 'na',
                aliases = dict(
                    apple = 'banana cherry "pie is good"',
                    cat = 'dog',
                    ),
                )
        result = cfg.process_command(['apple', 'arg1', 'arg2 with spaces'])
        assert [shlex.split(s) for s in result.script] == [
            ['banana', 'cherry', 'pie is good', 'arg1', 'arg2 with spaces'],
        ]

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
        assert [shlex.split(s) for s in result.script] == [
            ['banana', 'cherry', 'pie is good'],
            ['so', 'is', 'peach'],
        ]

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
        with pytest.raises(scuba.config.ConfigError):
            cfg.process_command(['apple', 'ARGS', 'NOT ALLOWED'])

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
        assert result.image == 'overridden'

    def test_process_command_alias_overrides_image_and_entrypoint(self):
        '''aliases can override the image and entrypoint'''
        cfg = scuba.config.ScubaConfig(
                image = 'default',
                entrypoint = 'default_entrypoint',
                aliases = dict(
                    apple = dict(
                        script = [
                            'banana cherry "pie is good"',
                            'so is peach',
                        ],
                        image = 'overridden',
                        entrypoint = 'overridden_entrypoint',
                    ),
                ),
            )
        result = cfg.process_command(['apple'])
        assert result.image == 'overridden'
        assert result.entrypoint == 'overridden_entrypoint'

    def test_process_command_alias_overrides_image_and_empty_entrypoint(self):
        '''aliases can override the image and empty/null entrypoint'''
        cfg = scuba.config.ScubaConfig(
                image = 'default',
                entrypoint = 'default_entrypoint',
                aliases = dict(
                    apple = dict(
                        script = [
                            'banana cherry "pie is good"',
                            'so is peach',
                        ],
                        image = 'overridden',
                        entrypoint = '',
                    ),
                ),
            )
        result = cfg.process_command(['apple'])
        assert result.image == 'overridden'
        assert result.entrypoint == ''


    def test_process_command_image_override(self):
        '''process_command allows image to be overridden when provided'''
        override_image_name = 'override_image'

        cfg = scuba.config.ScubaConfig(
                image = 'test_image',
                )
        result = cfg.process_command([], image=override_image_name)
        assert result.image == override_image_name

    def test_process_command_image_override_missing(self):
        '''process_command allows image to be overridden when not provided'''
        override_image_name = 'override_image'

        cfg = scuba.config.ScubaConfig()
        result = cfg.process_command([], image=override_image_name)
        assert result.image == override_image_name

    def test_process_command_image_override_alias(self):
        '''process_command allows image to be overridden when provided by alias'''
        override_image_name = 'override_image'

        cfg = scuba.config.ScubaConfig(
                aliases = dict(
                    apple = dict(
                        script = [
                            'banana cherry "pie is good"',
                            'so is peach',
                        ],
                        image = 'apple_image',
                    ),
                )
            )
        result = cfg.process_command([], image=override_image_name)
        assert result.image == override_image_name

    def test_process_command_alias_extends_docker_args(self):
        '''aliases can extend the docker_args'''
        cfg = scuba.config.ScubaConfig(
                image = 'default',
                docker_args = '--privileged',
                aliases = dict(
                    apple = dict(
                        script = [
                            'banana cherry "pie is good"',
                        ],
                        docker_args = '-v /tmp/:/tmp/',
                    ),
                ),
            )
        result = cfg.process_command(['apple'])
        assert result.docker_args == ['--privileged', '-v', '/tmp/:/tmp/']

    def test_process_command_alias_overrides_docker_args(self):
        '''aliases can override the docker_args'''
        cfg = scuba.config.ScubaConfig(
                image = 'default',
                docker_args = '--privileged',
                aliases = dict(
                    apple = dict(
                        script = [
                            'banana cherry "pie is good"',
                        ],
                        docker_args = scuba.config.OverrideStr('-v /tmp/:/tmp/'),
                    ),
                ),
            )
        result = cfg.process_command(['apple'])
        assert result.docker_args == ['-v', '/tmp/:/tmp/']

    def test_process_command_alias_overrides_docker_args_with_empty(self):
        '''aliases can override the docker_args'''
        cfg = scuba.config.ScubaConfig(
                image = 'default',
                docker_args = '--privileged',
                aliases = dict(
                    apple = dict(
                        script = [
                            'banana cherry "pie is good"',
                        ],
                        docker_args = scuba.config.OverrideStr(''),
                    ),
                ),
            )
        result = cfg.process_command(['apple'])
        assert result.docker_args == []

    def test_process_command_alias_inherits_top_docker_args(self):
        '''aliases inherit the top-level docker_args if not specified'''
        cfg = scuba.config.ScubaConfig(
                image = 'default',
                docker_args = '--privileged',
                aliases = dict(
                    apple = dict(
                        script = [
                            'banana cherry "pie is good"',
                        ],
                    ),
                ),
            )
        result = cfg.process_command(['apple'])
        assert result.docker_args == ['--privileged']

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

        assert config.hooks.get('root') == ['echo "This runs before we switch users"', 'id']
        assert config.hooks.get('user') == ['id']

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

        self._invalid_config()

    def test_hooks_missing_script(self):
        '''hooks with dict, but missing "script" are invalid'''
        with open('.scuba.yml', 'w') as f:
            f.write('''
                image: na
                hooks:
                  user:
                    not_script: missing "script" key
                ''')

        self._invalid_config()


    ############################################################################
    # Env

    def test_env_invalid(self):
        '''Environment must be dict or list of strings'''
        with open('.scuba.yml', 'w') as f:
            f.write(r'''
                image: na
                environment: 666
                ''')
        self._invalid_config('must be list or mapping')

    def test_env_top_dict(self, monkeypatch):
        '''Top-level environment can be loaded (dict)'''
        with open('.scuba.yml', 'w') as f:
            f.write(r'''
                image: na
                environment:
                  FOO: This is foo
                  FOO_WITH_QUOTES: "\"Quoted foo\""    # Quotes included in value
                  BAR: "This is bar"
                  MAGIC: 42
                  SWITCH_1: true        # YAML boolean
                  SWITCH_2: "true"      # YAML string
                  EMPTY: ""
                  EXTERNAL:             # Comes from os env
                  EXTERNAL_NOTSET:      # Missing in os env
                ''')

        monkeypatch.setenv('EXTERNAL', 'Outside world')
        monkeypatch.delenv('EXTERNAL_NOTSET', raising=False)

        config = scuba.config.load_config('.scuba.yml')

        expect = dict(
            FOO = "This is foo",
            FOO_WITH_QUOTES = "\"Quoted foo\"",
            BAR = "This is bar",
            MAGIC = "42",           # N.B. string
            SWITCH_1 = "True",      # Unfortunately this is due to str(bool(1))
            SWITCH_2 = "true",
            EMPTY = "",
            EXTERNAL = "Outside world",
            EXTERNAL_NOTSET = "",
        )
        assert expect == config.environment


    def test_env_top_list(self, monkeypatch):
        '''Top-level environment can be loaded (list)'''
        with open('.scuba.yml', 'w') as f:
            f.write(r'''
                image: na
                environment:
                  - FOO=This is foo                 # No quotes
                  - FOO_WITH_QUOTES="Quoted foo"    # Quotes included in value
                  - BAR=This is bar
                  - MAGIC=42
                  - SWITCH_2=true
                  - EMPTY=
                  - EXTERNAL                        # Comes from os env
                  - EXTERNAL_NOTSET                 # Missing in os env
                ''')

        monkeypatch.setenv('EXTERNAL', 'Outside world')
        monkeypatch.delenv('EXTERNAL_NOTSET', raising=False)

        config = scuba.config.load_config('.scuba.yml')

        expect = dict(
            FOO = "This is foo",
            FOO_WITH_QUOTES = "\"Quoted foo\"",
            BAR = "This is bar",
            MAGIC = "42",           # N.B. string
            SWITCH_2 = "true",
            EMPTY = "",
            EXTERNAL = "Outside world",
            EXTERNAL_NOTSET = "",
        )
        assert expect == config.environment


    def test_env_alias(self):
        '''Alias can have environment which overrides top-level'''
        with open('.scuba.yml', 'w') as f:
            f.write(r'''
                image: na
                environment:
                  FOO: Top-level
                  BAR: 42
                aliases:
                  al:
                    script: Don't care
                    environment:
                      FOO: Overridden
                      MORE: Hello world
                ''')

        config = scuba.config.load_config('.scuba.yml')

        assert config.environment == dict(
                FOO = "Top-level",
                BAR = "42",
            )

        assert config.aliases['al'].environment == dict(
                FOO = "Overridden",
                MORE = "Hello world",
            )

        # Does the environment get overridden / merged?
        ctx = config.process_command(['al'])

        assert ctx.environment == dict(
                FOO = "Overridden",
                BAR = "42",
                MORE = "Hello world",
            )


    ############################################################################
    # Entrypoint

    def test_entrypoint_not_set(self):
        '''Entrypoint can be missing'''
        with open('.scuba.yml', 'w') as f:
            f.write(r'''
                image: na
                ''')

        config = scuba.config.load_config('.scuba.yml')
        assert config.entrypoint is None

    def test_entrypoint_null(self):
        '''Entrypoint can be set to null'''
        with open('.scuba.yml', 'w') as f:
            f.write(r'''
                image: na
                entrypoint:
                ''')

        config = scuba.config.load_config('.scuba.yml')
        assert config.entrypoint == ''     # Null => empty string

    def test_entrypoint_invalid(self):
        '''Entrypoint of incorrect type raises ConfigError'''
        with open('.scuba.yml', 'w') as f:
            f.write(r'''
                image: na
                entrypoint: 666
                ''')

        self._invalid_config('must be a string')

    def test_entrypoint_emptry_string(self):
        '''Entrypoint can be set to an empty string'''
        with open('.scuba.yml', 'w') as f:
            f.write(r'''
                image: na
                entrypoint: ""
                ''')

        config = scuba.config.load_config('.scuba.yml')
        assert config.entrypoint == ''

    def test_entrypoint_set(self):
        '''Entrypoint can be set'''
        with open('.scuba.yml', 'w') as f:
            f.write(r'''
                image: na
                entrypoint: my_ep
                ''')

        config = scuba.config.load_config('.scuba.yml')
        assert config.entrypoint == 'my_ep'

    def test_alias_entrypoint_null(self):
        '''Entrypoint can be set to null via alias'''
        with open('.scuba.yml', 'w') as f:
            f.write(r'''
                image: na
                entrypoint: na_ep
                aliases:
                  testalias:
                    entrypoint:
                    script:
                      - ugh
                ''')

        config = scuba.config.load_config('.scuba.yml')
        assert config.aliases['testalias'].entrypoint == ''    # Null => empty string

    def test_alias_entrypoint_empty_string(self):
        '''Entrypoint can be set to an empty string via alias'''
        with open('.scuba.yml', 'w') as f:
            f.write(r'''
                image: na
                entrypoint: na_ep
                aliases:
                  testalias:
                    entrypoint: ""
                    script:
                      - ugh
                ''')

        config = scuba.config.load_config('.scuba.yml')
        assert config.aliases['testalias'].entrypoint == ''

    def test_alias_entrypoint(self):
        '''Entrypoint can be set via alias'''
        with open('.scuba.yml', 'w') as f:
            f.write(r'''
                image: na
                entrypoint: na_ep
                aliases:
                  testalias:
                    entrypoint: use_this_ep
                    script:
                      - ugh
                ''')

        config = scuba.config.load_config('.scuba.yml')
        assert config.aliases['testalias'].entrypoint == 'use_this_ep'

    ############################################################################
    # docker_args

    def test_docker_args_not_set(self):
        '''docker_args can be missing'''
        with open('.scuba.yml', 'w') as f:
            f.write(r'''
                image: na
                ''')

        config = scuba.config.load_config('.scuba.yml')
        assert config.docker_args is None

    def test_docker_args_invalid(self):
        '''docker_args of incorrect type raises ConfigError'''
        with open('.scuba.yml', 'w') as f:
            f.write(r'''
                image: na
                docker_args: 666
                ''')

        self._invalid_config('must be a string')

    def test_docker_args_null(self):
        '''docker_args can be set to null'''
        with open('.scuba.yml', 'w') as f:
            f.write(r'''
                image: na
                docker_args:
                ''')

        config = scuba.config.load_config('.scuba.yml')
        assert config.docker_args == []

    def test_docker_args_set_empty_string(self):
        '''docker_args can be set to empty string'''
        with open('.scuba.yml', 'w') as f:
            f.write(r'''
                image: na
                docker_args: ''
                ''')

        config = scuba.config.load_config('.scuba.yml')
        assert config.docker_args == []  # '' -> [] after shlex.split()

    def test_docker_args_set(self):
        '''docker_args can be set'''
        with open('.scuba.yml', 'w') as f:
            f.write(r'''
                image: na
                docker_args: --privileged
                ''')

        config = scuba.config.load_config('.scuba.yml')
        assert config.docker_args == ['--privileged']

    def test_docker_args_set_multi(self):
        '''docker_args can be set to multiple args'''
        with open('.scuba.yml', 'w') as f:
            f.write(r'''
                image: na
                docker_args: --privileged -v /tmp/:/tmp/
                ''')

        config = scuba.config.load_config('.scuba.yml')
        assert config.docker_args == ['--privileged', '-v', '/tmp/:/tmp/']

    def test_alias_docker_args_null(self):
        '''docker_args can be set to null via alias'''
        with open('.scuba.yml', 'w') as f:
            f.write(r'''
                image: na
                docker_args: --privileged
                aliases:
                  testalias:
                    docker_args:
                    script:
                      - ugh
                ''')

        config = scuba.config.load_config('.scuba.yml')
        assert config.aliases['testalias'].docker_args == []

    def test_alias_docker_args_empty_string(self):
        '''docker_args can be set to empty string via alias'''
        with open('.scuba.yml', 'w') as f:
            f.write(r'''
                image: na
                docker_args: --privileged
                aliases:
                  testalias:
                    docker_args: ''
                    script:
                      - ugh
                ''')

        config = scuba.config.load_config('.scuba.yml')
        assert config.aliases['testalias'].docker_args == []

    def test_alias_docker_args_set(self):
        '''docker_args can be set via alias'''
        with open('.scuba.yml', 'w') as f:
            f.write(r'''
                image: na
                docker_args: --privileged
                aliases:
                  testalias:
                    docker_args: -v /tmp/:/tmp/
                    script:
                      - ugh
                ''')

        config = scuba.config.load_config('.scuba.yml')
        assert config.aliases['testalias'].docker_args == ['-v', '/tmp/:/tmp/']

    def test_alias_docker_args_override(self):
        '''docker_args can be tagged for override'''
        with open('.scuba.yml', 'w') as f:
            f.write(r'''
                image: na
                docker_args: --privileged
                aliases:
                  testalias:
                    docker_args: !override -v /tmp/:/tmp/
                    script:
                      - ugh
                ''')

        config = scuba.config.load_config('.scuba.yml')
        assert config.aliases['testalias'].docker_args == ['-v', '/tmp/:/tmp/']
        assert isinstance(config.aliases['testalias'].docker_args, scuba.config.OverrideMixin)

    def test_alias_docker_args_override_implicit_null(self):
        '''docker_args can be overridden with an implicit null value'''
        with open('.scuba.yml', 'w') as f:
            f.write(r'''
                image: na
                docker_args: --privileged
                aliases:
                  testalias:
                    docker_args: !override
                    script:
                      - ugh
                ''')

        config = scuba.config.load_config('.scuba.yml')
        assert config.aliases['testalias'].docker_args == []
        assert isinstance(config.aliases['testalias'].docker_args, scuba.config.OverrideMixin)

    def test_alias_docker_args_override_from_yaml(self):
        '''!override tag can be applied before a !from_yaml tag'''
        with open('args.yml', 'w') as f:
            f.write('args: -v /tmp/:/tmp/\n')

        with open('.scuba.yml', 'w') as f:
            f.write(r'''
                image: na
                docker_args: --privileged
                aliases:
                  testalias:
                    docker_args: !override '!from_yaml args.yml args'
                    script:
                      - ugh
                ''')

        config = scuba.config.load_config('.scuba.yml')
        assert config.aliases['testalias'].docker_args == ['-v', '/tmp/:/tmp/']
        assert isinstance(config.aliases['testalias'].docker_args, scuba.config.OverrideMixin)

    def test_alias_docker_args_from_yaml_override(self):
        '''!override tag can be applied inside of a !from_yaml tag'''
        with open('args.yml', 'w') as f:
            f.write('args: !override -v /tmp/:/tmp/\n')

        with open('.scuba.yml', 'w') as f:
            f.write(r'''
                image: na
                docker_args: --privileged
                aliases:
                  testalias:
                    docker_args: !from_yaml args.yml args
                    script:
                      - ugh
                ''')

        config = scuba.config.load_config('.scuba.yml')
        assert config.aliases['testalias'].docker_args == ['-v', '/tmp/:/tmp/']
        assert isinstance(config.aliases['testalias'].docker_args, scuba.config.OverrideMixin)
