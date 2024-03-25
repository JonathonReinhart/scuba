import logging
import os
from pathlib import Path
import pytest
from typing import Optional
from unittest import mock

from .utils import assert_paths_equal, assert_vol

import scuba.config
from scuba.config import ScubaVolume


SCUBA_YML = Path(".scuba.yml")
GITLAB_YML = Path(".gitlab.yml")


def load_config(*, config_text: Optional[str] = None) -> scuba.config.ScubaConfig:
    if config_text is not None:
        SCUBA_YML.write_text(config_text)
    return scuba.config.load_config(SCUBA_YML, Path.cwd())


def invalid_config(
    *,
    config_text: Optional[str] = None,
    error_match: Optional[str] = None,
) -> None:
    with pytest.raises(scuba.config.ConfigError, match=error_match) as e:
        load_config(config_text=config_text)


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
class ConfigTest:
    pass


class TestFindConfig(ConfigTest):
    def test_find_config_cur_dir(self, in_tmp_path: Path) -> None:
        """find_config can find the config in the current directory"""
        SCUBA_YML.write_text("image: bosybux")

        path, rel, _ = scuba.config.find_config()
        assert_paths_equal(path, in_tmp_path)
        assert_paths_equal(rel, "")

    def test_find_config_parent_dir(self, in_tmp_path: Path) -> None:
        """find_config cuba can find the config in the parent directory"""
        SCUBA_YML.write_text("image: bosybux")

        subdir = Path("subdir")
        subdir.mkdir()
        os.chdir(subdir)

        # Verify our current working dir
        assert_paths_equal(Path.cwd(), in_tmp_path / subdir)

        path, rel, _ = scuba.config.find_config()
        assert_paths_equal(path, in_tmp_path)
        assert_paths_equal(rel, subdir)

    def test_find_config_way_up(self, in_tmp_path: Path) -> None:
        """find_config can find the config way up the directory hierarchy"""
        SCUBA_YML.write_text("image: bosybux")

        subdir = Path("foo/bar/snap/crackle/pop")
        subdir.mkdir(parents=True)
        os.chdir(subdir)

        # Verify our current working dir
        assert_paths_equal(Path.cwd(), in_tmp_path / subdir)

        path, rel, _ = scuba.config.find_config()
        assert_paths_equal(path, in_tmp_path)
        assert_paths_equal(rel, subdir)

    def test_find_config_nonexist(self) -> None:
        """find_config raises ConfigError if the config cannot be found"""
        with pytest.raises(scuba.config.ConfigError):
            scuba.config.find_config()


