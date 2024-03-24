from __future__ import annotations
import subprocess
import json
from typing import Any, Dict, IO, Optional, Sequence, Union
from pathlib import Path

# https://github.com/python/typeshed/blob/main/stdlib/subprocess.pyi
_CMD = Union[str, bytes, Sequence[Union[str, bytes]]]
_FILE = Union[None, int, IO[Any]]


class DockerError(Exception):
    pass


class DockerExecuteError(DockerError):
    def __init__(self) -> None:
        super().__init__("Failed to execute docker. Is it installed?")


class NoSuchImageError(DockerError):
    def __init__(self, image: str):
        self.image = image

    def __str__(self) -> str:
        return f"No such image: {self.image}"


def call(
    args: _CMD,
    stdin: _FILE,
    stdout: _FILE,
    stderr: _FILE,
) -> int:
    try:
        return subprocess.call(args, stdin=stdin, stdout=stdout, stderr=stderr)
    except FileNotFoundError as err:
        raise DockerExecuteError() from err


def _run_docker(*args: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
    """Run docker and raise DockerExecuteError on ENOENT"""
    docker_args = ["docker"] + list(args)
    kw: Dict[str, Any] = dict(text=True)
    if capture:
        kw.update(capture_output=True)

    try:
        return subprocess.run(docker_args, **kw)
    except FileNotFoundError as err:
        raise DockerExecuteError() from err


def docker_inspect(image: str) -> dict:
    """Inspects a docker image

    Returns: Parsed JSON data
    """
    cp = _run_docker("inspect", "--type", "image", image, capture=True)

    if not cp.returncode == 0:
        if "no such image" in cp.stderr.lower():
            raise NoSuchImageError(image)
        raise DockerError(f"Failed to inspect image: {cp.stderr.strip()}")

    result = json.loads(cp.stdout)[0]
    assert isinstance(result, dict)
    return result


def docker_pull(image: str) -> None:
    """Pulls an image"""
    # If this fails, the default docker stdout/stderr looks good to the user.
    cp = _run_docker("pull", image)
    if cp.returncode != 0:
        raise DockerError(f"Failed to pull image: {image}")


def docker_inspect_or_pull(image: str) -> dict:
    """Inspects a docker image, pulling it if it doesn't exist"""
    try:
        return docker_inspect(image)
    except NoSuchImageError:
        # If it doesn't exist yet, try to pull it now (#79)
        docker_pull(image)
        return docker_inspect(image)


def get_images() -> Sequence[str]:
    """Get the current list of docker images

    Returns: List of image names
    """
    cp = _run_docker(
        "images",
        # This format ouputs the same thing as '__docker_images --repo --tag'
        "--format",
        (
            # Always show the bare repository name
            r"{{.Repository}}"
            # And if there is a tag, show that too
            r'{{if ne .Tag "<none>"}}\n{{.Repository}}:{{.Tag}}{{end}}'
        ),
        capture=True,
    )

    if not cp.returncode == 0:
        raise DockerError(f"Failed to retrieve images: {cp.stderr.strip()}")

    return cp.stdout.splitlines()


def _get_image_config(image: str, key: str) -> Optional[Sequence[str]]:
    info = docker_inspect_or_pull(image)
    try:
        result = info["Config"][key]
    except KeyError as ke:
        raise DockerError(f"Failed to inspect image: JSON result missing key {ke}")

    assert isinstance(result, (type(None), list))
    return result


def get_image_command(image: str) -> Optional[Sequence[str]]:
    """Gets the default command for an image"""
    return _get_image_config(image, "Cmd")


def get_image_entrypoint(image: str) -> Optional[Sequence[str]]:
    """Gets the image entrypoint"""
    return _get_image_config(image, "Entrypoint")


def make_vol_opt(
    hostdir_or_volname: Union[Path, str],
    contdir: Path,
    options: Optional[Sequence[str]] = None,
) -> str:
    """Generate a docker volume option"""
    if isinstance(hostdir_or_volname, Path):
        hostdir: Path = hostdir_or_volname
        if not hostdir.is_absolute():
            # NOTE: As of Docker Engine version 23, you can use relative paths
            # on the host. But we have no minimum Docker version, so we don't
            # rely on this.
            raise ValueError(f"hostdir not absolute: {hostdir}")
    if not contdir.is_absolute():
        raise ValueError(f"contdir not absolute: {contdir}")

    vol = f"--volume={hostdir_or_volname}:{contdir}"
    if options:
        assert not isinstance(options, str)
        vol += ":" + ",".join(options)
    return vol
