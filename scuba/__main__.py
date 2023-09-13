# SCUBA - Simple Container-Utilizing Build Architecture
# (C) 2015 Jonathon Reinhart
# https://github.com/JonathonReinhart/scuba
# PYTHON_ARGCOMPLETE_OK

import os
import sys
import shlex
import itertools
import argparse
from pathlib import Path
from typing import Any, Optional, Sequence

try:
    import argcomplete  # type: ignore
except ImportError:
    from . import argcomplete_stub as argcomplete  # type: ignore[no-redef]

from . import dockerutil
from .config import find_config, ScubaConfig, ConfigError, ConfigNotFoundError
from .dockerutil import DockerError, DockerExecuteError
from .scuba import ScubaDive, ScubaError
from .utils import format_cmdline, parse_env_var
from .version import __version__

g_verbose: bool = False


def appmsg(msg: str) -> None:
    print("scuba: " + msg, file=sys.stderr)


def parse_scuba_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    def _list_images_completer(**kwargs: Any) -> Sequence[str]:
        return dockerutil.get_images()

    def _list_aliases_completer(
        parsed_args: argparse.Namespace, **kwargs: Any
    ) -> Sequence[str]:
        # We don't want to try to complete any aliases if one was already given
        if parsed_args.command:
            return []

        try:
            _, _, config = find_config()
            return sorted(config.aliases)
        except (ConfigNotFoundError, ConfigError):
            print(
                "\nNo or invalid config found. Cannot auto-complete aliases.",
                file=sys.stderr,
            )
            return []

    ap = argparse.ArgumentParser(
        description="Simple Container-Utilizing Build Apparatus"
    )
    ap.add_argument(
        "-d",
        "--docker-arg",
        dest="docker_args",
        action="append",
        type=lambda x: shlex.split(x),
        default=[],
        help="Pass additional arguments to 'docker run'",
    )
    ap.add_argument(
        "-e",
        "--env",
        dest="env_vars",
        action="append",
        type=parse_env_var,
        default=[],
        help="Environment variables to pass to docker",
    )
    ap.add_argument("--entrypoint", help="Override the default ENTRYPOINT of the image")

    img_arg = ap.add_argument("--image", help="Override Docker image")
    img_arg.completer = _list_images_completer  # type: ignore[attr-defined]

    ap.add_argument("--shell", help="Override shell used in Docker container")
    ap.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Don't actually invoke docker; just print the docker cmdline",
    )
    ap.add_argument(
        "-r",
        "--root",
        action="store_true",
        help="Run container as root (don't create scubauser)",
    )
    ap.add_argument("-v", "--version", action="version", version="scuba " + __version__)
    ap.add_argument("-V", "--verbose", action="store_true", help="Be verbose")

    cmd_arg = ap.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command (and arguments) to run in the container",
    )
    cmd_arg.completer = _list_aliases_completer  # type: ignore[attr-defined]

    argcomplete.autocomplete(ap, always_complete_options=False)
    args = ap.parse_args(argv)

    # Flatten docker arguments into single list
    args.docker_args = list(itertools.chain.from_iterable(args.docker_args))

    # Convert env var tuples into a dict, forbidding duplicates
    env = dict()
    for k, v in args.env_vars:
        if k in env:
            ap.error(f"Duplicate env var {k!r}")
        env[k] = v
    args.env_vars = env

    global g_verbose
    g_verbose = args.verbose

    return args


def run_scuba(scuba_args: argparse.Namespace) -> int:
    # Locate .scuba.yml
    try:
        # top_path is where .scuba.yml is found, and becomes the top of our bind mount.
        # top_rel is the relative path from top_path to the current working directory,
        # and is where we'll set the working directory in the container (relative to
        # the bind mount point).
        top_path, top_rel, config = find_config()
    except ConfigNotFoundError:
        # .scuba.yml is allowed to be missing if --image was given.
        if not scuba_args.image:
            raise
        top_path, top_rel, config = Path.cwd(), Path(), ScubaConfig()

    # Set up scuba Docker invocation
    dive = ScubaDive(
        user_command=scuba_args.command,
        config=config,
        top_path=top_path,
        top_rel=top_rel,
        docker_args=scuba_args.docker_args,
        env=scuba_args.env_vars,
        as_root=scuba_args.root,
        verbose=scuba_args.verbose,
        image_override=scuba_args.image,
        entrypoint=scuba_args.entrypoint,
        shell_override=scuba_args.shell,
        keep_tempfiles=scuba_args.dry_run,
    )

    with dive:
        run_args = dive.get_docker_cmdline()

        if g_verbose or scuba_args.dry_run:
            appmsg(str(dive) + "\n")
            appmsg("Docker command line:\n$ " + format_cmdline(run_args))

        if scuba_args.dry_run:
            appmsg("Temp files not cleaned up")
            return 0

        # Create volume host paths as current user
        dive.try_create_volumes()

        # Explicitly pass sys.stdin/stdout/stderr so they apply to the
        # child process if overridden (by tests).
        #
        # TODO: This doesn't seem to work in all cases with pytest:
        # _pytest.capture.DontReadFromInput doesn't have fileno()
        return dockerutil.call(
            args=run_args,
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )


def main(argv: Optional[Sequence[str]] = None) -> None:
    scuba_args = parse_scuba_args(argv)

    try:
        rc = run_scuba(scuba_args) or 0
        sys.exit(rc)
    except ConfigError as e:
        appmsg(f"Config error: {e}")
        sys.exit(128)
    except DockerExecuteError as e:
        appmsg(f"{e}")
        sys.exit(2)
    except (ScubaError, DockerError) as e:
        appmsg(str(e))
        sys.exit(128)


if __name__ == "__main__":
    main()
