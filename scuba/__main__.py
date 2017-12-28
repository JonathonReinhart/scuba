# SCUBA - Simple Container-Utilizing Build Architecture
# (C) 2015 Jonathon Reinhart
# https://github.com/JonathonReinhart/scuba

from __future__ import print_function
import os, os.path
import errno
import sys
import shlex
import itertools
import argparse
import tempfile
import shutil

from .cmdlineargs import *
from .compat import File, StringIO
from .constants import *
from .config import find_config, load_config, ScubaConfig, \
        ConfigError, ConfigNotFoundError
from .utils import *
from .version import __version__
from .dockerutil import get_image_command, get_image_entrypoint, make_vol_opt, \
        DockerError, DockerExecuteError
from . import dockerutil

# This is the path where all scuba-related things will be bind-mounted into the
# container.
SCUBA_DIR = '/.scuba'

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

def writeln(f, line):
    f.write(line + '\n')


def parse_scuba_args(argv):
    ap = argparse.ArgumentParser(description='Simple Container-Utilizing Build Apparatus')
    ap.add_argument('-d', '--docker-arg', dest='docker_args', action='append',
            type=lambda x: shlex.split(x), default=[],
            help="Pass additional arguments to 'docker run'")
    ap.add_argument('--list-aliases', action='store_true',
            help=argparse.SUPPRESS)
    ap.add_argument('--list-available-options', action=ListOptsAction,
            help=argparse.SUPPRESS)
    ap.add_argument('--image', help='Override Docker image')
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


class ScubaError(Exception):
    pass

