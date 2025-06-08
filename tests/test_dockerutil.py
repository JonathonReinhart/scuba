from pathlib import Path
import pytest
import subprocess
from typing import Optional, Sequence
from unittest import mock

from .const import ALT_DOCKER_IMAGE, DOCKER_IMAGE

import scuba.dockerutil as uut


def _mock_subprocess_run(  # type: ignore[no-untyped-def]
    stdout: str,
    returncode: int = 0,
    expected_args: Optional[Sequence[str]] = None,
):  # -> mock._patch[mock.MagicMock]:
    def mocked_run(args, **kwargs):  # type: ignore[no-untyped-def]
        assert expected_args is None or args == expected_args
        mock_obj = mock.MagicMock()
        mock_obj.returncode = returncode
        mock_obj.stdout = stdout
        return mock_obj

    return mock.patch("subprocess.run", side_effect=mocked_run)


# -----------------------------------------------------------------------------
# get_image_command()


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


def test__get_image_command__pulls_image_if_missing() -> None:
    """get_image_command pulls an image if missing"""
    image = ALT_DOCKER_IMAGE

    # First remove the image
    subprocess.call(["docker", "rmi", image])

    # Now try to get the image's Command
    result = uut.get_image_command(image)

    # Should return a non-empty string
    assert result


# -----------------------------------------------------------------------------
# get_images()


def _test_get_images(stdout: str, returncode: int = 0) -> Sequence[str]:
    run_mock = _mock_subprocess_run(
        stdout=stdout,
        returncode=returncode,
    )
    with run_mock:
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


# -----------------------------------------------------------------------------
# get_image_entrypoint()


def test_get_image_entrypoint() -> None:
    """get_image_entrypoint works"""
    result = uut.get_image_entrypoint("scuba/entrypoint-test")
    assert result == ["/entrypoint.sh"]


def test_get_image_entrypoint__none() -> None:
    """get_image_entrypoint works for image with no entrypoint"""
    result = uut.get_image_entrypoint(DOCKER_IMAGE)
    assert result is None


_DOCKER_INSPECT_OUTPUT_NO_ENTRYPOINT_OLD = """
[
    {
        "Id": "sha256:78138d4a1048e7c080a636858484eb7170ba15e93251a4f69fc42e8c4ad288b6",
        "RepoTags": [
            "scuba/hello:latest"
        ],
        "RepoDigests": [],
        "Parent": "",
        "Comment": "buildkit.dockerfile.v0",
        "Created": "2025-06-08T02:01:44.709546887-04:00",
        "DockerVersion": "",
        "Author": "",
        "Config": {
            "ArgsEscaped": true,
            "Hostname": "",
            "Domainname": "",
            "User": "",
            "AttachStdin": false,
            "AttachStdout": false,
            "AttachStderr": false,
            "Tty": false,
            "OpenStdin": false,
            "StdinOnce": false,
            "Env": [
                "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
            ],
            "Cmd": [
                "/hello.sh"
            ],
            "Image": "",
            "Volumes": null,
            "WorkingDir": "/",
            "Entrypoint": null,
            "OnBuild": null,
            "Labels": null
        },
        "Architecture": "amd64",
        "Os": "linux",
        "Size": 8309167,
        "GraphDriver": {
            "Data": {
                "LowerDir": "/var/lib/docker/overlay2/i0vanzaum61dxwhffnfupowvx/diff:/var/lib/docker/overlay2/c8f9936203f4f7f53e95eacc1c1931c5a02f21f734a42d992785b938a00419ec/diff",
                "MergedDir": "/var/lib/docker/overlay2/afv1jwfgnud934iv6kc4fdzsq/merged",
                "UpperDir": "/var/lib/docker/overlay2/afv1jwfgnud934iv6kc4fdzsq/diff",
                "WorkDir": "/var/lib/docker/overlay2/afv1jwfgnud934iv6kc4fdzsq/work"
            },
            "Name": "overlay2"
        },
        "RootFS": {
            "Type": "layers",
            "Layers": [
                "sha256:fd2758d7a50e2b78d275ee7d1c218489f2439084449d895fa17eede6c61ab2c4",
                "sha256:309ded99abb0f87ed73f4f364375a3f9765c1e04494910b07b969c0ebb09fb31",
                "sha256:05b16255096123e00ba39436de05901b62d646a48d8ed514a28d843bb23393b6"
            ]
        },
        "Metadata": {
            "LastTagTime": "2025-06-08T02:01:44.76502078-04:00"
        }
    }
]
"""


def test_get_image_entrypoint_mocked_no_entrypoint_old() -> None:
    run_mock = _mock_subprocess_run(
        stdout=_DOCKER_INSPECT_OUTPUT_NO_ENTRYPOINT_OLD,
    )
    with run_mock:
        result = uut.get_image_entrypoint(DOCKER_IMAGE)
        assert result is None


