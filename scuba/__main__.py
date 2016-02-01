#!/usr/bin/env python2

# SCUBA - Simple Container-Utilizing Build Architecture
# (C) 2015 Jonathon Reinhart
# https://github.com/JonathonReinhart/scuba

from __future__ import print_function
import os, os.path
import errno
import sys
import subprocess
import shlex
import argparse
from tempfile import NamedTemporaryFile
import atexit
import pipes
import json

from .constants import *
from .config import find_config, load_config, ConfigError
from .etcfiles import *
from .filecleanup import FileCleanup
from .utils import *
from .version import __version__

def appmsg(fmt, *args):
    print('scuba: ' + fmt.format(*args), file=sys.stderr)

def verbose_msg(fmt, *args):
    if g_verbose:
        appmsg(fmt, *args)



def make_vol_opt(hostdir, contdir, options=None):
    '''Generate a docker volume option'''
    vol = '--volume={0}:{1}'.format(hostdir, contdir)
    if options != None:
        if isinstance(options, str):
            options = (options,)
        vol += ':' + ','.join(options)
    return vol


def get_native_user_opts():
    opts = []

    uid = os.getuid()
    gid = os.getgid()

    opts.append('--user={uid}:{gid}'.format(uid=uid, gid=gid))

    def writeln(f, line):
        f.write(line + '\n')

    # /etc/passwd
    with NamedTemporaryFile(mode='wt', prefix='scuba', delete=False) as f:
        filecleanup.register(f.name)
        opts.append(make_vol_opt(f.name, '/etc/passwd', 'z'))

        writeln(f, passwd_entry(
            username = 'root',
            password = 'x',
            uid = 0,
            gid = 0,
            gecos = 'root',
            homedir = '/root',
            shell = '/bin/sh',
            ))

        writeln(f, passwd_entry(
            username = SCUBA_USER,
            password = 'x',
            uid = uid,
            gid = gid,
            gecos = 'Scuba User',
            homedir = '/',          # Docker sets $HOME=/
            shell = '/bin/sh',
            ))

    # /etc/group
    with NamedTemporaryFile(mode='wt', prefix='scuba', delete=False) as f:
        filecleanup.register(f.name)
        opts.append(make_vol_opt(f.name, '/etc/group', 'z'))

        writeln(f, group_entry(
            groupname = 'root',
            password = 'x',
            gid = 0,
            ))

        writeln(f, group_entry(
            groupname = SCUBA_GROUP,
            password = 'x',
            gid = gid,
            ))

    # /etc/shadow
    with NamedTemporaryFile(mode='wt', prefix='scuba', delete=False) as f:
        filecleanup.register(f.name)
        opts.append(make_vol_opt(f.name, '/etc/shadow', 'z'))

        writeln(f, shadow_entry(
            username = 'root',
            ))
        writeln(f, shadow_entry(
            username = SCUBA_USER,
            ))

    return opts


def get_native_opts(scuba_args):
    opts = []

    if not scuba_args.root:
        opts += get_native_user_opts()

    return opts


def parse_scuba_args(argv):
    ap = argparse.ArgumentParser(description='Simple Container-Utilizing Build Apparatus')
    ap.add_argument('-n', '--dry-run', action='store_true')
    ap.add_argument('-r', '--root', action='store_true')
    ap.add_argument('-v', '--version', action='version', version='scuba ' + __version__)
    ap.add_argument('-V', '--verbose', action='store_true')
    ap.add_argument('command', nargs=argparse.REMAINDER)
    args = ap.parse_args(argv)

    global g_verbose
    g_verbose = args.verbose

    return args


def main(argv=None):
    scuba_args = parse_scuba_args(argv)

    global filecleanup
    filecleanup = FileCleanup()
    if not scuba_args.dry_run:
        atexit.register(filecleanup.cleanup)

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

        docker_opts = get_native_opts(scuba_args)
        docker_cmd = usercmd

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
    ] + docker_opts

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
