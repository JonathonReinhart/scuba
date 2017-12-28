from __future__ import print_function

from nose.tools import *
from .utils import *
from unittest import TestCase
try:
    from unittest import mock
except ImportError:
    import mock

import logging
import os
import sys
from tempfile import TemporaryFile, NamedTemporaryFile
import subprocess

import scuba.__main__ as main
import scuba.constants
import scuba.dockerutil
import scuba

DOCKER_IMAGE = 'debian:8.2'

class TestMain(TmpDirTestCase):

    def run_scuba(self, args, exp_retval=0, mock_isatty=False, stdin=None):
        '''Run scuba, checking its return value

        Returns scuba/docker stdout data.
        '''

        # Capture both scuba and docker's stdout/stderr,
        # just as the user would see it.
        # Also mock atexit.register(), so we can simulate file cleanup.

        atexit_funcs = []
        def atexit_reg(cb, *args, **kw):
            atexit_funcs.append((cb, args, kw))

        with TemporaryFile(prefix='scubatest-stdout', mode='w+t') as stdout:
            with TemporaryFile(prefix='scubatest-stderr', mode='w+t') as stderr:
                with mock.patch('atexit.register', side_effect=atexit_reg) as atexit_reg_mock:

                    if mock_isatty:
                        stdout = PseudoTTY(stdout)
                        stderr = PseudoTTY(stderr)

                    old_stdin  = sys.stdin
                    old_stdout = sys.stdout
                    old_stderr = sys.stderr

                    if stdin is not None:
                        sys.stdin = stdin
                    sys.stdout = stdout
                    sys.stderr = stderr

                    try:
                        '''
                        Call scuba's main(), and expect it to either exit()
                        with a given return code, or return (implying an exit
                        status of 0).
                        '''
                        try:
                            main.main(argv = args)
                        except SystemExit as sysexit:
                            retcode = sysexit.code
                        else:
                            retcode = 0

                        stdout.seek(0)
                        stderr.seek(0)

                        stdout_data = stdout.read()
                        stderr_data = stderr.read()

                        logging.info('scuba stdout:\n' + stdout_data)
                        logging.info('scuba stderr:\n' + stderr_data)

                        # Verify the return value was as expected
                        assert_equal(exp_retval, retcode)

                        return stdout_data, stderr_data

                    finally:
                        sys.stdin  = old_stdin
                        sys.stdout = old_stdout
                        sys.stderr = old_stderr
                        for f, args, kw in atexit_funcs:
                            f(*args, **kw)


    def test_basic(self):
        '''Verify basic scuba functionality'''

        with open('.scuba.yml', 'w') as f:
            f.write('image: {0}\n'.format(DOCKER_IMAGE))

        args = ['/bin/echo', '-n', 'my output']
        out, _ = self.run_scuba(args)

        assert_str_equalish('my output', out)

    def test_no_cmd(self):
        '''Verify scuba works with no given command'''

        with open('.scuba.yml', 'w') as f:
            f.write('image: {0}\n'.format('jreinhart/hello'))

        out, _ = self.run_scuba([])
        self.assertTrue('Hello from alpine-hello' in out)

    def test_no_image_cmd(self):
        '''Verify scuba gracefully handles an image with no Cmd and no user command'''

        with open('.scuba.yml', 'w') as f:
            f.write('image: {0}\n'.format('jreinhart/scratch'))

        # ScubaError -> exit(128)
        out, _ = self.run_scuba([], 128)

    def test_handle_get_image_command_error(self):
        '''Verify scuba handles a get_image_command error'''

        with open('.scuba.yml', 'w') as f:
            f.write('image: {0}\n'.format(DOCKER_IMAGE))

        def mocked_gic(*args, **kw):
            raise scuba.dockerutil.DockerError('mock error')

        # http://alexmarandon.com/articles/python_mock_gotchas/#patching-in-the-wrong-place
        # http://www.voidspace.org.uk/python/mock/patch.html#where-to-patch
        with mock.patch('scuba.__main__.get_image_command', side_effect=mocked_gic):
            # DockerError -> exit(128)
            self.run_scuba([], 128)


    def test_config_error(self):
        '''Verify config errors are handled gracefully'''

        with open('.scuba.yml', 'w') as f:
            f.write('invalid_key: is no good\n')

        # ConfigError -> exit(128)
        self.run_scuba([], 128)

    def test_multiline_alias_no_args_error(self):
        '''Verify config errors from passing arguments to multi-line alias are caught'''
        with open('.scuba.yml', 'w') as f:
            f.write('''
                image: {image}
                aliases:
                  multi:
                    script:
                      - echo multi
                      - echo line
                      - echo alias
                '''.format(image=DOCKER_IMAGE))

        # ConfigError -> exit(128)
        self.run_scuba(['multi', 'with', 'args'], 128)



    def test_version(self):
        '''Verify scuba prints its version for -v'''

        out, err = self.run_scuba(['-v'])


        # Argparse in Python < 3.4 printed version to stderr, but
        # changed that to stdout in 3.4. We don't care where it goes.
        # https://bugs.python.org/issue18920
        check = out or err

        assert_startswith(check, 'scuba')

        ver = check.split()[1]
        assert_equal(ver, scuba.__version__)


    def test_no_docker(self):
        '''Verify scuba gracefully handles docker not being installed'''

        with open('.scuba.yml', 'w') as f:
            f.write('image: {0}\n'.format(DOCKER_IMAGE))

        args = ['/bin/echo', '-n', 'my output']

        old_PATH = os.environ['PATH']
        os.environ['PATH'] = ''

        try:
            _, err = self.run_scuba(args, 2)
        finally:
            os.environ['PATH'] = old_PATH

    @mock.patch('subprocess.call')
    def test_dry_run(self, subproc_call_mock):
        '''Verify scuba handles --dry-run and --verbose'''

        with open('.scuba.yml', 'w') as f:
            f.write('image: {0}\n'.format(DOCKER_IMAGE))

        args = ['--dry-run', '--verbose', '/bin/false']

        _, err = self.run_scuba(args, 42)

        assert_false(subproc_call_mock.called)

        #TODO: Assert temp files are not cleaned up?


    def test_args(self):
        '''Verify scuba handles cmdline args'''

        with open('.scuba.yml', 'w') as f:
            f.write('image: {0}\n'.format(DOCKER_IMAGE))

        with open('test.sh', 'w') as f:
            f.write('#!/bin/sh\n')
            f.write('for a in "$@"; do echo $a; done\n')
        make_executable('test.sh')

        lines = ['here', 'are', 'some args']

        out, _ = self.run_scuba(['./test.sh'] + lines)

        assert_seq_equal(out.splitlines(), lines)


    def test_created_file_ownership(self):
        '''Verify files created under scuba have correct ownership'''

        with open('.scuba.yml', 'w') as f:
            f.write('image: {0}\n'.format(DOCKER_IMAGE))

        filename = 'newfile.txt'

        self.run_scuba(['/bin/touch', filename])

        st = os.stat(filename)
        assert_equal(st.st_uid, os.getuid())
        assert_equal(st.st_gid, os.getgid())


    def _setup_test_tty(self):
        with open('.scuba.yml', 'w') as f:
            f.write('image: {0}\n'.format(DOCKER_IMAGE))

        with open('check_tty.sh', 'w') as f:
            f.write('#!/bin/sh\n')
            f.write('if [ -t 1 ]; then echo "isatty"; else echo "notatty"; fi\n')
        make_executable('check_tty.sh')

    def test_with_tty(self):
        '''Verify docker allocates tty if stdout is a tty.'''
        self._setup_test_tty()

        out, _ = self.run_scuba(['./check_tty.sh'], mock_isatty=True)

        assert_str_equalish(out, 'isatty')

    def test_without_tty(self):
        '''Verify docker doesn't allocate tty if stdout is not a tty.'''
        self._setup_test_tty()

        out, _ = self.run_scuba(['./check_tty.sh'])

        assert_str_equalish(out, 'notatty')

    def test_redirect_stdin(self):
        '''Verify stdin redirection works'''
        with open('.scuba.yml', 'w') as f:
            f.write('image: {0}\n'.format(DOCKER_IMAGE))

        test_str = 'hello world'
        with TemporaryFile(prefix='scubatest-stdin', mode='w+t') as stdin:
            stdin.write(test_str)
            stdin.seek(0)
            out, _ = self.run_scuba(['cat'], stdin=stdin)

        assert_str_equalish(out, test_str)


    def _test_user(self, scuba_args=[]):
        with open('.scuba.yml', 'w') as f:
            f.write('image: {0}\n'.format(DOCKER_IMAGE))

        args = scuba_args + ['/bin/sh', '-c', 'echo $(id -u) $(id -un) $(id -g) $(id -gn)']
        out, _ = self.run_scuba(args)

        uid, username, gid, groupname = out.split()
        return int(uid), username, int(gid), groupname


    def test_user_scubauser(self):
        '''Verify scuba runs container as the current (host) uid/gid'''

        uid, username, gid, groupname = self._test_user()

        assert_equal(uid, os.getuid())
        assert_equal(username, scuba.constants.SCUBA_USER)
        assert_equal(gid, os.getgid())
        assert_equal(groupname, scuba.constants.SCUBA_GROUP)


    def test_user_root(self):
        '''Verify scuba -r runs container as root'''

        uid, username, gid, groupname = self._test_user(['-r'])

        assert_equal(uid, 0)
        assert_equal(username, 'root')
        assert_equal(gid, 0)
        assert_equal(groupname, 'root')
    

    def _test_home_writable(self, scuba_args=[]):
        with open('.scuba.yml', 'w') as f:
            f.write('image: {0}\n'.format(DOCKER_IMAGE))

        args = scuba_args + ['/bin/sh', '-c', 'echo success >> ~/testfile; cat ~/testfile']
        out, _ = self.run_scuba(args)

        assert_str_equalish(out, 'success')


    def test_home_writable_scubauser(self):
        '''Verify scubauser has a writable homedir'''
        self._test_home_writable()


    def test_home_writable_root(self):
        '''Verify root has a writable homedir'''
        self._test_home_writable(['-r'])


    def test_arbitrary_docker_args(self):
        '''Verify -d successfully passes arbitrary docker arguments'''

        with open('.scuba.yml', 'w') as f:
            f.write('image: {0}\n'.format(DOCKER_IMAGE))

        data = 'Lorem ipsum dolor sit amet'
        data_path = '/lorem/ipsum'

        with NamedTemporaryFile(mode='wt') as tempf:
            tempf.write(data)
            tempf.flush()

            args = [
                '-d=-v {0}:{1}:ro,z'.format(tempf.name, data_path),
                'cat', data_path,
            ]
            out, _ = self.run_scuba(args)

        assert_str_equalish(out, data)

    def test_image_entrypoint(self):
        '''Verify scuba doesn't interfere with the configured image ENTRYPOINT'''

        with open('.scuba.yml', 'w') as f:
            # This image was built with ENTRYPOINT ["echo"]
            f.write('image: jreinhart/echo')

        test_string = 'Hello world'
        out, _ = self.run_scuba([test_string])
        assert_str_equalish(test_string, out)

    def test_image_override(self):
        '''Verify --image works'''

        with open('.scuba.yml', 'w') as f:
            # This image does not exist
            f.write('image: jreinhart/notheredoesnotexistbb7e344f9722\n')

        test_string = 'Hello world'
        args = [
            # This image was built with ENTRYPOINT ["echo"]
            '--image', 'jreinhart/echo',
            test_string,
        ]
        out, _ = self.run_scuba(args)
        assert_str_equalish(test_string, out)

    def test_image_override_with_alias(self):
        '''Verify --image works with aliases'''

        with open('.scuba.yml', 'w') as f:
            # These images do not exist
            f.write('''
                image: jreinhart/notheredoesnotexistbb7e344f9722
                aliases:
                  testalias:
                    image: jreinhart/notheredoesnotexist765205d09dea
                    script:
                      - echo multi
                      - echo line
                      - echo alias
                ''')

        args = [
            '--image', DOCKER_IMAGE,
            'testalias',
        ]
        out, _ = self.run_scuba(args)
        assert_str_equalish('multi\nline\nalias', out)

    def test_yml_not_needed_with_image_override(self):
        '''Verify .scuba.yml can be missing if --image is used'''

        # no .scuba.yml

        test_string = 'Hello world'
        args = [
            # This image was built with ENTRYPOINT ["echo"]
            '--image', 'jreinhart/echo',
            test_string,
        ]
        out, _ = self.run_scuba(args)
        assert_str_equalish(test_string, out)

    def test_complex_commands_in_alias(self):
        '''Verify complex commands can be used in alias scripts'''
        test_string = 'Hello world'
        os.mkdir('foo')
        with open('foo/bar.txt', 'w') as f:
            f.write(test_string)
        with open('.scuba.yml', 'w') as f:
            f.write('image: {0}\n'.format(DOCKER_IMAGE))
            f.write('aliases:\n')
            f.write('  alias1:\n')
            f.write('    script:\n')
            f.write('      - cd foo && cat bar.txt\n')

        out, _ = self.run_scuba(['alias1'])
        assert_str_equalish(test_string, out)


    ############################################################################
    # Hooks

    def _test_one_hook(self, hookname, exp_uid, exp_gid):
        with open('.scuba.yml', 'w') as f:
            f.write('image: {0}\n'.format(DOCKER_IMAGE))
            f.write('hooks:\n')
            f.write('  {0}: echo $(id -u) $(id -g)\n'.format(hookname))

        args = ['/bin/sh', '-c', 'echo success']
        out, _ = self.run_scuba(args)

        out = out.splitlines()

        uid, gid = map(int, out[0].split())
        assert_equal(exp_uid, uid)
        assert_equal(exp_gid, gid)

        assert_str_equalish(out[1], 'success')

    def test_user_hook(self):
        '''Verify user hook executes as user'''
        self._test_one_hook('user', os.getuid(), os.getgid())

    def test_root_hook(self):
        '''Verify root hook executes as root'''
        self._test_one_hook('root', 0, 0)


    ############################################################################
    # Misc
    def test_list_aliases(self):
        '''Verify --list-aliases works'''
        with open('.scuba.yml', 'w') as f:
            f.write('image: default\n')
            f.write('aliases:\n')
            f.write('  aaa:\n')
            f.write('    image: aaa_image\n')
            f.write('    script:\n')
            f.write('      - foo\n')
            f.write('  bbb:\n')
            f.write('    script:\n')
            f.write('      - foo\n')
            f.write('  ccc: foo\n')

        expected = (
            ('ALIAS',   'IMAGE'),
            ('aaa',     'aaa_image'),
            ('bbb',     'default'),
            ('ccc',     'default'),
        )

        out, err = self.run_scuba(['--list-aliases'])
        lines = out.splitlines()

        assert_equal(len(expected), len(lines))
        for i in range(len(expected)):
            assert_seq_equal(expected[i], lines[i].split('\t'))
