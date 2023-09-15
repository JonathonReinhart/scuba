# coding=utf-8
from .utils import *
import pytest

import logging
import os
from os.path import join
from pathlib import Path
from shutil import rmtree

import scuba.config


def load_config() -> scuba.config.ScubaConfig:
    return scuba.config.load_config(Path(".scuba.yml"), Path.cwd())


class TestCommonScriptSchema:
    def test_simple(self) -> None:
        """Simple form: value is a string"""
        node = "foo"
        result = scuba.config._process_script_node(node, "dontcare")
        assert result == ["foo"]

    def test_script_key_string(self) -> None:
        """Value is a mapping: script is a string"""
        node = dict(
            script="foo",
            otherkey="other",
        )
        result = scuba.config._process_script_node(node, "dontcare")
        assert result == ["foo"]

    def test_script_key_list(self) -> None:
        """Value is a mapping: script is a list"""
        node = dict(
            script=[
                "foo",
                "bar",
            ],
            otherkey="other",
        )
        result = scuba.config._process_script_node(node, "dontcare")
        assert result == ["foo", "bar"]

    def test_script_key_mapping_invalid(self) -> None:
        """Value is a mapping: script is a mapping (invalid)"""
        node = dict(
            script=dict(
                whatisthis="idontknow",
            ),
        )
        with pytest.raises(scuba.config.ConfigError):
            scuba.config._process_script_node(node, "dontcare")


