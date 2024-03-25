import dataclasses
from os.path import abspath, dirname, exists, join, normpath
import subprocess
import sys

# This logic has been adapted from that of PyInstaller
# https://github.com/pyinstaller/pyinstaller/

PACKAGEPATH = abspath(dirname(__file__))
PROJPATH = dirname(PACKAGEPATH)

DIST_SPEC = "scuba"

# Base version, which will be augmented with Git information
BASE_VERSION = "2.13.0"

# This string will be replaced by `git-archive`
# with the abbreviated commit hash
git_archive_rev = "$Format:%h$"


@dataclasses.dataclass(frozen=True)
class GitDescribe:
    tag: str
    commits: int
    rev: str


def git_describe() -> GitDescribe:
    # Get the version from the local Git repository
    subprocess.run(["git", "update-index", "-q", "--refresh"], check=True, cwd=PROJPATH)

    result = subprocess.run(
        ["git", "describe", "--long", "--dirty", "--tag"],
        check=True,
        cwd=PROJPATH,
        stdout=subprocess.PIPE,
        encoding="utf-8",
    )
    parts = result.stdout.rstrip().split("-", 2)
    return GitDescribe(
        tag=parts[0].lstrip("v"),
        commits=int(parts[1]),
        rev=parts[2],
    )


def get_version() -> str:
    # Git repo
    # If a local git repository is present, use `git describe` to provide a rich version
    gitdir = normpath(join(PROJPATH, ".git"))
    if exists(gitdir):
        desc = git_describe()

        # Ensure the base version matches the Git tag
        if desc.tag != BASE_VERSION:
            raise Exception("Git revision different from base version")

        # No local version if we're on a tag
        if desc.commits == 0 and not desc.rev.endswith("dirty"):
            return BASE_VERSION

        return f"{BASE_VERSION}+{desc.commits}-{desc.rev}"

    # Git archive
    # If this was produced via `git archive`, we'll use the version it provides
    if not git_archive_rev.startswith("$"):
        return f"{BASE_VERSION}+g{git_archive_rev}"

    # Otherwise, we're either installed (e.g. via pip), or running from
    # an 'sdist' source distribution, and have a local PKG_INFO file.

    # TODO(#242): Remove backport when Python 3.7 support is removed.
    if sys.version_info >= (3, 8):
        import importlib.metadata as importlib_metadata
    else:
        import importlib_metadata  # backport

    # Can raise importlib.metadata.PackageNotFoundError
    return importlib_metadata.version(DIST_SPEC)


__version__ = get_version()

if __name__ == "__main__":
    print(__version__)
