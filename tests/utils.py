from __future__ import annotations
import os
import sys
from os.path import normpath
import tempfile
import shutil
import unittest
import logging
from pathlib import Path
from typing import Any, Callable, Sequence, TypeVar, Optional, Union
from unittest import mock

from scuba.config import ScubaVolume

PathStr = Union[Path, str]

_FT = TypeVar("_FT", bound=Callable[..., Any])


def assert_seq_equal(a: Sequence, b: Sequence) -> None:
    assert list(a) == list(b)


def assert_paths_equal(a: PathStr, b: PathStr) -> None:
    # NOTE: normpath() can behave undesirably in the face of symlinks, so this
    # comparison is probably not perfect. But since we're often dealing with
    # "pure" paths (that don't actually exist on the filesystem), there's not
    # much more we can do.
    #
    # "This string manipulation may change the meaning of a path that contains
    # symbolic links."
    #
    # https://docs.python.org/3/library/os.path.html#os.path.normpath
    assert normpath(a) == normpath(b)


def assert_str_equalish(exp: Any, act: Any) -> None:
    exp = str(exp).strip()
    act = str(act).strip()
    assert exp == act


def assert_vol(
    vols: dict[Path, ScubaVolume],
    cpath_str: PathStr,
    hpath_str: PathStr,
    options: list[str] = [],
) -> None:
    cpath = Path(cpath_str)
    hpath = Path(hpath_str)
    v = vols[cpath]
    assert isinstance(v, ScubaVolume)
    assert_paths_equal(v.container_path, cpath)
    assert v.volume_name is None
    assert v.host_path is not None
    assert_paths_equal(v.host_path, hpath)
    assert v.options == options


def make_executable(path: PathStr) -> None:
    mode = os.stat(path).st_mode
    mode |= (mode & 0o444) >> 2  # copy R bits to X
    os.chmod(path, mode)


# http://stackoverflow.com/a/8389373/119527
class PseudoTTY:
    def __init__(self, underlying: object):
        self.__underlying = underlying

    def __getattr__(self, name: str) -> Any:
        return getattr(self.__underlying, name)

    def isatty(self) -> bool:
        return True


def skipUnlessTty() -> Callable[[_FT], _FT]:
    return unittest.skipUnless(
        sys.stdin.isatty(), "Can't test docker tty if not connected to a terminal"
    )


class InTempDir:
    def __init__(
        self,
        suffix: str = "",
        prefix: str = "tmp",
        dir: Optional[PathStr] = None,
        delete: bool = True,
    ):
        self.delete = delete
        self.temp_path = tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir)

    def __enter__(self) -> InTempDir:
        self.orig_path = os.getcwd()
        os.chdir(self.temp_path)
        return self

    def __exit__(self, *exc_info: Any) -> None:
        # Restore the working dir and cleanup the temp one
        os.chdir(self.orig_path)
        if self.delete:
            shutil.rmtree(self.temp_path)
