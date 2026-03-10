import pytest
import shlex
import tempfile
from pathlib import Path
from typing import Any
from unittest import mock
from .utils import assert_vol

from scuba.config import ScubaConfig, ConfigError, OverrideStr
from scuba.scuba import ScubaContext, ScubaDive, ScubaError


# This exists simply to adapt all of the existing, simple kwargs-style callers
# to the new one-dict argument ScubaConfig.__init__().
def make_config(**data: Any) -> ScubaConfig:
    return ScubaConfig(data)


class TestScubaContext:
    def test_process_command_image(self) -> None:
        """process_command returns the image and entrypoint"""
        image_name = "test_image"
        entrypoint = "test_entrypoint"

        cfg = make_config(
            image=image_name,
            entrypoint=entrypoint,
        )
        result = ScubaContext.process_command(cfg, [])
        assert result.image == image_name
        assert result.entrypoint == entrypoint

    def test_process_command_empty(self) -> None:
        """process_command handles no aliases and an empty command"""
        cfg = make_config(
            image="na",
        )
        result = ScubaContext.process_command(cfg, [])
        assert result.script == None

    def test_process_command_no_aliases(self) -> None:
        """process_command handles no aliases"""
        cfg = make_config(
            image="na",
        )
        result = ScubaContext.process_command(cfg, ["cmd", "arg1", "arg2"])
        assert result.script is not None
        assert [shlex.split(s) for s in result.script] == [
            ["cmd", "arg1", "arg2"],
        ]

    def test_process_command_aliases_unused(self) -> None:
        """process_command handles unused aliases"""
        cfg = make_config(
            image="na",
            aliases=dict(
                apple="banana",
                cat="dog",
            ),
        )
        result = ScubaContext.process_command(cfg, ["cmd", "arg1", "arg2"])
        assert result.script is not None
        assert [shlex.split(s) for s in result.script] == [
            ["cmd", "arg1", "arg2"],
        ]

    def test_process_command_aliases_used_noargs(self) -> None:
        """process_command handles aliases with no args"""
        cfg = make_config(
            image="na",
            aliases=dict(
                apple="banana",
                cat="dog",
            ),
        )
        result = ScubaContext.process_command(cfg, ["apple", "arg1", "arg2"])
        assert result.script is not None
        assert [shlex.split(s) for s in result.script] == [
            ["banana", "arg1", "arg2"],
        ]

    def test_process_command_aliases_used_withargs(self) -> None:
        """process_command handles aliases with args"""
        cfg = make_config(
            image="na",
            aliases=dict(
                apple='banana cherry "pie is good"',
                cat="dog",
            ),
        )
        result = ScubaContext.process_command(
            cfg, ["apple", "arg1", "arg2 with spaces"]
        )
        assert result.script is not None
        assert [shlex.split(s) for s in result.script] == [
            ["banana", "cherry", "pie is good", "arg1", "arg2 with spaces"],
        ]

    def test_process_command_multiline_aliases_used(self) -> None:
        """process_command handles multiline aliases"""
        cfg = make_config(
            image="na",
            aliases=dict(
                apple=dict(
                    script=[
                        'banana cherry "pie is good"',
                        "so is peach",
                    ]
                ),
                cat="dog",
            ),
        )
        result = ScubaContext.process_command(cfg, ["apple"])
        assert result.script is not None
        assert [shlex.split(s) for s in result.script] == [
            ["banana", "cherry", "pie is good"],
            ["so", "is", "peach"],
        ]

    def test_process_command_multiline_aliases_forbid_user_args(self) -> None:
        """process_command raises ConfigError when args are specified with multiline aliases"""
        cfg = make_config(
            image="na",
            aliases=dict(
                apple=dict(
                    script=[
                        'banana cherry "pie is good"',
                        "so is peach",
                    ]
                ),
                cat="dog",
            ),
        )
        with pytest.raises(ConfigError):
            ScubaContext.process_command(cfg, ["apple", "ARGS", "NOT ALLOWED"])

    def test_process_command_alias_overrides_image(self) -> None:
        """aliases can override the image"""
        cfg = make_config(
            image="default",
            aliases=dict(
                apple=dict(
                    script=[
                        'banana cherry "pie is good"',
                        "so is peach",
                    ],
                    image="overridden",
                ),
            ),
        )
        result = ScubaContext.process_command(cfg, ["apple"])
        assert result.image == "overridden"

    def test_process_command_alias_overrides_image_and_entrypoint(self) -> None:
        """aliases can override the image and entrypoint"""
        cfg = make_config(
            image="default",
            entrypoint="default_entrypoint",
            aliases=dict(
                apple=dict(
                    script=[
                        'banana cherry "pie is good"',
                        "so is peach",
                    ],
                    image="overridden",
                    entrypoint="overridden_entrypoint",
                ),
            ),
        )
        result = ScubaContext.process_command(cfg, ["apple"])
        assert result.image == "overridden"
        assert result.entrypoint == "overridden_entrypoint"

    def test_process_command_alias_overrides_image_and_empty_entrypoint(self) -> None:
        """aliases can override the image and empty/null entrypoint"""
        cfg = make_config(
            image="default",
            entrypoint="default_entrypoint",
            aliases=dict(
                apple=dict(
                    script=[
                        'banana cherry "pie is good"',
                        "so is peach",
                    ],
                    image="overridden",
                    entrypoint="",
                ),
            ),
        )
        result = ScubaContext.process_command(cfg, ["apple"])
        assert result.image == "overridden"
        assert result.entrypoint == ""

    def test_process_command_image_override(self) -> None:
        """process_command allows image to be overridden when provided"""
        override_image_name = "override_image"

        cfg = make_config(
            image="test_image",
        )
        result = ScubaContext.process_command(
            cfg, [], image_override=override_image_name
        )
        assert result.image == override_image_name

    def test_process_command_image_override_missing(self) -> None:
        """process_command allows image to be overridden when not provided"""
        override_image_name = "override_image"

        cfg = make_config()
        result = ScubaContext.process_command(
            cfg, [], image_override=override_image_name
        )
        assert result.image == override_image_name

    def test_process_command_image_override_alias(self) -> None:
        """process_command allows image to be overridden when provided by alias"""
        override_image_name = "override_image"

        cfg = make_config(
            aliases=dict(
                apple=dict(
                    script=[
                        'banana cherry "pie is good"',
                        "so is peach",
                    ],
                    image="apple_image",
                ),
            )
        )
        result = ScubaContext.process_command(
            cfg, [], image_override=override_image_name
        )
        assert result.image == override_image_name

    def test_env_merge(self) -> None:
        """process_command merges/overrides the environment from the alias"""
        cfg = make_config(
            image="dontcare",
            environment=dict(
                AAA="aaa_base",
                BBB="bbb_base",
            ),
            aliases=dict(
                test=dict(
                    script="dontcare",
                    environment=dict(
                        BBB="bbb_overridden",
                        CCC="ccc_overridden",
                    ),
                ),
            ),
        )
        result = ScubaContext.process_command(cfg, ["test"])
        expected = dict(
            AAA="aaa_base",
            BBB="bbb_overridden",
            CCC="ccc_overridden",
        )
        assert result.environment == expected

    def test_process_command_alias_extends_docker_args(self) -> None:
        """aliases can extend the docker_args"""
        cfg = make_config(
            image="default",
            docker_args="--privileged",
            aliases=dict(
                apple=dict(
                    script=[
                        'banana cherry "pie is good"',
                    ],
                    docker_args="-v /tmp/:/tmp/",
                ),
            ),
        )
        result = ScubaContext.process_command(cfg, ["apple"])
        assert result.docker_args == ["--privileged", "-v", "/tmp/:/tmp/"]

    def test_process_command_alias_overrides_docker_args(self) -> None:
        """aliases can override the docker_args"""
        cfg = make_config(
            image="default",
            docker_args="--privileged",
            aliases=dict(
                apple=dict(
                    script=[
                        'banana cherry "pie is good"',
                    ],
                    docker_args=OverrideStr("-v /tmp/:/tmp/"),
                ),
            ),
        )
        result = ScubaContext.process_command(cfg, ["apple"])
        assert result.docker_args == ["-v", "/tmp/:/tmp/"]

    def test_process_command_alias_overrides_docker_args_with_empty(self) -> None:
        """aliases can override the docker_args"""
        cfg = make_config(
            image="default",
            docker_args="--privileged",
            aliases=dict(
                apple=dict(
                    script=[
                        'banana cherry "pie is good"',
                    ],
                    docker_args=OverrideStr(""),
                ),
            ),
        )
        result = ScubaContext.process_command(cfg, ["apple"])
        assert result.docker_args == []

    def test_process_command_alias_inherits_top_docker_args(self) -> None:
        """aliases inherit the top-level docker_args if not specified"""
        cfg = make_config(
            image="default",
            docker_args="--privileged",
            aliases=dict(
                apple=dict(
                    script=[
                        'banana cherry "pie is good"',
                    ],
                ),
            ),
        )
        result = ScubaContext.process_command(cfg, ["apple"])
        assert result.docker_args == ["--privileged"]

    ############################################################################
    # volumes

    def test_process_command_alias_extends_volumes(self) -> None:
        """aliases can extend the volumes"""
        cfg = make_config(
            image="default",
            volumes={
                "/foo": "/host/foo",
            },
            aliases=dict(
                apple=dict(
                    script=[
                        'banana cherry "pie is good"',
                    ],
                    volumes={
                        "/bar": "/host/bar",
                    },
                ),
            ),
        )
        result = ScubaContext.process_command(cfg, ["apple"])
        vols = result.volumes
        assert len(vols) == 2

        assert_vol(vols, "/foo", "/host/foo")
        assert_vol(vols, "/bar", "/host/bar")

    def test_process_command_alias_updates_volumes(self) -> None:
        """aliases can extend the volumes"""
        cfg = make_config(
            image="default",
            volumes={
                "/foo": "/host/foo",
            },
            aliases=dict(
                apple=dict(
                    script=[
                        'banana cherry "pie is good"',
                    ],
                    volumes={
                        "/foo": "/alternate/foo",
                    },
                ),
            ),
        )
        result = ScubaContext.process_command(cfg, ["apple"])
        vols = result.volumes
        assert len(vols) == 1

        assert_vol(vols, "/foo", "/alternate/foo")

    ############################################################################
    # su-root

    def test_process_command_alias_su_root(self) -> None:
        """process_command propagates as_su_root from alias"""
        cfg = make_config(
            image="default",
            aliases=dict(
                build=dict(
                    script="make all",
                    su_root=True,
                ),
            ),
        )
        result = ScubaContext.process_command(cfg, ["build"])
        assert result.as_su_root is True


