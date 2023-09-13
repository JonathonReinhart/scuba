import pytest
import shlex
from typing import Any
from .utils import assert_vol

from scuba.config import ScubaConfig, ConfigError, OverrideStr
from scuba.scuba import ScubaContext


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