class TestLoadConfig(ConfigTest):
    def test_load_config_no_image(self) -> None:
        """load_config raises ConfigError if the config is empty and image is referenced"""
        config = load_config(config_text="")
        with pytest.raises(scuba.config.ConfigError):
            img = config.image

    def test_load_unexpected_node(self) -> None:
        """load_config raises ConfigError on unexpected config node"""
        invalid_config(
            config_text="""
            image: bosybux
            unexpected_node_123456: value
            """
        )

    def test_load_config_minimal(self) -> None:
        """load_config loads a minimal config"""
        config = load_config(config_text="image: bosybux")
        assert config.image == "bosybux"

    def test_load_config_with_aliases(self) -> None:
        """load_config loads a config with aliases"""
        config = load_config(
            config_text="""
            image: bosybux
            aliases:
              foo: bar
              snap: crackle pop
            """
        )
        assert config.image == "bosybux"
        assert len(config.aliases) == 2
        assert config.aliases["foo"].script == ["bar"]
        assert config.aliases["snap"].script == ["crackle pop"]

    def test_load_config__no_spaces_in_aliases(self) -> None:
        """load_config refuses spaces in aliases"""
        invalid_config(
            config_text="""
            image: bosybux
            aliases:
              this has spaces: whatever
            """
        )

    def test_load_config_image_from_yaml(self) -> None:
        """load_config loads a config using !from_yaml"""
        GITLAB_YML.write_text("image: dummian:8.2")
        config = load_config(config_text=f"image: !from_yaml {GITLAB_YML} image")
        assert config.image == "dummian:8.2"

    def test_load_config_image_from_yaml_nested_keys(self) -> None:
        """load_config loads a config using !from_yaml with nested keys"""
        GITLAB_YML.write_text(
            """
            somewhere:
              down:
                here: dummian:8.2
            """
        )
        config = load_config(
            config_text=f"image: !from_yaml {GITLAB_YML} somewhere.down.here"
        )
        assert config.image == "dummian:8.2"

    def test_load_config_image_from_yaml_nested_keys_with_escaped_characters(
        self,
    ) -> None:
        """load_config loads a config using !from_yaml with nested keys containing escaped '.' characters"""
        GITLAB_YML.write_text(
            """
            .its:
              somewhere.down:
                here: dummian:8.2
            """
        )
        config = load_config(
            config_text=f'image: !from_yaml {GITLAB_YML} "\\.its.somewhere\\.down.here"\n'
        )
        assert config.image == "dummian:8.2"

    def test_load_config_from_yaml_cached_file(self) -> None:
        """load_config loads a config using !from_yaml from cached version"""
        GITLAB_YML.write_text(
            """
            one: dummian:8.2
            two: dummian:9.3
            three: dummian:10.1
            """
        )
        SCUBA_YML.write_text(
            f"""
            image: !from_yaml {GITLAB_YML} one
            aliases:
              two:
                image:  !from_yaml {GITLAB_YML} two
                script: ugh
              three:
                image:  !from_yaml {GITLAB_YML} three
                script: ugh
            """
        )

        with mock.patch.object(Path, "open", autospec=True, side_effect=Path.open) as m:
            # Write config separately so its open() call is not counted here.
            config = load_config()

        # Assert that GITLAB_YML was only opened once
        assert m.mock_calls == [
            mock.call(SCUBA_YML, "r"),
            mock.call(GITLAB_YML, "r"),
        ]

    def test_load_config_image_from_yaml_nested_key_missing(self) -> None:
        """load_config raises ConfigError when !from_yaml references nonexistant key"""
        GITLAB_YML.write_text(
            """
            somewhere:
              down:
            """
        )
        invalid_config(
            config_text=f"image: !from_yaml {GITLAB_YML} somewhere.NONEXISTANT"
        )

    def test_load_config_image_from_yaml_missing_file(self) -> None:
        """load_config raises ConfigError when !from_yaml references nonexistant file"""
        invalid_config(config_text="image: !from_yaml .NONEXISTANT.yml image")

    def test_load_config_image_from_yaml_unicode_args(self) -> None:
        """load_config !from_yaml works with unicode args"""
        GITLAB_YML.write_text("𝕦𝕟𝕚𝕔𝕠𝕕𝕖: 𝕨𝕠𝕣𝕜𝕤:𝕠𝕜")
        config = load_config(config_text=f"image: !from_yaml {GITLAB_YML} 𝕦𝕟𝕚𝕔𝕠𝕕𝕖")
        assert config.image == "𝕨𝕠𝕣𝕜𝕤:𝕠𝕜"

    def test_load_config_image_from_yaml_missing_arg(self) -> None:
        """load_config raises ConfigError when !from_yaml has missing args"""
        GITLAB_YML.write_text("image: dummian:8.2")
        invalid_config(config_text=f"image: !from_yaml {GITLAB_YML}")

    def __test_load_config_safe(self, bad_yaml_path: Path) -> None:
        bad_yaml_path.write_text(
            """
            danger:
              - !!python/object/apply:print [Danger]
              - !!python/object/apply:sys.exit [66]
            """
        )
        pat = "could not determine a constructor for the tag.*python/object/apply"
        with pytest.raises(scuba.config.ConfigError, match=pat) as ctx:
            load_config()

    def test_load_config_safe(self) -> None:
        """load_config safely loads yaml"""
        self.__test_load_config_safe(SCUBA_YML)

    def test_load_config_safe_external(self) -> None:
        """load_config safely loads yaml from external files"""
        external_yml = Path(".external.yml")
        SCUBA_YML.write_text(f"image: !from_yaml {external_yml} danger")
        self.__test_load_config_safe(external_yml)


class TestConfigHooks(ConfigTest):
    def test_hooks_mixed(self) -> None:
        """hooks of mixed forms are valid"""
        config = load_config(
            config_text="""
            image: na
            hooks:
              root:
                script:
                  - echo "This runs before we switch users"
                  - id
              user: id
            """
        )
        assert config.hooks.get("root") == [
            'echo "This runs before we switch users"',
            "id",
        ]
        assert config.hooks.get("user") == ["id"]

    def test_hooks_invalid_list(self) -> None:
        """hooks with list not under "script" key are invalid"""
        invalid_config(
            config_text="""
            image: na
            hooks:
              user:
                - this list should be under
                - a 'script'
            """
        )

    def test_hooks_missing_script(self) -> None:
        """hooks with dict, but missing "script" are invalid"""
        invalid_config(
            config_text="""
            image: na
            hooks:
              user:
                not_script: missing "script" key
            """
        )