_DOCKER_INSPECT_OUTPUT_NO_ENTRYPOINT_NEW = """
[
    {
        "Id": "sha256:78138d4a1048e7c080a636858484eb7170ba15e93251a4f69fc42e8c4ad288b6",
        "RepoTags": [
            "scuba/hello:latest"
        ],
        "RepoDigests": [],
        "Parent": "",
        "Comment": "buildkit.dockerfile.v0",
        "Created": "2025-06-08T02:01:44.709546887-04:00",
        "DockerVersion": "",
        "Author": "",
        "Config": {
            "Env": [
                "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
            ],
            "Cmd": [
                "/hello.sh"
            ],
            "WorkingDir": "/",
            "ArgsEscaped": true
        },
        "Architecture": "amd64",
        "Os": "linux",
        "Size": 8309167,
        "GraphDriver": {
            "Data": {
                "LowerDir": "/var/lib/docker/overlay2/i0vanzaum61dxwhffnfupowvx/diff:/var/lib/docker/overlay2/c8f9936203f4f7f53e95eacc1c1931c5a02f21f734a42d992785b938a00419ec/diff",
                "MergedDir": "/var/lib/docker/overlay2/afv1jwfgnud934iv6kc4fdzsq/merged",
                "UpperDir": "/var/lib/docker/overlay2/afv1jwfgnud934iv6kc4fdzsq/diff",
                "WorkDir": "/var/lib/docker/overlay2/afv1jwfgnud934iv6kc4fdzsq/work"
            },
            "Name": "overlay2"
        },
        "RootFS": {
            "Type": "layers",
            "Layers": [
                "sha256:fd2758d7a50e2b78d275ee7d1c218489f2439084449d895fa17eede6c61ab2c4",
                "sha256:309ded99abb0f87ed73f4f364375a3f9765c1e04494910b07b969c0ebb09fb31",
                "sha256:05b16255096123e00ba39436de05901b62d646a48d8ed514a28d843bb23393b6"
            ]
        },
        "Metadata": {
            "LastTagTime": "2025-06-08T02:01:44.76502078-04:00"
        }
    }
]
"""


def test_get_image_entrypoint_mocked_no_entrypoint_new() -> None:
    run_mock = _mock_subprocess_run(
        stdout=_DOCKER_INSPECT_OUTPUT_NO_ENTRYPOINT_NEW,
    )
    with run_mock:
        result = uut.get_image_entrypoint(DOCKER_IMAGE)
        assert result is None


_DOCKER_INSPECT_OUTPUT_ENTRYPOINT = """
[
    {
        "Id": "sha256:d8c0eab119d7bd0c449e62023bb045a4996dc39078da9843b2483605a15a7bb8",
        "RepoTags": [
            "scuba/entrypoint-test:latest"
        ],
        "RepoDigests": [],
        "Parent": "",
        "Comment": "buildkit.dockerfile.v0",
        "Created": "2025-06-08T02:01:43.869621065-04:00",
        "DockerVersion": "",
        "Author": "",
        "Config": {
            "Env": [
                "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
            ],
            "Entrypoint": [
                "/entrypoint.sh"
            ],
            "WorkingDir": "/"
        },
        "Architecture": "amd64",
        "Os": "linux",
        "Size": 8309289,
        "GraphDriver": {
            "Data": {
                "LowerDir": "/var/lib/docker/overlay2/s8yfiyigocp8jmafjlwrnvbjh/diff:/var/lib/docker/overlay2/c8f9936203f4f7f53e95eacc1c1931c5a02f21f734a42d992785b938a00419ec/diff",
                "MergedDir": "/var/lib/docker/overlay2/bko2v72yngijjzs77qw42im5c/merged",
                "UpperDir": "/var/lib/docker/overlay2/bko2v72yngijjzs77qw42im5c/diff",
                "WorkDir": "/var/lib/docker/overlay2/bko2v72yngijjzs77qw42im5c/work"
            },
            "Name": "overlay2"
        },
        "RootFS": {
            "Type": "layers",
            "Layers": [
                "sha256:fd2758d7a50e2b78d275ee7d1c218489f2439084449d895fa17eede6c61ab2c4",
                "sha256:b9d8112de4c9dbe254f0f9264f5bbd2b4af2ede492a0a4795b7cf899257bea60",
                "sha256:89c4ad1aa7abed7e63c84d12cf81771472b64e1a6fbe9169a6c0e22e0f0aceb7"
            ]
        },
        "Metadata": {
            "LastTagTime": "2025-06-08T02:01:43.92217129-04:00"
        }
    }
]
"""


def test_get_image_entrypoint_mocked() -> None:
    run_mock = _mock_subprocess_run(
        stdout=_DOCKER_INSPECT_OUTPUT_ENTRYPOINT,
    )
    with run_mock:
        result = uut.get_image_entrypoint(DOCKER_IMAGE)
        assert result == ["/entrypoint.sh"]


# -----------------------------------------------------------------------------
# make_vol_opt()


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