@pytest.mark.usefixtures("in_tmp_path")
class TestConfig:
    ######################################################################
    # Find config

    def test_find_config_cur_dir(self, in_tmp_path) -> None:
        """find_config can find the config in the current directory"""
        with open(".scuba.yml", "w") as f:
            f.write("image: bosybux\n")

        path, rel, _ = scuba.config.find_config()
        assert_paths_equal(path, in_tmp_path)
        assert_paths_equal(rel, "")

    def test_find_config_parent_dir(self, in_tmp_path) -> None:
        """find_config cuba can find the config in the parent directory"""
        with open(".scuba.yml", "w") as f:
            f.write("image: bosybux\n")

        os.mkdir("subdir")
        os.chdir("subdir")

        # Verify our current working dir
        assert_paths_equal(os.getcwd(), in_tmp_path.joinpath("subdir"))

        path, rel, _ = scuba.config.find_config()
        assert_paths_equal(path, in_tmp_path)
        assert_paths_equal(rel, "subdir")

    def test_find_config_way_up(self, in_tmp_path) -> None:
        """find_config can find the config way up the directory hierarchy"""
        with open(".scuba.yml", "w") as f:
            f.write("image: bosybux\n")

        subdirs = ["foo", "bar", "snap", "crackle", "pop"]

        for sd in subdirs:
            os.mkdir(sd)
            os.chdir(sd)

        # Verify our current working dir
        assert_paths_equal(os.getcwd(), in_tmp_path.joinpath(*subdirs))

        path, rel, _ = scuba.config.find_config()
        assert_paths_equal(path, in_tmp_path)
        assert_paths_equal(rel, join(*subdirs))

    def test_find_config_nonexist(self) -> None:
        """find_config raises ConfigError if the config cannot be found"""
        with pytest.raises(scuba.config.ConfigError):
            scuba.config.find_config()

    ######################################################################
    # Load config

    def _invalid_config(self, match=None):
        with pytest.raises(scuba.config.ConfigError, match=match) as e:
            load_config()

    def test_load_config_no_image(self) -> None:
        """load_config raises ConfigError if the config is empty and image is referenced"""
        with open(".scuba.yml", "w") as f:
            pass

        config = load_config()
        with pytest.raises(scuba.config.ConfigError):
            img = config.image

    def test_load_unexpected_node(self) -> None:
        """load_config raises ConfigError on unexpected config node"""
        with open(".scuba.yml", "w") as f:
            f.write("image: bosybux\n")
            f.write("unexpected_node_123456: value\n")

        self._invalid_config()

    def test_load_config_minimal(self) -> None:
        """load_config loads a minimal config"""
        with open(".scuba.yml", "w") as f:
            f.write("image: bosybux\n")

        config = load_config()
        assert config.image == "bosybux"

    def test_load_config_with_aliases(self) -> None:
        """load_config loads a config with aliases"""
        with open(".scuba.yml", "w") as f:
            f.write("image: bosybux\n")
            f.write("aliases:\n")
            f.write("  foo: bar\n")
            f.write("  snap: crackle pop\n")

        config = load_config()
        assert config.image == "bosybux"
        assert len(config.aliases) == 2
        assert config.aliases["foo"].script == ["bar"]
        assert config.aliases["snap"].script == ["crackle pop"]

    def test_load_config__no_spaces_in_aliases(self) -> None:
        """load_config refuses spaces in aliases"""
        with open(".scuba.yml", "w") as f:
            f.write("image: bosybux\n")
            f.write("aliases:\n")
            f.write("  this has spaces: whatever\n")

        self._invalid_config()

    def test_load_config_image_from_yaml(self) -> None:
        """load_config loads a config using !from_yaml"""
        with open(".gitlab.yml", "w") as f:
            f.write("image: dummian:8.2\n")

        with open(".scuba.yml", "w") as f:
            f.write("image: !from_yaml .gitlab.yml image\n")

        config = load_config()
        assert config.image == "dummian:8.2"

    def test_load_config_image_from_yaml_nested_keys(self) -> None:
        """load_config loads a config using !from_yaml with nested keys"""
        with open(".gitlab.yml", "w") as f:
            f.write("somewhere:\n")
            f.write("  down:\n")
            f.write("    here: dummian:8.2\n")

        with open(".scuba.yml", "w") as f:
            f.write("image: !from_yaml .gitlab.yml somewhere.down.here\n")

        config = load_config()
        assert config.image == "dummian:8.2"

    def test_load_config_image_from_yaml_nested_keys_with_escaped_characters(
        self,
    ) -> None:
        """load_config loads a config using !from_yaml with nested keys containing escaped '.' characters"""
        with open(".gitlab.yml", "w") as f:
            f.write(".its:\n")
            f.write("  somewhere.down:\n")
            f.write("    here: dummian:8.2\n")

        with open(".scuba.yml", "w") as f:
            f.write('image: !from_yaml .gitlab.yml "\\.its.somewhere\\.down.here"\n')

        config = load_config()
        assert config.image == "dummian:8.2"

    def test_load_config_from_yaml_cached_file(self) -> None:
        """load_config loads a config using !from_yaml from cached version"""
        with open(".gitlab.yml", "w") as f:
            f.write("one: dummian:8.2\n")
            f.write("two: dummian:9.3\n")
            f.write("three: dummian:10.1\n")

        with open(".scuba.yml", "w") as f:
            f.write("image: !from_yaml .gitlab.yml one\n")
            f.write("aliases:\n")
            f.write("  two:\n")
            f.write("    image:  !from_yaml .gitlab.yml two\n")
            f.write("    script: ugh\n")
            f.write("  three:\n")
            f.write("    image:  !from_yaml .gitlab.yml three\n")
            f.write("    script: ugh\n")

        with mock.patch.object(Path, "open", autospec=True, side_effect=Path.open) as m:
            config = load_config()

        # Assert that .gitlab.yml was only opened once
        assert m.mock_calls == [
            mock.call(Path(".scuba.yml"), "r"),
            mock.call(Path(".gitlab.yml"), "r"),
        ]

    def test_load_config_image_from_yaml_nested_key_missing(self) -> None:
        """load_config raises ConfigError when !from_yaml references nonexistant key"""
        with open(".gitlab.yml", "w") as f:
            f.write("somewhere:\n")
            f.write("  down:\n")

        with open(".scuba.yml", "w") as f:
            f.write("image: !from_yaml .gitlab.yml somewhere.NONEXISTANT\n")

        self._invalid_config()

    def test_load_config_image_from_yaml_missing_file(self) -> None:
        """load_config raises ConfigError when !from_yaml references nonexistant file"""
        with open(".scuba.yml", "w") as f:
            f.write("image: !from_yaml .NONEXISTANT.yml image\n")

        self._invalid_config()

    def test_load_config_image_from_yaml_unicode_args(self) -> None:
        """load_config !from_yaml works with unicode args"""
        with open(".gitlab.yml", "w") as f:
            f.write("𝕦𝕟𝕚𝕔𝕠𝕕𝕖: 𝕨𝕠𝕣𝕜𝕤:𝕠𝕜\n")

        with open(".scuba.yml", "w") as f:
            f.write("image: !from_yaml .gitlab.yml 𝕦𝕟𝕚𝕔𝕠𝕕𝕖\n")

        config = load_config()
        assert config.image == "𝕨𝕠𝕣𝕜𝕤:𝕠𝕜"

    def test_load_config_image_from_yaml_missing_arg(self) -> None:
        """load_config raises ConfigError when !from_yaml has missing args"""
        with open(".gitlab.yml", "w") as f:
            f.write("image: dummian:8.2\n")

        with open(".scuba.yml", "w") as f:
            f.write("image: !from_yaml .gitlab.yml\n")

        self._invalid_config()

    def __test_load_config_safe(self, bad_yaml_path) -> None:
        with open(bad_yaml_path, "w") as f:
            f.write("danger:\n")
            f.write("  - !!python/object/apply:print [Danger]\n")
            f.write("  - !!python/object/apply:sys.exit [66]\n")

        pat = "could not determine a constructor for the tag.*python/object/apply"
        with pytest.raises(scuba.config.ConfigError, match=pat) as ctx:
            load_config()

    def test_load_config_safe(self) -> None:
        """load_config safely loads yaml"""
        self.__test_load_config_safe(".scuba.yml")

    def test_load_config_safe_external(self) -> None:
        """load_config safely loads yaml from external files"""
        with open(".scuba.yml", "w") as f:
            f.write("image: !from_yaml .external.yml danger\n")

        self.__test_load_config_safe(".external.yml")

    ############################################################################
    # Hooks

    def test_hooks_mixed(self) -> None:
        """hooks of mixed forms are valid"""
        with open(".scuba.yml", "w") as f:
            f.write(
                """
                image: na
                hooks:
                  root:
                    script:
                      - echo "This runs before we switch users"
                      - id
                  user: id
                """
            )

        config = load_config()

        assert config.hooks.get("root") == [
            'echo "This runs before we switch users"',
            "id",
        ]
        assert config.hooks.get("user") == ["id"]

    def test_hooks_invalid_list(self) -> None:
        """hooks with list not under "script" key are invalid"""
        with open(".scuba.yml", "w") as f:
            f.write(
                """
                image: na
                hooks:
                  user:
                    - this list should be under
                    - a 'script'
                """
            )

        self._invalid_config()

    def test_hooks_missing_script(self) -> None:
        """hooks with dict, but missing "script" are invalid"""
        with open(".scuba.yml", "w") as f:
            f.write(
                """
                image: na
                hooks:
                  user:
                    not_script: missing "script" key
                """
            )

        self._invalid_config()

    ############################################################################
    # Env

    def test_env_invalid(self) -> None:
        """Environment must be dict or list of strings"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                environment: 666
                """
            )
        self._invalid_config("must be list or mapping")

    def test_env_top_dict(self, monkeypatch) -> None:
        """Top-level environment can be loaded (dict)"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
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
                """
            )

        monkeypatch.setenv("EXTERNAL", "Outside world")
        monkeypatch.delenv("EXTERNAL_NOTSET", raising=False)

        config = load_config()

        expect = dict(
            FOO="This is foo",
            FOO_WITH_QUOTES='"Quoted foo"',
            BAR="This is bar",
            MAGIC="42",  # N.B. string
            SWITCH_1="True",  # Unfortunately this is due to str(bool(1))
            SWITCH_2="true",
            EMPTY="",
            EXTERNAL="Outside world",
            EXTERNAL_NOTSET="",
        )
        assert expect == config.environment

    def test_env_top_list(self, monkeypatch) -> None:
        """Top-level environment can be loaded (list)"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
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
                """
            )

        monkeypatch.setenv("EXTERNAL", "Outside world")
        monkeypatch.delenv("EXTERNAL_NOTSET", raising=False)

        config = load_config()

        expect = dict(
            FOO="This is foo",
            FOO_WITH_QUOTES='"Quoted foo"',
            BAR="This is bar",
            MAGIC="42",  # N.B. string
            SWITCH_2="true",
            EMPTY="",
            EXTERNAL="Outside world",
            EXTERNAL_NOTSET="",
        )
        assert expect == config.environment

    def test_env_alias(self) -> None:
        """Alias can have environment"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                aliases:
                  al:
                    script: Don't care
                    environment:
                      FOO: Overridden
                      MORE: Hello world
                """
            )

        config = load_config()

        assert config.aliases["al"].environment == dict(
            FOO="Overridden",
            MORE="Hello world",
        )

    ############################################################################
    # Entrypoint

    def test_entrypoint_not_set(self) -> None:
        """Entrypoint can be missing"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                """
            )

        config = load_config()
        assert config.entrypoint is None

    def test_entrypoint_null(self) -> None:
        """Entrypoint can be set to null"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                entrypoint:
                """
            )

        config = load_config()
        assert config.entrypoint == ""  # Null => empty string

    def test_entrypoint_invalid(self) -> None:
        """Entrypoint of incorrect type raises ConfigError"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                entrypoint: 666
                """
            )

        self._invalid_config("must be a string")

    def test_entrypoint_emptry_string(self) -> None:
        """Entrypoint can be set to an empty string"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                entrypoint: ""
                """
            )

        config = load_config()
        assert config.entrypoint == ""

    def test_entrypoint_set(self) -> None:
        """Entrypoint can be set"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                entrypoint: my_ep
                """
            )

        config = load_config()
        assert config.entrypoint == "my_ep"

    def test_alias_entrypoint_null(self) -> None:
        """Entrypoint can be set to null via alias"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                entrypoint: na_ep
                aliases:
                  testalias:
                    entrypoint:
                    script:
                      - ugh
                """
            )

        config = load_config()
        assert config.aliases["testalias"].entrypoint == ""  # Null => empty string

    def test_alias_entrypoint_empty_string(self) -> None:
        """Entrypoint can be set to an empty string via alias"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                entrypoint: na_ep
                aliases:
                  testalias:
                    entrypoint: ""
                    script:
                      - ugh
                """
            )

        config = load_config()
        assert config.aliases["testalias"].entrypoint == ""

    def test_alias_entrypoint(self) -> None:
        """Entrypoint can be set via alias"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                entrypoint: na_ep
                aliases:
                  testalias:
                    entrypoint: use_this_ep
                    script:
                      - ugh
                """
            )

        config = load_config()
        assert config.aliases["testalias"].entrypoint == "use_this_ep"

    ############################################################################
    # docker_args

    def test_docker_args_not_set(self) -> None:
        """docker_args can be missing"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                """
            )

        config = load_config()
        assert config.docker_args is None

    def test_docker_args_invalid(self) -> None:
        """docker_args of incorrect type raises ConfigError"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                docker_args: 666
                """
            )

        self._invalid_config("must be a string")

    def test_docker_args_null(self) -> None:
        """docker_args can be set to null"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                docker_args:
                """
            )

        config = load_config()
        assert config.docker_args == []

    def test_docker_args_set_empty_string(self) -> None:
        """docker_args can be set to empty string"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                docker_args: ''
                """
            )

        config = load_config()
        assert config.docker_args == []  # '' -> [] after shlex.split()

    def test_docker_args_set(self) -> None:
        """docker_args can be set"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                docker_args: --privileged
                """
            )

        config = load_config()
        assert config.docker_args == ["--privileged"]

    def test_docker_args_set_multi(self) -> None:
        """docker_args can be set to multiple args"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                docker_args: --privileged -v /tmp/:/tmp/
                """
            )

        config = load_config()
        assert config.docker_args == ["--privileged", "-v", "/tmp/:/tmp/"]

    def test_alias_docker_args_null(self) -> None:
        """docker_args can be set to null via alias"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                docker_args: --privileged
                aliases:
                  testalias:
                    docker_args:
                    script:
                      - ugh
                """
            )

        config = load_config()
        assert config.aliases["testalias"].docker_args == []

    def test_alias_docker_args_empty_string(self) -> None:
        """docker_args can be set to empty string via alias"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                docker_args: --privileged
                aliases:
                  testalias:
                    docker_args: ''
                    script:
                      - ugh
                """
            )

        config = load_config()
        assert config.aliases["testalias"].docker_args == []

    def test_alias_docker_args_set(self) -> None:
        """docker_args can be set via alias"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                docker_args: --privileged
                aliases:
                  testalias:
                    docker_args: -v /tmp/:/tmp/
                    script:
                      - ugh
                """
            )

        config = load_config()
        assert config.aliases["testalias"].docker_args == ["-v", "/tmp/:/tmp/"]

    def test_alias_docker_args_override(self) -> None:
        """docker_args can be tagged for override"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                docker_args: --privileged
                aliases:
                  testalias:
                    docker_args: !override -v /tmp/:/tmp/
                    script:
                      - ugh
                """
            )

        config = load_config()
        assert config.aliases["testalias"].docker_args == ["-v", "/tmp/:/tmp/"]
        assert isinstance(
            config.aliases["testalias"].docker_args, scuba.config.OverrideMixin
        )

    def test_alias_docker_args_override_implicit_null(self) -> None:
        """docker_args can be overridden with an implicit null value"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                docker_args: --privileged
                aliases:
                  testalias:
                    docker_args: !override
                    script:
                      - ugh
                """
            )

        config = load_config()
        assert config.aliases["testalias"].docker_args == []
        assert isinstance(
            config.aliases["testalias"].docker_args, scuba.config.OverrideMixin
        )

    def test_alias_docker_args_override_from_yaml(self) -> None:
        """!override tag can be applied before a !from_yaml tag"""
        with open("args.yml", "w") as f:
            f.write("args: -v /tmp/:/tmp/\n")

        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                docker_args: --privileged
                aliases:
                  testalias:
                    docker_args: !override '!from_yaml args.yml args'
                    script:
                      - ugh
                """
            )

        config = load_config()
        assert config.aliases["testalias"].docker_args == ["-v", "/tmp/:/tmp/"]
        assert isinstance(
            config.aliases["testalias"].docker_args, scuba.config.OverrideMixin
        )

    def test_alias_docker_args_from_yaml_override(self) -> None:
        """!override tag can be applied inside of a !from_yaml tag"""
        with open("args.yml", "w") as f:
            f.write("args: !override -v /tmp/:/tmp/\n")

        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                docker_args: --privileged
                aliases:
                  testalias:
                    docker_args: !from_yaml args.yml args
                    script:
                      - ugh
                """
            )

        config = load_config()
        assert config.aliases["testalias"].docker_args == ["-v", "/tmp/:/tmp/"]
        assert isinstance(
            config.aliases["testalias"].docker_args, scuba.config.OverrideMixin
        )

    ############################################################################
    # volumes

    def test_volumes_not_set(self) -> None:
        """volumes can be missing"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                """
            )

        config = load_config()
        assert config.volumes is None

    def test_volumes_null(self) -> None:
        """volumes can be set to null"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                volumes:
                """
            )

        config = load_config()
        assert config.volumes == None

    def test_volumes_invalid(self) -> None:
        """volumes of incorrect type raises ConfigError"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                volumes: 666
                """
            )

        self._invalid_config("must be a dict")

    def test_volumes_invalid_volume_type(self) -> None:
        """volume of incorrect type (list) raises ConfigError"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                volumes:
                  /foo:
                    - a list makes no sense
                """
            )

        self._invalid_config("must be string or dict")

    def test_volumes_null_volume_type(self) -> None:
        """volume of None type raises ConfigError"""
        # NOTE: In the future, we might want to support this as a volume
        #       (non-bindmount, e.g. '-v /somedata'), or as tmpfs
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                volumes:
                  /bar:
                """
            )

        self._invalid_config("hostpath")

    def test_volume_as_dict_missing_hostpath(self) -> None:
        """volume of incorrect type raises ConfigError"""
        # NOTE: In the future, we might want to support this as a volume
        #       (non-bindmount, e.g. '-v /somedata'), or as tmpfs
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                volumes:
                  /bar:
                    options: hostpath,is,missing
                """
            )

        self._invalid_config("hostpath")

    def test_volumes_simple_volume(self) -> None:
        """volumes can be set using the simple form"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                volumes:
                  /cpath: /hpath
                """
            )

        config = load_config()
        assert config.volumes is not None
        assert len(config.volumes) == 1

        assert_vol(config.volumes, "/cpath", "/hpath")

    def test_volumes_complex(self) -> None:
        """volumes can be set using the complex form"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                volumes:
                  /foo: /host/foo
                  /bar:
                    hostpath: /host/bar
                  /snap:
                    hostpath: /host/snap
                    options: z,ro
                """
            )

        config = load_config()
        vols = config.volumes
        assert vols is not None
        assert len(vols) == 3

        assert_vol(vols, "/foo", "/host/foo")
        assert_vol(vols, "/bar", "/host/bar")
        assert_vol(vols, "/snap", "/host/snap", ["z", "ro"])

    def test_alias_volumes_set(self) -> None:
        """docker_args can be set via alias"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                aliases:
                  testalias:
                    script:
                      - ugh
                    volumes:
                      /foo: /host/foo
                      /bar:
                        hostpath: /host/bar
                        options: z,ro
                """
            )

        config = load_config()
        vols = config.aliases["testalias"].volumes
        assert vols is not None
        assert len(vols) == 2

        assert_vol(vols, "/foo", "/host/foo")
        assert_vol(vols, "/bar", "/host/bar", ["z", "ro"])

    def test_volumes_with_env_vars_simple(self, monkeypatch) -> None:
        """volume definitions can contain environment variables"""
        monkeypatch.setenv("TEST_VOL_PATH", "/bar/baz")
        monkeypatch.setenv("TEST_VOL_PATH2", "/moo/doo")
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                volumes:
                  $TEST_VOL_PATH/foo: ${TEST_VOL_PATH2}/foo
                """
            )

        config = load_config()
        vols = config.volumes
        assert vols is not None
        assert len(vols) == 1

        assert_vol(vols, "/bar/baz/foo", "/moo/doo/foo")

    def test_volumes_with_env_vars_complex(self, monkeypatch) -> None:
        """complex volume definitions can contain environment variables"""
        monkeypatch.setenv("TEST_HOME", "/home/testuser")
        monkeypatch.setenv("TEST_TMP", "/tmp")
        monkeypatch.setenv("TEST_MAIL", "/var/spool/mail/testuser")

        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                volumes:
                  $TEST_HOME/.config: ${TEST_HOME}/.config
                  $TEST_TMP/:
                    hostpath: $TEST_HOME/scuba/myproject/tmp
                  /var/spool/mail/container:
                    hostpath: $TEST_MAIL
                    options: z,ro
                """
            )

        config = load_config()
        vols = config.volumes
        assert vols is not None
        assert len(vols) == 3

        assert_vol(vols, "/home/testuser/.config", "/home/testuser/.config")
        assert_vol(vols, "/tmp", "/home/testuser/scuba/myproject/tmp")
        assert_vol(
            vols, "/var/spool/mail/container", "/var/spool/mail/testuser", ["z", "ro"]
        )

    def test_volumes_with_invalid_env_vars(self, monkeypatch) -> None:
        """Volume definitions cannot include unset env vars"""
        # Ensure that the entry does not exist in the environment
        monkeypatch.delenv("TEST_VAR1", raising=False)
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                volumes:
                  $TEST_VAR1/foo: /host/foo
                """
            )
        self._invalid_config("TEST_VAR1")

    def test_volumes_hostpath_rel(self, monkeypatch, in_tmp_path) -> None:
        """volume hostpath can be relative to scuba_root (top dir)"""
        monkeypatch.setenv("RELVAR", "./spam/eggs")

        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                volumes:
                  /bar: ./foo/bar       # simple form, dotted path
                  /scp:                 # complex form
                    hostpath: ./snap/crackle/pop
                  /relvar: $RELVAR      # simple form, relative path in variable
                """
            )

        # Make a subdirectory and cd into it
        subdir = Path("way/down/here")
        subdir.mkdir(parents=True)
        monkeypatch.chdir(subdir)

        # Locate the config
        found_topdir, found_rel, config = scuba.config.find_config()
        assert found_topdir == in_tmp_path
        assert found_rel == subdir
        assert config.volumes is not None

        assert_vol(config.volumes, "/bar", in_tmp_path / "foo" / "bar")
        assert_vol(config.volumes, "/scp", in_tmp_path / "snap" / "crackle" / "pop")
        assert_vol(config.volumes, "/relvar", in_tmp_path / "spam" / "eggs")

    def test_volumes_hostpath_rel_above(self, monkeypatch, in_tmp_path) -> None:
        """volume hostpath can be relative, above scuba_root (top dir)"""
        # Directory structure:
        #
        # test-tmpdir/              # in_tmp_path
        # |- foo_up_here/           # will be mounted at /foo
        # |- way/
        #    |- down/
        #       |- here/            # scuba roo (found_topdir)
        #          |- .scuba.yml

        # First, make a subdirectory and cd into it
        project_dir = Path("way/down/here")
        project_dir.mkdir(parents=True)
        monkeypatch.chdir(project_dir)

        # Now put .scuba.yml here
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                volumes:
                  /foo: ../../../foo_up_here
                """
            )

        # Locate the config
        found_topdir, found_rel, config = scuba.config.find_config()
        assert found_topdir == in_tmp_path / project_dir
        assert found_rel == Path()

        assert config.volumes is not None
        assert_vol(config.volumes, "/foo", in_tmp_path / "foo_up_here")

    def test_volumes_hostpath_rel_req_dot_simple(
        self, monkeypatch, in_tmp_path
    ) -> None:
        """relaitve volume hostpath (simple form) must start with ./ or ../"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                volumes:
                  /one: foo  # Forbidden
                """
            )
        self._invalid_config("Relative path must start with ./ or ../")

    def test_volumes_hostpath_rel_requires_dot_complex(
        self, monkeypatch, in_tmp_path
    ) -> None:
        """relaitve volume hostpath (complex form) must start with ./ or ../"""
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                volumes:
                  /one:
                    hostpath: foo  # Forbidden
                """
            )
        self._invalid_config("Relative path must start with ./ or ../")

    def test_volumes_hostpath_rel_in_env(self, monkeypatch, in_tmp_path) -> None:
        """volume definitions can contain environment variables, including relative path portions"""
        monkeypatch.setenv("PREFIX", "./")
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                volumes:
                  /foo: ${PREFIX}/foo
                """
            )

        config = load_config()
        vols = config.volumes
        assert vols is not None
        assert len(vols) == 1

        assert_vol(vols, "/foo", in_tmp_path / "foo")

    def test_volumes_contpath_rel(self, monkeypatch, in_tmp_path) -> None:
        with open(".scuba.yml", "w") as f:
            f.write(
                r"""
                image: na
                volumes:
                  foo: /what/now
                """
            )
        self._invalid_config("Relative path not allowed: foo")