def _make_passwd_entry(uid: int, name: str) -> mock.Mock:
    entry = mock.Mock()
    entry.pw_name = name
    entry.pw_uid = uid
    return entry


def _make_group_entry(gid: int, name: str) -> mock.Mock:
    entry = mock.Mock()
    entry.gr_name = name
    entry.gr_gid = gid
    return entry


class TestScubaDiveSuRoot:
    """Tests for ScubaDive su-root mutual exclusion behavior."""

    def _make_dive(
        self,
        alias_dict: dict[str, object],
        cli_root: bool = False,
        cli_su_root: bool = False,
    ) -> ScubaDive:
        """Helper to create a ScubaDive with mocked system calls."""
        config = ScubaConfig(
            {"image": "test_image", "aliases": {"myalias": alias_dict}}
        )

        tmp_dir = tempfile.mkdtemp()
        top_path = Path(tmp_dir)
        fake_scubainit = top_path / "scubainit"
        fake_scubainit.write_bytes(b"\x00")

        with (
            mock.patch("scuba.scuba.os.getuid", return_value=1000),
            mock.patch("scuba.scuba.os.getgid", return_value=1000),
            mock.patch(
                "scuba.scuba.getpwuid",
                return_value=_make_passwd_entry(1000, "testuser"),
            ),
            mock.patch(
                "scuba.scuba.getgrgid",
                return_value=_make_group_entry(1000, "testgroup"),
            ),
            mock.patch("scuba.scuba.get_image_command", return_value=["bash"]),
            mock.patch("scuba.scuba.get_image_entrypoint", return_value=None),
            mock.patch.object(
                ScubaDive,
                "_ScubaDive__locate_scubainit",
                return_value=str(fake_scubainit),
            ),
        ):
            dive = ScubaDive(
                user_command=["myalias"],
                config=config,
                top_path=top_path,
                top_rel=Path("."),
                as_root=cli_root,
                as_su_root=cli_su_root,
            )
            return dive

    def test_cli_su_root_with_alias_root_raises(self) -> None:
        """CLI --su-root combined with alias root: true raises ScubaError"""
        with pytest.raises(ScubaError, match="mutually exclusive"):
            dive = self._make_dive(
                alias_dict={"script": "echo test", "root": True},
                cli_su_root=True,
            )
            dive._cleanup()

    def test_cli_root_with_alias_su_root_raises(self) -> None:
        """CLI --root combined with alias su_root: true raises ScubaError"""
        with pytest.raises(ScubaError, match="mutually exclusive"):
            dive = self._make_dive(
                alias_dict={"script": "echo test", "su_root": True},
                cli_root=True,
            )
            dive._cleanup()