class TestConfigEnv(ConfigTest):
    def test_env_invalid(self) -> None:
        """Environment must be dict or list of strings"""
        invalid_config(
            config_text=r"""
            image: na
            environment: 666
            """,
            error_match="must be list or mapping",
        )

    def test_env_top_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Top-level environment can be loaded (dict)"""
        monkeypatch.setenv("EXTERNAL", "Outside world")
        monkeypatch.delenv("EXTERNAL_NOTSET", raising=False)
        config = load_config(
            config_text=r"""
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

    def test_env_top_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Top-level environment can be loaded (list)"""
        monkeypatch.setenv("EXTERNAL", "Outside world")
        monkeypatch.delenv("EXTERNAL_NOTSET", raising=False)
        config = load_config(
            config_text=r"""
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
        config = load_config(
            config_text=r"""
            image: na
            aliases:
              al:
                script: Don't care
                environment:
                  FOO: Overridden
                  MORE: Hello world
            """
        )
        assert config.aliases["al"].environment == dict(
            FOO="Overridden",
            MORE="Hello world",
        )


class TestConfigEntrypoint(ConfigTest):
    def test_entrypoint_not_set(self) -> None:
        """Entrypoint can be missing"""
        config = load_config(config_text="image: na")
        assert config.entrypoint is None

    def test_entrypoint_null(self) -> None:
        """Entrypoint can be set to null"""
        config = load_config(
            config_text=r"""
            image: na
            entrypoint:
            """
        )
        assert config.entrypoint == ""  # Null => empty string

    def test_entrypoint_invalid(self) -> None:
        """Entrypoint of incorrect type raises ConfigError"""
        invalid_config(
            config_text=r"""
            image: na
            entrypoint: 666
            """,
            error_match="must be a string",
        )

    def test_entrypoint_empty_string(self) -> None:
        """Entrypoint can be set to an empty string"""
        config = load_config(
            config_text=r"""
            image: na
            entrypoint: ""
            """
        )
        assert config.entrypoint == ""

    def test_entrypoint_set(self) -> None:
        """Entrypoint can be set"""
        config = load_config(
            config_text=r"""
            image: na
            entrypoint: my_ep
            """
        )
        assert config.entrypoint == "my_ep"

    def test_alias_entrypoint_null(self) -> None:
        """Entrypoint can be set to null via alias"""
        config = load_config(
            config_text=r"""
            image: na
            entrypoint: na_ep
            aliases:
              testalias:
                entrypoint:
                script:
                  - ugh
            """
        )
        assert config.aliases["testalias"].entrypoint == ""  # Null => empty string

    def test_alias_entrypoint_empty_string(self) -> None:
        """Entrypoint can be set to an empty string via alias"""
        config = load_config(
            config_text=r"""
            image: na
            entrypoint: na_ep
            aliases:
              testalias:
                entrypoint: ""
                script:
                  - ugh
            """
        )
        assert config.aliases["testalias"].entrypoint == ""

    def test_alias_entrypoint(self) -> None:
        """Entrypoint can be set via alias"""
        config = load_config(
            config_text=r"""
            image: na
            entrypoint: na_ep
            aliases:
              testalias:
                entrypoint: use_this_ep
                script:
                  - ugh
            """
        )
        assert config.aliases["testalias"].entrypoint == "use_this_ep"