class ScubaDive(object):
    def __init__(self, user_command, docker_args=[], as_root=False, verbose=False,
            image_override=None):
        self.user_command = user_command
        self.as_root = as_root
        self.verbose = verbose
        self.image_override = image_override

        # These will be added to docker run cmdline
        self.env_vars = {}
        self.volumes = []
        self.options = docker_args
        self.workdir = None

        self.__locate_scubainit()
        self.__load_config()


    def prepare(self):
        '''Prepare to run the docker command'''
        self.__make_scubadir()

        if self.is_remote_docker:
            '''
            Docker is running remotely (e.g. boot2docker on OSX).
            We don't need to do any user setup whatsoever.

            TODO: For now, remote instances won't have any .scubainit

            See:
            https://github.com/JonathonReinhart/scuba/issues/17
            '''
            raise ScubaError('Remote docker not supported (DOCKER_HOST is set)')

        # Docker is running natively
        self.__setup_native_run()

    def __str__(self):
        s = StringIO()
        writeln(s, 'ScubaDive')
        writeln(s, '   verbose:      {0}'.format(self.verbose))
        writeln(s, '   as_root:      {0}'.format(self.as_root))
        writeln(s, '   workdir:      {0}'.format(self.workdir))

        writeln(s, '   options:')
        for a in self.options:
            writeln(s, '      ' + a)

        writeln(s, '   env_vars:')
        for k,v in self.env_vars.items():
            writeln(s, '      {0}={1}'.format(k, v))

        writeln(s, '   volumes:')
        for hostpath, contpath, options in self.__get_vol_opts():
            writeln(s, '      {0} => {1} {2}'.format(hostpath, contpath, options))

        writeln(s, '   user_command: {0}'.format(self.user_command))
        writeln(s, '   context:')
        writeln(s, '     script: ' + str(self.context.script)) 
        writeln(s, '     image:  ' + str(self.context.image)) 

        return s.getvalue()


    def cleanup_tempfiles(self):
        shutil.rmtree(self.__scubadir_hostpath)


    @property
    def is_remote_docker(self):
        return 'DOCKER_HOST' in os.environ

    def add_env(self, name, val):
        '''Add an environment variable to the docker run invocation
        '''
        if name in self.env_vars:
            raise KeyError(name)
        self.env_vars[name] = val

    def add_volume(self, hostpath, contpath, options=None):
        '''Add a volume (bind-mount) to the docker run invocation
        '''
        if options is None:
            options = []
        self.volumes.append((hostpath, contpath, options))

    def add_option(self, option):
        '''Add another option to the docker run invocation
        '''
        self.options.append(option)

    def set_workdir(self, workdir):
        self.workdir = workdir

    def __locate_scubainit(self):
        '''Determine path to scubainit binary
        '''
        pkg_path = os.path.dirname(__file__)

        self.scubainit_path = os.path.join(pkg_path, 'scubainit')
        if not os.path.isfile(self.scubainit_path):
            raise ScubaError('scubainit not found at "{0}"'.format(self.scubainit_path))


    def __load_config(self):
        '''Find and load .scuba.yml
        '''

        # top_path is where .scuba.yml is found, and becomes the top of our bind mount.
        # top_rel is the relative path from top_path to the current working directory,
        # and is where we'll set the working directory in the container (relative to
        # the bind mount point).
        try:
            top_path, top_rel = find_config()
            self.config = load_config(os.path.join(top_path, SCUBA_YML))
        except ConfigNotFoundError as cfgerr:
            # SCUBA_YML can be missing if --image was given.
            # In this case, we assume a default config
            if not self.image_override:
                raise ScubaError(str(cfgerr))
            top_path, top_rel = os.getcwd(), ''
            self.config = ScubaConfig(image=None)
        except ConfigError as cfgerr:
            raise ScubaError(str(cfgerr))

        # Mount scuba root directory at the same path in the container...
        self.add_volume(top_path, top_path)

        # ...and set the working dir relative to it
        self.set_workdir(os.path.join(top_path, top_rel))

    def __make_scubadir(self):
        '''Make temp directory where all ancillary files are bind-mounted
        '''
        self.__scubadir_hostpath = tempfile.mkdtemp(prefix='scubadir')
        self.__scubadir_contpath = '/.scuba'
        self.add_volume(self.__scubadir_hostpath, self.__scubadir_contpath)

    def __setup_native_run(self):
        # These options are appended to mounted volume arguments
        # NOTE: This tells Docker to re-label the directory for compatibility
        # with SELinux. See `man docker-run` for more information.
        self.vol_opts = ['z']


        # Pass variables to scubainit
        self.add_env('SCUBAINIT_UMASK', '{0:04o}'.format(get_umask()))

        if not self.as_root:
            self.add_env('SCUBAINIT_UID', os.getuid())
            self.add_env('SCUBAINIT_GID', os.getgid())

        if self.verbose:
            self.add_env('SCUBAINIT_VERBOSE', 1)


        # Mount scubainit in the container
        self.add_volume(self.scubainit_path, '/scubainit', ['ro'])

        # Hooks
        for name in ('root', 'user', ):
            self.__generate_hook_script(name)

        # allocate TTY if scuba's output is going to a terminal
        # and stdin is not redirected
        if sys.stdout.isatty() and sys.stdin.isatty():
            self.add_option('--tty')

        # Process any aliases
        try:
            context = self.config.process_command(self.user_command)
        except ConfigError as cfgerr:
            raise ScubaError(str(cfgerr))

        if self.image_override:
            context.image = self.image_override

        '''
        Normally, if the user provides no command to "docker run", the image's
        default CMD is run. Because we set the entrypiont, scuba must emulate the
        default behavior itself.
        '''
        if not context.script:
            # No user-provided command; we want to run the image's default command
            verbose_msg('No user command; getting command from image')
            default_cmd = get_image_command(context.image)
            if not default_cmd:
                raise ScubaError('No command given and no image-specified command')
            verbose_msg('{0} Cmd: "{1}"'.format(context.image, default_cmd))
            context.script = [shell_quote_cmd(default_cmd)]

        # Make scubainit the entrypoint, and manually insert an existing
        # entrypoint before each user command
        entrypoint = get_image_entrypoint(context.image) or []
        self.add_option('--entrypoint=/scubainit')

        # The user command is executed via a generated shell script
        with self.open_scubadir_file('command.sh', 'wt') as f:
            self.docker_cmd = ['/bin/sh', f.container_path]
            writeln(f, '#!/bin/sh')
            writeln(f, '# Auto-generated from scuba')
            writeln(f, 'set -e')
            for cmd in context.script:
                if entrypoint:
                    cmd = shell_quote_cmd(entrypoint) + ' ' + cmd
                writeln(f, cmd)

        self.context = context



    def open_scubadir_file(self, name, mode):
        '''Opens a file in the 'scubadir'

        This file will automatically be bind-mounted into the container,
        at a path given by the 'container_path' property on the returned file object.
        '''
        path = os.path.join(self.__scubadir_hostpath, name)
        assert not os.path.exists(path)

        # Make any directories required
        mkdir_p(os.path.dirname(path))

        f = File(path, mode)
        f.container_path = os.path.join(self.__scubadir_contpath, name)
        return f


    def __generate_hook_script(self, name):
        script = self.config.hooks.get(name)
        if not script:
            return

        # Generate the hook script, mount it into the container, and tell scubainit
        with self.open_scubadir_file('hooks/{0}.sh'.format(name), 'wt') as f:

            self.add_env('SCUBAINIT_HOOK_{0}'.format(name.upper()), f.container_path)

            writeln(f, '#!/bin/sh')
            writeln(f, '# Auto-generated from .scuba.yml')
            writeln(f, 'set -e')
            for cmd in script:
                writeln(f, cmd)

    def __get_vol_opts(self):
        for hostpath, contpath, options in self.volumes:
            yield hostpath, contpath, options + self.vol_opts

    def get_docker_cmdline(self):
        args = ['docker', 'run',
            # interactive: keep STDIN open
            '-i',

            # remove container after exit
            '--rm',
        ]

        for name,val in self.env_vars.items():
            args.append('--env={0}={1}'.format(name, val))

        for hostpath, contpath, options in self.__get_vol_opts():
            args.append(make_vol_opt(hostpath, contpath, options))

        if self.workdir:
            args += ['-w', self.workdir]

        args += self.options

        # Docker image
        args.append(self.context.image)

        # Command to run in container
        args += self.docker_cmd

        return args


