from pathlib import Path
import pytest
import subprocess
from typing import Sequence
from unittest import mock

from .const import ALT_DOCKER_IMAGE, DOCKER_IMAGE

import scuba.dockerutil as uut


def test_get_image_command_success() -> None:
    """get_image_command works"""
    assert uut.get_image_command(DOCKER_IMAGE)


def test_get_image_command_bad_image() -> None:
    """get_image_command raises an exception for a bad image name"""
    with pytest.raises(uut.DockerError):
        uut.get_image_command("nosuchimageZZZZZZZZ")


def test_get_image_no_docker() -> None:
    """get_image_command raises an exception if docker is not installed"""

    def mocked_run(args, real_run=subprocess.run, **kw):  # type: ignore[no-untyped-def]
        assert args[0] == "docker"
        args[0] = "dockerZZZZ"
        return real_run(args, **kw)

    with mock.patch("subprocess.run", side_effect=mocked_run) as run_mock:
        with pytest.raises(uut.DockerError):
            uut.get_image_command("n/a")


def _test_get_images(stdout: str, returncode: int = 0) -> Sequence[str]:
    def mocked_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        mock_obj = mock.MagicMock()
        mock_obj.returncode = returncode
        mock_obj.stdout = stdout
        return mock_obj

    with mock.patch("subprocess.run", side_effect=mocked_run) as run_mock:
        return uut.get_images()


def test_get_images_success__no_images() -> None:
    """get_images works when no images are present"""
    images = _test_get_images("")
    assert images == []


def test_get_images_success__multiple_images() -> None:
    """get_images works when many images are present"""
    output = """\
foo
foo:latest
bar
bar:snap
bar:latest
dummy/crackle
dummy/crackle:pop
"""
    images = _test_get_images(output)
    assert images == [
        "foo",
        "foo:latest",
        "bar",
        "bar:snap",
        "bar:latest",
        "dummy/crackle",
        "dummy/crackle:pop",
    ]


def test_get_images__failure() -> None:
    """get_images fails because of error"""
    with pytest.raises(uut.DockerError):
        _test_get_images("This is a pre-canned error", 1)


def test__get_image_command__pulls_image_if_missing() -> None:
    """get_image_command pulls an image if missing"""
    image = ALT_DOCKER_IMAGE

    # First remove the image
    subprocess.call(["docker", "rmi", image])

    # Now try to get the image's Command
    result = uut.get_image_command(image)

    # Should return a non-empty string
    assert result


def test_get_image_entrypoint() -> None:
    """get_image_entrypoint works"""
    result = uut.get_image_entrypoint("scuba/entrypoint-test")
    assert result == ["/entrypoint.sh"]


def test_get_image_entrypoint__none() -> None:
    """get_image_entrypoint works for image with no entrypoint"""
    result = uut.get_image_entrypoint(DOCKER_IMAGE)
    assert result is None


def test_make_vol_opt_no_opts() -> None:
    assert (
        uut.make_vol_opt(Path("/hostdir"), Path("/contdir"))
        == "--volume=/hostdir:/contdir"
    )


def test_make_vol_opt_empty_opts() -> None:
    assert (
        uut.make_vol_opt(Path("/hostdir"), Path("/contdir"), [])
        == "--volume=/hostdir:/contdir"
    )


def test_make_vol_opt_multi_opts() -> None:
    assert (
        uut.make_vol_opt(Path("/hostdir"), Path("/contdir"), ["ro", "z"])
        == "--volume=/hostdir:/contdir:ro,z"
    )


def test_make_vol_opt__requires_absolute() -> None:
    with pytest.raises(ValueError):
        uut.make_vol_opt(Path("hostdir"), Path("/contdir"))