class TestConfigDockerArgs(ConfigTest):
    def test_docker_args_not_set(self) -> None:
        """docker_args can be missing"""
        config = load_config(config_text="image: na")
        assert config.docker_args is None

    def test_docker_args_invalid(self) -> None:
        """docker_args of incorrect type raises ConfigError"""
        invalid_config(
            config_text=r"""
            image: na
            docker_args: 666
            """,
            error_match="must be a string",
        )

    def test_docker_args_null(self) -> None:
        """docker_args can be set to null"""
        config = load_config(
            config_text=r"""
            image: na
            docker_args:
            """
        )
        assert config.docker_args == []

    def test_docker_args_set_empty_string(self) -> None:
        """docker_args can be set to empty string"""
        config = load_config(
            config_text=r"""
            image: na
            docker_args: ''
            """
        )
        assert config.docker_args == []  # '' -> [] after shlex.split()

    def test_docker_args_set(self) -> None:
        """docker_args can be set"""
        config = load_config(
            config_text=r"""
            image: na
            docker_args: --privileged
            """
        )
        assert config.docker_args == ["--privileged"]

    def test_docker_args_set_multi(self) -> None:
        """docker_args can be set to multiple args"""
        config = load_config(
            config_text=r"""
            image: na
            docker_args: --privileged -v /tmp/:/tmp/
            """
        )
        assert config.docker_args == ["--privileged", "-v", "/tmp/:/tmp/"]

    def test_alias_docker_args_null(self) -> None:
        """docker_args can be set to null via alias"""
        config = load_config(
            config_text=r"""
            image: na
            docker_args: --privileged
            aliases:
              testalias:
                docker_args:
                script:
                  - ugh
            """
        )
        assert config.aliases["testalias"].docker_args == []

    def test_alias_docker_args_empty_string(self) -> None:
        """docker_args can be set to empty string via alias"""
        config = load_config(
            config_text=r"""
            image: na
            docker_args: --privileged
            aliases:
              testalias:
                docker_args: ''
                script:
                  - ugh
            """
        )
        assert config.aliases["testalias"].docker_args == []

    def test_alias_docker_args_set(self) -> None:
        """docker_args can be set via alias"""
        config = load_config(
            config_text=r"""
            image: na
            docker_args: --privileged
            aliases:
              testalias:
                docker_args: -v /tmp/:/tmp/
                script:
                  - ugh
            """
        )
        assert config.aliases["testalias"].docker_args == ["-v", "/tmp/:/tmp/"]

    def test_alias_docker_args_override(self) -> None:
        """docker_args can be tagged for override"""
        config = load_config(
            config_text=r"""
            image: na
            docker_args: --privileged
            aliases:
              testalias:
                docker_args: !override -v /tmp/:/tmp/
                script:
                  - ugh
            """
        )
        assert config.aliases["testalias"].docker_args == ["-v", "/tmp/:/tmp/"]
        assert isinstance(
            config.aliases["testalias"].docker_args, scuba.config.OverrideMixin
        )

    def test_alias_docker_args_override_implicit_null(self) -> None:
        """docker_args can be overridden with an implicit null value"""
        config = load_config(
            config_text=r"""
            image: na
            docker_args: --privileged
            aliases:
              testalias:
                docker_args: !override
                script:
                  - ugh
            """
        )
        assert config.aliases["testalias"].docker_args == []
        assert isinstance(
            config.aliases["testalias"].docker_args, scuba.config.OverrideMixin
        )

    def test_alias_docker_args_override_from_yaml(self) -> None:
        """!override tag can be applied before a !from_yaml tag"""
        args_yml = Path("args.yml")
        args_yml.write_text("args: -v /tmp/:/tmp/")

        config = load_config(
            config_text=rf"""
            image: na
            docker_args: --privileged
            aliases:
              testalias:
                docker_args: !override '!from_yaml {args_yml} args'
                script:
                  - ugh
            """
        )
        assert config.aliases["testalias"].docker_args == ["-v", "/tmp/:/tmp/"]
        assert isinstance(
            config.aliases["testalias"].docker_args, scuba.config.OverrideMixin
        )

    def test_alias_docker_args_from_yaml_override(self) -> None:
        """!override tag can be applied inside of a !from_yaml tag"""
        args_yml = Path("args.yml")
        args_yml.write_text("args: !override -v /tmp/:/tmp/")

        config = load_config(
            config_text=rf"""
            image: na
            docker_args: --privileged
            aliases:
              testalias:
                docker_args: !from_yaml {args_yml} args
                script:
                  - ugh
            """
        )
        assert config.aliases["testalias"].docker_args == ["-v", "/tmp/:/tmp/"]
        assert isinstance(
            config.aliases["testalias"].docker_args, scuba.config.OverrideMixin
        )