class TestCliSuRoot:
    """Tests for CLI --su-root / -S flag parsing and dry-run output."""

    def test_su_root_long_flag_accepted(self) -> None:
        """--su-root flag is accepted and sets su_root=True"""
        from scuba.__main__ import parse_scuba_args

        args = parse_scuba_args(["--su-root", "echo", "hi"])
        assert args.su_root is True

    def test_su_root_short_flag_accepted(self) -> None:
        """-S short form is accepted and sets su_root=True"""
        from scuba.__main__ import parse_scuba_args

        args = parse_scuba_args(["-S", "echo", "hi"])
        assert args.su_root is True

    def test_root_and_su_root_mutually_exclusive(self) -> None:
        """--root --su-root together causes an error exit"""
        from scuba.__main__ import parse_scuba_args

        with pytest.raises(SystemExit):
            parse_scuba_args(["--root", "--su-root", "echo", "hi"])

    def test_dry_run_su_root_includes_env_var(self) -> None:
        """Dry-run with --su-root includes SCUBAINIT_SU_ROOT in docker cmdline"""
        config = ScubaConfig({"image": "test_image"})
        tmp_dir = tempfile.mkdtemp()
        top_path = Path(tmp_dir)
        fake_scubainit = top_path / "scubainit"
        fake_scubainit.write_bytes(b"\x00")

        with (
            mock.patch("scuba.scuba.os.getuid", return_value=1000),
            mock.patch("scuba.scuba.os.getgid", return_value=1000),
            mock.patch(
                "scuba.scuba.getpwuid",
                return_value=_make_passwd_entry(1000, "testuser"),
            ),
            mock.patch(
                "scuba.scuba.getgrgid",
                return_value=_make_group_entry(1000, "testgroup"),
            ),
            mock.patch("scuba.scuba.get_image_command", return_value=["bash"]),
            mock.patch("scuba.scuba.get_image_entrypoint", return_value=None),
            mock.patch.object(
                ScubaDive,
                "_ScubaDive__locate_scubainit",
                return_value=str(fake_scubainit),
            ),
        ):
            dive = ScubaDive(
                user_command=["echo", "hi"],
                config=config,
                top_path=top_path,
                top_rel=Path("."),
                as_su_root=True,
                keep_tempfiles=True,
            )
            cmdline = dive.get_docker_cmdline()
            cmdline_str = " ".join(cmdline)
            assert "SCUBAINIT_SU_ROOT=1" in cmdline_str
            dive._cleanup()
