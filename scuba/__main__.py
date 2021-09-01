# SCUBA - Simple Container-Utilizing Build Architecture
# (C) 2015 Jonathon Reinhart
# https://github.com/JonathonReinhart/scuba
# PYTHON_ARGCOMPLETE_OK

import os
import sys
import shlex
import itertools
import argparse
try:
    import argcomplete
except ImportError:
    class argcomplete:
        @staticmethod
        def autocomplete(*_, **__):
            pass

from . import dockerutil
from .config import find_config, ScubaConfig, ConfigError, ConfigNotFoundError
from .dockerutil import DockerError, DockerExecuteError
from .scuba import ScubaDive, ScubaError
from .utils import format_cmdline, parse_env_var
from .version import __version__


def appmsg(fmt, *args):
    print('scuba: ' + fmt.format(*args), file=sys.stderr)


def parse_scuba_args(argv):

    def _list_images_completer(**_):
        return dockerutil.get_images()

    def _list_aliases_completer(parsed_args, **_):
        # We don't want to try to complete any aliases if one was already given
        if parsed_args.command:
            return []

        try:
            _, _, config = find_config()
            return sorted(config.aliases)
        except (ConfigNotFoundError, ConfigError):
            argcomplete.warn('No or invalid config found.  Cannot auto-complete aliases.')
            return []

    ap = argparse.ArgumentParser(description='Simple Container-Utilizing Build Apparatus')
    ap.add_argument('-d', '--docker-arg', dest='docker_args', action='append',
            type=lambda x: shlex.split(x), default=[],
            help="Pass additional arguments to 'docker run'")
    ap.add_argument('-e', '--env', dest='env_vars', action='append',
            type=parse_env_var, default=[],
            help='Environment variables to pass to docker')
    ap.add_argument('--entrypoint',
            help='Override the default ENTRYPOINT of the image')
    ap.add_argument('--image', help='Override Docker image').completer = _list_images_completer
    ap.add_argument('--shell', help='Override shell used in Docker container')
    ap.add_argument('-n', '--dry-run', action='store_true',
            help="Don't actually invoke docker; just print the docker cmdline")
    ap.add_argument('-r', '--root', action='store_true',
            help="Run container as root (don't create scubauser)")
    ap.add_argument('-v', '--version', action='version', version='scuba ' + __version__)
    ap.add_argument('-V', '--verbose', action='store_true',
            help="Be verbose")
    ap.add_argument('command', nargs=argparse.REMAINDER,
            help="Command (and arguments) to run in the container").completer = _list_aliases_completer

    argcomplete.autocomplete(ap, always_complete_options=False)
    args = ap.parse_args(argv)

    # Flatten docker arguments into single list
    args.docker_args = list(itertools.chain.from_iterable(args.docker_args))

    # Convert env var tuples into a dict, forbidding duplicates
    env = dict()
    for k,v in args.env_vars:
        if k in env:
            ap.error("Duplicate env var {}".format(k))
        env[k] = v
    args.env_vars = env

    global g_verbose
    g_verbose = args.verbose

    return args


def run_scuba(scuba_args):
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
        top_path, top_rel, config = os.getcwd(), '', ScubaConfig()

    # Set up scuba Docker invocation
    dive = ScubaDive(
        user_command = scuba_args.command,
        config = config,
        top_path = top_path,
        top_rel = top_rel,
        docker_args = scuba_args.docker_args,
        env = scuba_args.env_vars,
        as_root = scuba_args.root,
        verbose = scuba_args.verbose,
        image_override = scuba_args.image,
        entrypoint = scuba_args.entrypoint,
        shell_override = scuba_args.shell,
        keep_tempfiles = scuba_args.dry_run,
        )

    with dive:
        run_args = dive.get_docker_cmdline()

        if g_verbose or scuba_args.dry_run:
            print(str(dive))
            print()

            appmsg('Docker command line:')
            print('$ ' + format_cmdline(run_args))

        if scuba_args.dry_run:
            appmsg("Temp files not cleaned up")
            return 0

        # Explicitly pass sys.stdin/stdout/stderr so they apply to the
        # child process if overridden (by tests).
        return dockerutil.call(
                args = run_args,
                stdin = sys.stdin,
                stdout = sys.stdout,
                stderr = sys.stderr,
                )


def main(argv=None):
    scuba_args = parse_scuba_args(argv)

    try:
        rc = run_scuba(scuba_args) or 0
        sys.exit(rc)
    except ConfigError as e:
        appmsg("Config error: " + str(e))
        sys.exit(128)
    except DockerExecuteError as e:
        appmsg(str(e))
        sys.exit(2)
    except (ScubaError, DockerError) as e:
        appmsg(str(e))
        sys.exit(128)

if __name__ == '__main__':
    main()