class TestConfigVolumes(ConfigTest):
    def test_not_set(self) -> None:
        """volumes can be missing"""
        config = load_config(config_text="image: na")
        assert config.volumes is None

    def test_null(self) -> None:
        """volumes can be set to null"""
        config = load_config(
            config_text=r"""
            image: na
            volumes:
            """
        )
        assert config.volumes == None

    def test_invalid_int(self) -> None:
        """volumes of incorrect type (int) raises ConfigError"""
        invalid_config(
            config_text=r"""
            image: na
            volumes: 666
            """,
            error_match="must be a dict",
        )

    def test_invalid_list(self) -> None:
        """volume of incorrect type (list) raises ConfigError"""
        invalid_config(
            config_text=r"""
            image: na
            volumes:
              /foo:
                - a list makes no sense
            """,
            error_match="must be string or dict",
        )

    def test_null_volume_type(self) -> None:
        """volume of None type raises ConfigError"""
        # NOTE: In the future, we might want to support this as a volume
        #       (non-bindmount, e.g. '-v /somedata'), or as tmpfs
        invalid_config(
            config_text=r"""
            image: na
            volumes:
              /bar:
            """,
            error_match="hostpath",
        )

    def test_complex_missing_hostpath(self) -> None:
        """volume of incorrect type raises ConfigError"""
        # NOTE: In the future, we might want to support this as a volume
        #       (non-bindmount, e.g. '-v /somedata'), or as tmpfs
        invalid_config(
            config_text=r"""
            image: na
            volumes:
              /bar:
                options: hostpath,is,missing
            """,
            error_match="hostpath",
        )

    def test_simple_bind(self) -> None:
        """volumes can be set using the simple form"""
        config = load_config(
            config_text=r"""
            image: na
            volumes:
              /cpath: /hpath
            """
        )
        assert config.volumes is not None
        assert len(config.volumes) == 1

        assert_vol(config.volumes, "/cpath", "/hpath")

    def test_complex_bind(self) -> None:
        """volumes can be set using the complex form"""
        config = load_config(
            config_text=r"""
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
        vols = config.volumes
        assert vols is not None
        assert len(vols) == 3

        assert_vol(vols, "/foo", "/host/foo")
        assert_vol(vols, "/bar", "/host/bar")
        assert_vol(vols, "/snap", "/host/snap", ["z", "ro"])

    def test_complex_named_volume(self) -> None:
        """volumes complex form can specify a named volume"""
        config = load_config(
            config_text=r"""
            image: na
            volumes:
              /foo:
                name: foo-volume
            """
        )
        assert config.volumes is not None
        assert len(config.volumes) == 1
        vol = config.volumes[Path("/foo")]

        assert isinstance(vol, ScubaVolume)
        assert_paths_equal(vol.container_path, "/foo")
        assert vol.volume_name == "foo-volume"

    def test_via_alias(self) -> None:
        """volumes can be set via alias"""
        config = load_config(
            config_text=r"""
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
        vols = config.aliases["testalias"].volumes
        assert vols is not None
        assert len(vols) == 2

        assert_vol(vols, "/foo", "/host/foo")
        assert_vol(vols, "/bar", "/host/bar", ["z", "ro"])

    def test_with_env_vars_simple(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """volume definitions can contain environment variables"""
        monkeypatch.setenv("TEST_VOL_PATH", "/bar/baz")
        monkeypatch.setenv("TEST_VOL_PATH2", "/moo/doo")
        config = load_config(
            config_text=r"""
            image: na
            volumes:
              $TEST_VOL_PATH/foo: ${TEST_VOL_PATH2}/foo
            """
        )
        vols = config.volumes
        assert vols is not None
        assert len(vols) == 1

        assert_vol(vols, "/bar/baz/foo", "/moo/doo/foo")

    def test_with_env_vars_complex(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """complex volume definitions can contain environment variables"""
        monkeypatch.setenv("TEST_HOME", "/home/testuser")
        monkeypatch.setenv("TEST_TMP", "/tmp")
        monkeypatch.setenv("TEST_MAIL", "/var/spool/mail/testuser")

        config = load_config(
            config_text=r"""
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
        vols = config.volumes
        assert vols is not None
        assert len(vols) == 3

        assert_vol(vols, "/home/testuser/.config", "/home/testuser/.config")
        assert_vol(vols, "/tmp", "/home/testuser/scuba/myproject/tmp")
        assert_vol(
            vols, "/var/spool/mail/container", "/var/spool/mail/testuser", ["z", "ro"]
        )

    def test_with_invalid_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Volume definitions cannot include unset env vars"""
        # Ensure that the entry does not exist in the environment
        monkeypatch.delenv("TEST_VAR1", raising=False)
        invalid_config(
            config_text=r"""
            image: na
            volumes:
              $TEST_VAR1/foo: /host/foo
            """,
            error_match="TEST_VAR1",
        )

    def test_hostpath_rel(
        self, monkeypatch: pytest.MonkeyPatch, in_tmp_path: Path
    ) -> None:
        """volume hostpath can be relative to scuba_root (top dir)"""
        monkeypatch.setenv("RELVAR", "./spam/eggs")

        SCUBA_YML.write_text(
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

    def test_hostpath_rel_above(
        self, monkeypatch: pytest.MonkeyPatch, in_tmp_path: Path
    ) -> None:
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
        SCUBA_YML.write_text(
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

    def test_hostpath_rel_requires_dot_complex(self) -> None:
        """relaitve volume hostpath (complex form) must start with ./ or ../"""
        invalid_config(
            config_text=r"""
            image: na
            volumes:
              /one:
                hostpath: foo  # Forbidden
            """,
            error_match="Relative path must start with ./ or ../",
        )

    def test_hostpath_rel_in_env(
        self, monkeypatch: pytest.MonkeyPatch, in_tmp_path: Path
    ) -> None:
        """volume definitions can contain environment variables, including relative path portions"""
        monkeypatch.setenv("PREFIX", "./")
        config = load_config(
            config_text=r"""
            image: na
            volumes:
              /foo: ${PREFIX}/foo
            """
        )
        vols = config.volumes
        assert vols is not None
        assert len(vols) == 1

        assert_vol(vols, "/foo", in_tmp_path / "foo")

    def test_contpath_rel(self) -> None:
        invalid_config(
            config_text=r"""
            image: na
            volumes:
              foo: /what/now
            """,
            error_match="Relative path not allowed: foo",
        )

    def test_simple_named_volume(self) -> None:
        """volumes simple form can specify a named volume"""
        config = load_config(
            config_text=r"""
            image: na
            volumes:
              /foo: foo-volume
            """
        )
        assert config.volumes is not None
        assert len(config.volumes) == 1
        vol = config.volumes[Path("/foo")]

        assert isinstance(vol, ScubaVolume)
        assert_paths_equal(vol.container_path, "/foo")
        assert vol.volume_name == "foo-volume"

    def test_simple_named_volume_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """volumes simple form can specify a named volume via env var"""
        monkeypatch.setenv("FOO_VOLUME", "foo-volume")
        config = load_config(
            config_text=r"""
            image: na
            volumes:
              /foo: $FOO_VOLUME
            """
        )
        assert config.volumes is not None
        assert len(config.volumes) == 1
        vol = config.volumes[Path("/foo")]

        assert isinstance(vol, ScubaVolume)
        assert_paths_equal(vol.container_path, "/foo")
        assert vol.volume_name == "foo-volume"

    def test_complex_named_volume_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """volumes complex form can specify a named volume via env var"""
        monkeypatch.setenv("FOO_VOLUME", "foo-volume")
        config = load_config(
            config_text=r"""
            image: na
            volumes:
              /foo:
                name: $FOO_VOLUME
            """
        )
        assert config.volumes is not None
        assert len(config.volumes) == 1
        vol = config.volumes[Path("/foo")]

        assert isinstance(vol, ScubaVolume)
        assert_paths_equal(vol.container_path, "/foo")
        assert vol.volume_name == "foo-volume"

    def test_complex_named_volume_env_unset(self) -> None:
        """volumes complex form fails on unset env var"""
        invalid_config(
            config_text=r"""
            image: na
            volumes:
              /foo:
                name: $FOO_VOLUME
            """,
            error_match="Unset environment variable",
        )

    def test_complex_invalid_hostpath(self) -> None:
        """volumes complex form cannot specify an invalid hostpath"""
        invalid_config(
            config_text=r"""
            image: na
            volumes:
              /foo:
                hostpath: foo-volume
            """,
            error_match="Relative path must start with ./ or ../",
        )

    def test_complex_hostpath_and_name(self) -> None:
        """volumes complex form cannot specify a named volume and hostpath"""
        invalid_config(
            config_text=r"""
            image: na
            volumes:
              /foo:
                hostpath: /bar
                name: foo-volume
            """,
            error_match="Volume /foo must have exactly one of 'hostpath' or 'name' subkey",
        )

    def test_complex_empty(self) -> None:
        """volumes complex form cannot be empty"""
        invalid_config(
            config_text=r"""
            image: na
            volumes:
              /foo:
            """,
            error_match="Volume /foo must have exactly one of 'hostpath' or 'name' subkey",
        )
