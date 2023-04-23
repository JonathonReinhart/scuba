import pytest
import shlex

from scuba.config import ScubaConfig, ConfigError, OverrideStr
from scuba.scuba import ScubaContext


class TestScubaContext:
    def test_process_command_image(self):
        """process_command returns the image and entrypoint"""
        image_name = "test_image"
        entrypoint = "test_entrypoint"

        cfg = ScubaConfig(
            image=image_name,
            entrypoint=entrypoint,
        )
        result = ScubaContext.process_command(cfg, [])
        assert result.image == image_name
        assert result.entrypoint == entrypoint

    def test_process_command_empty(self):
        """process_command handles no aliases and an empty command"""
        cfg = ScubaConfig(
            image="na",
        )
        result = ScubaContext.process_command(cfg, [])
        assert result.script == None

    def test_process_command_no_aliases(self):
        """process_command handles no aliases"""
        cfg = ScubaConfig(
            image="na",
        )
        result = ScubaContext.process_command(cfg, ["cmd", "arg1", "arg2"])
        assert [shlex.split(s) for s in result.script] == [
            ["cmd", "arg1", "arg2"],
        ]

    def test_process_command_aliases_unused(self):
        """process_command handles unused aliases"""
        cfg = ScubaConfig(
            image="na",
            aliases=dict(
                apple="banana",
                cat="dog",
            ),
        )
        result = ScubaContext.process_command(cfg, ["cmd", "arg1", "arg2"])
        assert [shlex.split(s) for s in result.script] == [
            ["cmd", "arg1", "arg2"],
        ]

    def test_process_command_aliases_used_noargs(self):
        """process_command handles aliases with no args"""
        cfg = ScubaConfig(
            image="na",
            aliases=dict(
                apple="banana",
                cat="dog",
            ),
        )
        result = ScubaContext.process_command(cfg, ["apple", "arg1", "arg2"])
        assert [shlex.split(s) for s in result.script] == [
            ["banana", "arg1", "arg2"],
        ]

    def test_process_command_aliases_used_withargs(self):
        """process_command handles aliases with args"""
        cfg = ScubaConfig(
            image="na",
            aliases=dict(
                apple='banana cherry "pie is good"',
                cat="dog",
            ),
        )
        result = ScubaContext.process_command(
            cfg, ["apple", "arg1", "arg2 with spaces"]
        )
        assert [shlex.split(s) for s in result.script] == [
            ["banana", "cherry", "pie is good", "arg1", "arg2 with spaces"],
        ]

    def test_process_command_multiline_aliases_used(self):
        """process_command handles multiline aliases"""
        cfg = ScubaConfig(
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
        assert [shlex.split(s) for s in result.script] == [
            ["banana", "cherry", "pie is good"],
            ["so", "is", "peach"],
        ]

    def test_process_command_multiline_aliases_forbid_user_args(self):
        """process_command raises ConfigError when args are specified with multiline aliases"""
        cfg = ScubaConfig(
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

    def test_process_command_alias_overrides_image(self):
        """aliases can override the image"""
        cfg = ScubaConfig(
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

    def test_process_command_alias_overrides_image_and_entrypoint(self):
        """aliases can override the image and entrypoint"""
        cfg = ScubaConfig(
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

    def test_process_command_alias_overrides_image_and_empty_entrypoint(self):
        """aliases can override the image and empty/null entrypoint"""
        cfg = ScubaConfig(
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

    def test_process_command_image_override(self):
        """process_command allows image to be overridden when provided"""
        override_image_name = "override_image"

        cfg = ScubaConfig(
            image="test_image",
        )
        result = ScubaContext.process_command(
            cfg, [], image_override=override_image_name
        )
        assert result.image == override_image_name

    def test_process_command_image_override_missing(self):
        """process_command allows image to be overridden when not provided"""
        override_image_name = "override_image"

        cfg = ScubaConfig()
        result = ScubaContext.process_command(
            cfg, [], image_override=override_image_name
        )
        assert result.image == override_image_name

    def test_process_command_image_override_alias(self):
        """process_command allows image to be overridden when provided by alias"""
        override_image_name = "override_image"

        cfg = ScubaConfig(
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

    def test_env_merge(self):
        """process_command merges/overrides the environment from the alias"""
        cfg = ScubaConfig(
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

    def test_process_command_alias_extends_docker_args(self):
        """aliases can extend the docker_args"""
        cfg = ScubaConfig(
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

    def test_process_command_alias_overrides_docker_args(self):
        """aliases can override the docker_args"""
        cfg = ScubaConfig(
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

    def test_process_command_alias_overrides_docker_args_with_empty(self):
        """aliases can override the docker_args"""
        cfg = ScubaConfig(
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

    def test_process_command_alias_inherits_top_docker_args(self):
        """aliases inherit the top-level docker_args if not specified"""
        cfg = ScubaConfig(
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

    def test_process_command_alias_extends_volumes(self):
        """aliases can extend the volumes"""
        cfg = ScubaConfig(
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

        v = vols["/foo"]
        assert v.container_path == "/foo"
        assert v.host_path == "/host/foo"

        v = vols["/bar"]
        assert v.container_path == "/bar"
        assert v.host_path == "/host/bar"

    def test_process_command_alias_updates_volumes(self):
        """aliases can extend the volumes"""
        cfg = ScubaConfig(
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

        v = vols["/foo"]
        assert v.container_path == "/foo"
        assert v.host_path == "/alternate/foo"
