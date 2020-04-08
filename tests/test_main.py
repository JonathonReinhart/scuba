from nose.tools import *
from .utils import *
from unittest import TestCase
from unittest import mock

import logging
import os
import sys
from tempfile import TemporaryFile, NamedTemporaryFile
import subprocess
import shlex
from pwd import getpwuid
from grp import getgrgid

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
            f.write('image: {}\n'.format(DOCKER_IMAGE))

        args = ['/bin/echo', '-n', 'my output']
        out, _ = self.run_scuba(args)

        assert_str_equalish('my output', out)

    def test_no_cmd(self):
        '''Verify scuba works with no given command'''

        with open('.scuba.yml', 'w') as f:
            f.write('image: {}\n'.format('scuba/hello'))

        out, _ = self.run_scuba([])
        self.assertTrue('Hello world' in out)

    def test_no_image_cmd(self):
        '''Verify scuba gracefully handles an image with no Cmd and no user command'''

        with open('.scuba.yml', 'w') as f:
            f.write('image: {}\n'.format('scuba/scratch'))

        # ScubaError -> exit(128)
        out, _ = self.run_scuba([], 128)

    def test_handle_get_image_command_error(self):
        '''Verify scuba handles a get_image_command error'''

        with open('.scuba.yml', 'w') as f:
            f.write('image: {}\n'.format(DOCKER_IMAGE))

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
            f.write('image: {}\n'.format(DOCKER_IMAGE))

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
            f.write('image: {}\n'.format(DOCKER_IMAGE))

        args = ['--dry-run', '--verbose', '/bin/false']

        _, err = self.run_scuba(args, 42)

        assert_false(subproc_call_mock.called)

        #TODO: Assert temp files are not cleaned up?


    def test_args(self):
        '''Verify scuba handles cmdline args'''

        with open('.scuba.yml', 'w') as f:
            f.write('image: {}\n'.format(DOCKER_IMAGE))

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
            f.write('image: {}\n'.format(DOCKER_IMAGE))

        filename = 'newfile.txt'

        self.run_scuba(['/bin/touch', filename])

        st = os.stat(filename)
        assert_equal(st.st_uid, os.getuid())
        assert_equal(st.st_gid, os.getgid())


    def _setup_test_tty(self):
        with open('.scuba.yml', 'w') as f:
            f.write('image: {}\n'.format(DOCKER_IMAGE))

        with open('check_tty.sh', 'w') as f:
            f.write('#!/bin/sh\n')
            f.write('if [ -t 1 ]; then echo "isatty"; else echo "notatty"; fi\n')
        make_executable('check_tty.sh')

    @skipUnlessTty()
    def test_with_tty(self):
        '''Verify docker allocates tty if stdout is a tty.'''
        self._setup_test_tty()

        out, _ = self.run_scuba(['./check_tty.sh'], mock_isatty=True)

        assert_str_equalish(out, 'isatty')

    @skipUnlessTty()
    def test_without_tty(self):
        '''Verify docker doesn't allocate tty if stdout is not a tty.'''
        self._setup_test_tty()

        out, _ = self.run_scuba(['./check_tty.sh'])

        assert_str_equalish(out, 'notatty')

    def test_redirect_stdin(self):
        '''Verify stdin redirection works'''
        with open('.scuba.yml', 'w') as f:
            f.write('image: {}\n'.format(DOCKER_IMAGE))

        test_str = 'hello world'
        with TemporaryFile(prefix='scubatest-stdin', mode='w+t') as stdin:
            stdin.write(test_str)
            stdin.seek(0)
            out, _ = self.run_scuba(['cat'], stdin=stdin)

        assert_str_equalish(out, test_str)


    def _test_user(self,
                   expected_uid, expected_username,
                   expected_gid, expected_groupname,
                   scuba_args=[]):
        with open('.scuba.yml', 'w') as f:
            f.write('image: {}\n'.format(DOCKER_IMAGE))

        args = scuba_args + ['/bin/sh', '-c', 'echo $(id -u) $(id -un) $(id -g) $(id -gn)']
        out, _ = self.run_scuba(args)

        uid, username, gid, groupname = out.split()
        uid = int(uid)
        gid = int(gid)

        assert_equal(uid, expected_uid)
        assert_equal(username, expected_username)
        assert_equal(gid, expected_gid)
        assert_equal(groupname, expected_groupname)


    def test_user_scubauser(self):
        '''Verify scuba runs container as the current (host) uid/gid'''
        self._test_user(
            expected_uid = os.getuid(),
            expected_username = getpwuid(os.getuid()).pw_name,
            expected_gid = os.getgid(),
            expected_groupname = getgrgid(os.getgid()).gr_name,
        )

    EXPECT_ROOT = dict(
        expected_uid = 0,
        expected_username = 'root',
        expected_gid = 0,
        expected_groupname = 'root',
    )

    def test_user_root(self):
        '''Verify scuba -r runs container as root'''
        self._test_user(
            **self.EXPECT_ROOT,
            scuba_args = ['-r'],
        )

    def test_user_run_as_root(self):
        '''Verify running scuba as root is identical to "scuba -r"'''

        with mock.patch('os.getuid', return_value=0) as getuid_mock, \
             mock.patch('os.getgid', return_value=0) as getgid_mock:

            self._test_user(**self.EXPECT_ROOT)
            assert_true(getuid_mock.called)
            assert_true(getgid_mock.called)

    def test_user_root_alias(self):
        '''Verify that aliases can set whether the container is run as root'''
        with open('.scuba.yml', 'w') as f:
            f.write('''
                image: {image}
                aliases:
                  root_test:
                    root: true
                    script:
                      - echo $(id -u) $(id -un) $(id -g) $(id -gn)
                '''.format(image=DOCKER_IMAGE))

        out, _ = self.run_scuba(["root_test"])
        uid, username, gid, groupname = out.split()

        assert_equal(int(uid), 0)
        assert_equal(username, 'root')
        assert_equal(int(gid), 0)
        assert_equal(groupname, 'root')

        # No one should ever specify 'root: false' in an alias, but Scuba should behave
        # correctly if they do
        with open('.scuba.yml', 'w') as f:
            f.write('''
                image: {image}
                aliases:
                  no_root_test:
                    root: false
                    script:
                      - echo $(id -u) $(id -un) $(id -g) $(id -gn)
                '''.format(image=DOCKER_IMAGE))

        out, _ = self.run_scuba(["no_root_test"])
        uid, username, gid, groupname = out.split()

        assert_equal(int(uid), os.getuid())
        assert_equal(username, getpwuid(os.getuid()).pw_name)
        assert_equal(int(gid), os.getgid())
        assert_equal(groupname, getgrgid(os.getgid()).gr_name)

    def _test_home_writable(self, scuba_args=[]):
        with open('.scuba.yml', 'w') as f:
            f.write('image: {}\n'.format(DOCKER_IMAGE))

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
            f.write('image: {}\n'.format(DOCKER_IMAGE))

        data = 'Lorem ipsum dolor sit amet'
        data_path = '/lorem/ipsum'

        with NamedTemporaryFile(mode='wt') as tempf:
            tempf.write(data)
            tempf.flush()

            args = [
                '-d=-v {}:{}:ro,z'.format(tempf.name, data_path),
                'cat', data_path,
            ]
            out, _ = self.run_scuba(args)

        assert_str_equalish(out, data)


    def test_nested_sript(self):
        '''Verify nested scripts works'''
        with open('.scuba.yml', 'w') as f:
            f.write('image: {}\n'.format(DOCKER_IMAGE))
            f.write('aliases:\n')
            f.write('  foo:\n')
            f.write('    script:\n')
            f.write('      - echo "This"\n')
            f.write('      - - echo "list"\n')
            f.write('        - echo "is"\n')
            f.write('        - echo "nested"\n')
            f.write('        - - echo "kinda"\n')
            f.write('          - echo "crazy"\n')

        test_str = 'This list is nested kinda crazy'
        out, _ = self.run_scuba(['foo'])

        out = out.replace('\n', ' ')
        assert_str_equalish(out, test_str)


    ############################################################################
    # Entrypoint

    def test_image_entrypoint(self):
        '''Verify scuba doesn't interfere with the configured image ENTRYPOINT'''

        with open('.scuba.yml', 'w') as f:
            f.write('image: scuba/entrypoint-test')

        out, _ = self.run_scuba(['cat', 'entrypoint_works.txt'])
        assert_str_equalish('success', out)


    def test_image_entrypoint_multiline(self):
        '''Verify entrypoints are handled correctly with multi-line scripts'''
        with open('.scuba.yml', 'w') as f:
            f.write('''
                image: scuba/entrypoint-test
                aliases:
                  testalias:
                    script:
                      - cat entrypoint_works.txt
                      - echo $ENTRYPOINT_WORKS
                ''')

        out, _ = self.run_scuba(['testalias'])
        assert_str_equalish('\n'.join(['success']*2), out)


    def test_entrypoint_override(self):
        '''Verify --entrypoint override works'''
        with open('.scuba.yml', 'w') as f:
            f.write('''
                image: scuba/entrypoint-test
                aliases:
                  testalias:
                    script:
                      - echo $ENTRYPOINT_WORKS
                ''')

        test_str = 'This is output from the overridden entrypoint'

        with open('new.sh', 'w') as f:
            f.write('#!/bin/sh\n')
            f.write('echo "{}"\n'.format(test_str))
        make_executable('new.sh')

        args = [
            '--entrypoint', os.path.abspath('new.sh'),
            'true',
        ]
        out, _ = self.run_scuba(args)
        assert_str_equalish(test_str, out)


    def test_entrypoint_override_none(self):
        '''Verify --entrypoint override (to nothing) works'''
        with open('.scuba.yml', 'w') as f:
            f.write('''
                image: scuba/entrypoint-test
                aliases:
                  testalias:
                    script:
                      - echo $ENTRYPOINT_WORKS
                ''')

        args = [
            '--entrypoint', '',
            'testalias',
        ]
        out, _ = self.run_scuba(args)

        # Verify that ENTRYPOINT_WORKS wasn not set by the entrypoint
        # (because it didn't run)
        self.assertNotIn('success', out)


    def test_yaml_entrypoint_override(self):
        '''Verify entrypoint in .scuba.yml works'''
        with open('.scuba.yml', 'w') as f:
            f.write('''
                image: scuba/entrypoint-test
                entrypoint: "./new.sh"
                ''')

        test_str = 'This is output from the overridden entrypoint'

        with open('new.sh', 'w') as f:
            f.write('#!/bin/sh\n')
            f.write('echo "{}"\n'.format(test_str))
        make_executable('new.sh')

        args = [
            'true',
        ]
        out, _ = self.run_scuba(args)
        assert_str_equalish(test_str, out)


    def test_entrypoint_override_none(self):
        '''Verify "none" entrypoint in .scuba.yml works'''
        with open('.scuba.yml', 'w') as f:
            f.write('''
                image: scuba/entrypoint-test
                entrypoint:
                aliases:
                  testalias:
                    script:
                      - echo $ENTRYPOINT_WORKS
                ''')

        args = [
            'testalias',
        ]
        out, _ = self.run_scuba(args)

        # Verify that ENTRYPOINT_WORKS wasn not set by the entrypoint
        # (because it didn't run)
        self.assertNotIn('success', out)


    ############################################################################
    # Image override

    def test_image_override(self):
        '''Verify --image works'''

        with open('.scuba.yml', 'w') as f:
            # This image does not exist
            f.write('image: scuba/notheredoesnotexistbb7e344f9722\n')

        args = [
            '--image', DOCKER_IMAGE,
            'echo', 'success',
        ]
        out, _ = self.run_scuba(args)
        assert_str_equalish('success', out)

    def test_image_override_with_alias(self):
        '''Verify --image works with aliases'''

        with open('.scuba.yml', 'w') as f:
            # These images do not exist
            f.write('''
                image: scuba/notheredoesnotexistbb7e344f9722
                aliases:
                  testalias:
                    image: scuba/notheredoesnotexist765205d09dea
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

        args = [
            '--image', DOCKER_IMAGE,
            'echo', 'success',
        ]
        out, _ = self.run_scuba(args)
        assert_str_equalish('success', out)

    def test_complex_commands_in_alias(self):
        '''Verify complex commands can be used in alias scripts'''
        test_string = 'Hello world'
        os.mkdir('foo')
        with open('foo/bar.txt', 'w') as f:
            f.write(test_string)
        with open('.scuba.yml', 'w') as f:
            f.write('image: {}\n'.format(DOCKER_IMAGE))
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
            f.write('image: {}\n'.format(DOCKER_IMAGE))
            f.write('hooks:\n')
            f.write('  {}: echo $(id -u) $(id -g)\n'.format(hookname))

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
    # Environment

    def test_env_var_keyval(self):
        '''Verify -e KEY=VAL works'''
        with open('.scuba.yml', 'w') as f:
            f.write('image: {}\n'.format(DOCKER_IMAGE))
        args = [
            '-e', 'KEY=VAL',
            '/bin/sh', '-c', 'echo $KEY',
        ]
        out, _ = self.run_scuba(args)
        assert_str_equalish(out, 'VAL')

    def test_env_var_key_only(self):
        '''Verify -e KEY works'''
        with open('.scuba.yml', 'w') as f:
            f.write('image: {}\n'.format(DOCKER_IMAGE))
        args = [
            '-e', 'KEY',
            '/bin/sh', '-c', 'echo $KEY',
        ]
        with mocked_os_env(KEY='mockedvalue'):
            out, _ = self.run_scuba(args)
        assert_str_equalish(out, 'mockedvalue')


    def test_env_var_sources(self):
        '''Verify scuba handles all possible environment variable sources'''
        with open('.scuba.yml', 'w') as f:
            f.write(r'''
                image: {image}
                environment:
                  FOO: Top-level
                  BAR: 42
                  EXTERNAL_2:
                aliases:
                  al:
                    script:
                      - echo "FOO=\"$FOO\""
                      - echo "BAR=\"$BAR\""
                      - echo "MORE=\"$MORE\""
                      - echo "EXTERNAL_1=\"$EXTERNAL_1\""
                      - echo "EXTERNAL_2=\"$EXTERNAL_2\""
                      - echo "EXTERNAL_3=\"$EXTERNAL_3\""
                      - echo "BAZ=\"$BAZ\""
                    environment:
                      FOO: Overridden
                      MORE: Hello world
                      EXTERNAL_3:
                '''.format(image=DOCKER_IMAGE))

        args = [
            '-e', 'EXTERNAL_1',
            '-e', 'BAZ=From the command line',
            'al',
        ]

        m = mocked_os_env(
                EXTERNAL_1 = "External value 1",
                EXTERNAL_2 = "External value 2",
                EXTERNAL_3 = "External value 3",
                )
        with m:
            out, _ = self.run_scuba(args)

        # Convert key/pair output to dictionary
        result = dict( pair.split('=', 1) for pair in shlex.split(out) )

        self.assertEqual(result, dict(
                FOO = "Overridden",
                BAR = "42",
                MORE = "Hello world",
                EXTERNAL_1 = "External value 1",
                EXTERNAL_2 = "External value 2",
                EXTERNAL_3 = "External value 3",
                BAZ = "From the command line",
            ))

    def test_builtin_env__SCUBA_DIR(self):
        '''Verify SCUBA_DIR is set in container'''
        with open('.scuba.yml', 'w') as f:
            f.write('image: {}\n'.format(DOCKER_IMAGE))

        args = ['/bin/sh', '-c', 'echo $SCUBA_ROOT']
        out, _ = self.run_scuba(args)

        assert_str_equalish(self.path, out)


    ############################################################################
    # Shell Override

    def test_use_top_level_shell_override(self):
        '''Verify that the shell can be overriden at the top level'''
        with open('.scuba.yml', 'w') as f:
            f.write('''
                image: {image}
                shell: /bin/bash
                aliases:
                  check_shell:
                    script: readlink -f /proc/$$/exe
                '''.format(image=DOCKER_IMAGE))

        out, _ = self.run_scuba(['check_shell'])
        # If we failed to override, the shebang would be #!/bin/sh
        self.assertTrue("/bin/bash" in out)

    def test_alias_level_shell_override(self):
        '''Verify that the shell can be overriden at the alias level without affecting other aliases'''
        with open('.scuba.yml', 'w') as f:
            f.write('''
                image: {image}
                aliases:
                  shell_override:
                    shell: /bin/bash
                    script: readlink -f /proc/$$/exe
                  default_shell:
                    script: readlink -f /proc/$$/exe
                '''.format(image=DOCKER_IMAGE))
        out, _ = self.run_scuba(['shell_override'])
        self.assertTrue("/bin/bash" in out)

        out, _ = self.run_scuba(['default_shell'])
        # The way that we check the shell uses the resolved symlink of /bin/sh,
        # which is /bin/dash on Debian
        self.assertTrue("/bin/sh" in out or "/bin/dash" in out)

    def test_cli_shell_override(self):
        '''Verify that the shell can be overriden by the CLI'''
        with open('.scuba.yml', 'w') as f:
            f.write('''
                image: {image}
                aliases:
                  default_shell:
                    script: readlink -f /proc/$$/exe
                '''.format(image=DOCKER_IMAGE))

        out, _ = self.run_scuba(['--shell', '/bin/bash', 'default_shell'])
        self.assertTrue("/bin/bash" in out)

    def test_shell_override_precedence(self):
        '''Verify that shell overrides at different levels override each other as expected'''
        # Precedence expectations are (with "<<" meaning "overridden by"):
        # Top-level SCUBA_YML shell << alias-level SCUBA_YML shell << CLI-specified shell

        # Test top-level << alias-level
        with open('.scuba.yml', 'w') as f:
            f.write('''
                image: {image}
                shell: /bin/this_does_not_exist
                aliases:
                  shell_override:
                    shell: /bin/bash
                    script: readlink -f /proc/$$/exe
                '''.format(image=DOCKER_IMAGE))
        out, _ = self.run_scuba(['shell_override'])
        self.assertTrue("/bin/bash" in out)

        # Test alias-level << CLI
        with open('.scuba.yml', 'w') as f:
            f.write('''
                image: {image}
                aliases:
                  shell_overridden:
                    shell: /bin/this_is_not_a_real_shell
                    script: readlink -f /proc/$$/exe
                '''.format(image=DOCKER_IMAGE))
        out, _ = self.run_scuba(['--shell', '/bin/bash', 'shell_overridden'])
        self.assertTrue("/bin/bash" in out)

        # Test top-level << CLI
        with open('.scuba.yml', 'w') as f:
            f.write('''
                image: {image}
                shell: /bin/this_is_not_a_real_shell
                aliases:
                  shell_check: readlink -f /proc/$$/exe
                '''.format(image=DOCKER_IMAGE))
        out, _ = self.run_scuba(['--shell', '/bin/bash', 'shell_check'])
        self.assertTrue("/bin/bash" in out)


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
