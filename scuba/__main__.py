# SCUBA - Simple Container-Utilizing Build Architecture
# (C) 2015 Jonathon Reinhart
# https://github.com/JonathonReinhart/scuba

from __future__ import print_function
import os, os.path
import errno
import sys
import subprocess
import shlex
import itertools
import argparse
from tempfile import NamedTemporaryFile
import atexit

from .constants import *
from .config import find_config, load_config, ConfigError
from .filecleanup import FileCleanup
from .utils import *
from .version import __version__
from .dockerutil import *

def appmsg(fmt, *args):
    print('scuba: ' + fmt.format(*args), file=sys.stderr)

def verbose_msg(fmt, *args):
    if g_verbose:
        appmsg(fmt, *args)

def get_umask():
    # Same logic as bash/builtins/umask.def
    val = os.umask(0o22)
    os.umask(val)
    return val

def generate_hook_script(config, opts, name):
    script = config.hooks.get(name)
    if not script:
        return

    def writeln(f, line):
        f.write(line + '\n')

    # Generate the hook script, mount it into the container, and tell scubainit
    with NamedTemporaryFile(mode='wt', prefix='scuba', delete=False) as f:
        filecleanup.register(f.name)

        cpath = '/.scuba/hooks/{0}.sh'.format(name)
        opts.append(make_vol_opt(f.name, cpath))
        opts.append('--env=SCUBAINIT_HOOK_{0}={1}'.format(name.upper(), cpath))

        writeln(f, '#!/bin/sh')
        writeln(f, '# Auto-generated from .scuba.yml')
        writeln(f, 'set -e')
        for cmd in script:
            writeln(f, cmd)


def get_native_opts(config, scuba_args, usercmd):
    opts = [
        '--env=SCUBAINIT_UMASK={0:04o}'.format(get_umask()),
    ]

    if not scuba_args.root:
        opts += [
            '--env=SCUBAINIT_UID={0}'.format(os.getuid()),
            '--env=SCUBAINIT_GID={0}'.format(os.getgid()),
        ]

    if g_verbose:
        opts.append('--env=SCUBAINIT_VERBOSE=1')

    # Mount scubainit in the container
    opts.append(make_vol_opt(g_scubainit_path, '/scubainit', ['ro','z']))

    # Make scubainit the entrypoint
    # TODO: What if the image already defines an entrypoint?
    opts.append('--entrypoint=/scubainit')


    '''
    Normally, if the user provides no command to "docker run", the image's
    default CMD is run. Because we set the entrypiont, scuba must emulate the
    default behavior itself.
    '''
    if len(usercmd) == 0:
        # No user-provided command; we want to run the image's default command
        verbose_msg('No user command; getting command from image')
        try:
            usercmd = get_image_command(config.image)
        except DockerError as e:
            appmsg(str(e))
            sys.exit(128)
        verbose_msg('{0} Cmd: "{1}"'.format(config.image, usercmd))

    # Hooks
    for name in ('root', 'user', ):
        generate_hook_script(config, opts, name)

    return opts, usercmd


def parse_scuba_args(argv):
    ap = argparse.ArgumentParser(description='Simple Container-Utilizing Build Apparatus')
    ap.add_argument('-d', '--docker-arg', dest='docker_args', action='append',
            type=lambda x: shlex.split(x), default=[],
            help="Pass additional arguments to 'docker run'")
    ap.add_argument('-n', '--dry-run', action='store_true',
            help="Don't actually invoke docker; just print the docker cmdline")
    ap.add_argument('-r', '--root', action='store_true',
            help="Run container as root (don't create scubauser)")
    ap.add_argument('-v', '--version', action='version', version='scuba ' + __version__)
    ap.add_argument('-V', '--verbose', action='store_true',
            help="Be verbose")
    ap.add_argument('command', nargs=argparse.REMAINDER,
            help="Command (and arguments) to run in the container")

    args = ap.parse_args(argv)

    # Flatten docker arguments into single list
    args.docker_args = list(itertools.chain.from_iterable(args.docker_args))

    global g_verbose
    g_verbose = args.verbose

    return args


def main(argv=None):
    scuba_args = parse_scuba_args(argv)

    global filecleanup
    filecleanup = FileCleanup()
    if not scuba_args.dry_run:
        atexit.register(filecleanup.cleanup)

    pkg_path = os.path.dirname(__file__)

    # Determine path to scubainit binary
    global g_scubainit_path
    g_scubainit_path = os.path.join(pkg_path, 'scubainit')
    if not os.path.isfile(g_scubainit_path):
        appmsg('scubainit not found at "{0}"'.format(g_scubainit_path))
        sys.exit(128)


    # top_path is where .scuba.yml is found, and becomes the top of our bind mount.
    # top_rel is the relative path from top_path to the current working directory,
    # and is where we'll set the working directory in the container (relative to
    # the bind mount point).
    try:
        top_path, top_rel = find_config()
        config = load_config(os.path.join(top_path, SCUBA_YML))
    except ConfigError as cfgerr:
        appmsg(str(cfgerr))
        sys.exit(128)

    # Process any aliases
    usercmd = config.process_command(scuba_args.command)

    # Determine if Docker is running locally or remotely
    if 'DOCKER_HOST' in os.environ:
        '''
        Docker is running remotely (e.g. boot2docker on OSX).
        We don't need to do any user setup whatsoever.

        TODO: For now, remote instances won't have any .scubainit

        See:
        https://github.com/JonathonReinhart/scuba/issues/17
        '''
        verbose_msg('DOCKER_HOST in environment, Docker running remotely')
        docker_opts = []
        docker_cmd = usercmd
        vol_opts = None

    else:
        '''
        Docker is running natively (e.g. on Linux).

        We want files created inside the container (in scubaroot) to appear to the
        host as if they were created there (owned by the same uid/gid, with same
        umask, etc.)
        '''
        verbose_msg('Docker running natively')

        docker_opts, docker_cmd = get_native_opts(config, scuba_args, usercmd)

        # NOTE: This tells Docker to re-label the directory for compatibility
        # with SELinux. See `man docker-run` for more information.
        vol_opts = ['z']


    # Build the docker command line
    run_args = ['docker', 'run',
        # interactive: keep STDIN open
        '-i',

        # remove container after exit
        '--rm',

        # Mount scuba root directory...
        make_vol_opt(top_path, SCUBA_ROOT, vol_opts),

        # ...and set the working dir relative to it
        '-w', os.path.join(SCUBA_ROOT, top_rel),
    ] + docker_opts + scuba_args.docker_args

    # allocate TTY if scuba's output is going to a terminal
    if sys.stdout.isatty():
        run_args.append('--tty')

    # Docker image
    run_args.append(config.image)

    # Command to run in container
    run_args += docker_cmd

    if g_verbose or scuba_args.dry_run:
        appmsg('Docker command line:')
        print('$ ' + format_cmdline(run_args))

    if scuba_args.dry_run:
        appmsg('Exiting for dry run. Temporary files not removed:')
        for f in filecleanup.files:
            print('   ' + f, file=sys.stderr)
        sys.exit(42)

    try:
        # Explicitly pass sys.stdout/stderr so they apply to the
        # child process if overridden (by tests).
        rc = subprocess.call(
                args = run_args,
                stdout = sys.stdout,
                stderr = sys.stderr,
                )
    except OSError as e:
        if e.errno == errno.ENOENT:
            appmsg('Failed to execute docker. Is it installed?')
            sys.exit(2)

    sys.exit(rc)

if __name__ == '__main__':
    main()