def run_scuba(scuba_args):
    dive = ScubaDive(
        scuba_args.command,
        docker_args = scuba_args.docker_args,
        as_root = scuba_args.root,
        verbose = scuba_args.verbose,
        image_override = scuba_args.image,
        )

    if scuba_args.list_aliases:
        print('ALIAS\tIMAGE')
        for name in sorted(dive.config.aliases):
            alias = dive.config.aliases[name]
            print('{0}\t{1}'.format(alias.name, alias.image or dive.config.image))
        return

    try:
        dive.prepare()
        run_args = dive.get_docker_cmdline()

        if g_verbose or scuba_args.dry_run:
            print(str(dive))
            print()

            appmsg('Docker command line:')
            print('$ ' + format_cmdline(run_args))

        if scuba_args.dry_run:
            sys.exit(42)

        # Explicitly pass sys.stdin/stdout/stderr so they apply to the
        # child process if overridden (by tests).
        return dockerutil.call(
                args = run_args,
                stdin = sys.stdin,
                stdout = sys.stdout,
                stderr = sys.stderr,
                )

    finally:
        if scuba_args.dry_run:
            appmsg("Temp files not cleaned up")
        else:
            dive.cleanup_tempfiles()


def main(argv=None):
    scuba_args = parse_scuba_args(argv)

    try:
        rc = run_scuba(scuba_args) or 0
        sys.exit(rc)
    except DockerExecuteError as e:
        appmsg(str(e))
        sys.exit(2)
    except (ScubaError, DockerError) as e:
        appmsg(str(e))
        sys.exit(128)

if __name__ == '__main__':
    main()
