from .utils import *
from unittest import mock
import pytest
import warnings

import logging
import os
import sys
from pathlib import Path
from tempfile import TemporaryFile, NamedTemporaryFile
import subprocess
import shlex
from pwd import getpwuid
from grp import getgrgid

import scuba.__main__ as main
import scuba.constants
import scuba.dockerutil
import scuba
import re

from .const import DOCKER_IMAGE

SCUBAINIT_EXIT_FAIL = 99


@pytest.mark.usefixtures("in_tmp_path")
class TestMain:
    def run_scuba(self, args, exp_retval=0, mock_isatty=False, stdin=None):
        """Run scuba, checking its return value

        Returns scuba/docker stdout data.
        """

        # Capture both scuba and docker's stdout/stderr,
        # just as the user would see it.
        with TemporaryFile(prefix="scubatest-stdout", mode="w+t") as stdout:
            with TemporaryFile(prefix="scubatest-stderr", mode="w+t") as stderr:
                if mock_isatty:
                    stdout = PseudoTTY(stdout)
                    stderr = PseudoTTY(stderr)

                old_stdin = sys.stdin
                old_stdout = sys.stdout
                old_stderr = sys.stderr

                if stdin is None:
                    sys.stdin = open(os.devnull, "w")
                else:
                    sys.stdin = stdin
                sys.stdout = stdout
                sys.stderr = stderr

                try:
                    """
                    Call scuba's main(), and expect it to either exit()
                    with a given return code, or return (implying an exit
                    status of 0).
                    """
                    try:
                        main.main(argv=args)
                    except SystemExit as sysexit:
                        retcode = sysexit.code
                    else:
                        retcode = 0

                    stdout.seek(0)
                    stderr.seek(0)

                    stdout_data = stdout.read()
                    stderr_data = stderr.read()

                    logging.info("scuba stdout:\n" + stdout_data)
                    logging.info("scuba stderr:\n" + stderr_data)

                    # Verify the return value was as expected
                    assert exp_retval == retcode

                    return stdout_data, stderr_data

                finally:
                    sys.stdin = old_stdin
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr

    def test_basic(self) -> None:
        """Verify basic scuba functionality"""

        with open(".scuba.yml", "w") as f:
            f.write(f"image: {DOCKER_IMAGE}\n")

        args = ["/bin/echo", "-n", "my output"]
        out, _ = self.run_scuba(args)

        assert_str_equalish("my output", out)

    def test_no_cmd(self) -> None:
        """Verify scuba works with no given command"""

        with open(".scuba.yml", "w") as f:
            f.write("image: scuba/hello\n")

        out, _ = self.run_scuba([])
        assert_str_equalish(out, "Hello world")

    def test_no_image_cmd(self) -> None:
        """Verify scuba gracefully handles an image with no Cmd and no user command"""

        with open(".scuba.yml", "w") as f:
            f.write("image: scuba/scratch\n")

        # ScubaError -> exit(128)
        out, _ = self.run_scuba([], 128)

    def test_handle_get_image_command_error(self) -> None:
        """Verify scuba handles a get_image_command error"""

        with open(".scuba.yml", "w") as f:
            f.write(f"image: {DOCKER_IMAGE}\n")

        def mocked_gic(*args, **kw):
            raise scuba.dockerutil.DockerError("mock error")

        # http://alexmarandon.com/articles/python_mock_gotchas/#patching-in-the-wrong-place
        # http://www.voidspace.org.uk/python/mock/patch.html#where-to-patch
        with mock.patch("scuba.scuba.get_image_command", side_effect=mocked_gic):
            # DockerError -> exit(128)
            self.run_scuba([], 128)

    def test_config_error(self) -> None:
        """Verify config errors are handled gracefully"""

        with open(".scuba.yml", "w") as f:
            f.write("invalid_key: is no good\n")

        # ConfigError -> exit(128)
        self.run_scuba([], 128)

    def test_multiline_alias_no_args_error(self) -> None:
        """Verify config errors from passing arguments to multi-line alias are caught"""
        with open(".scuba.yml", "w") as f:
            f.write(
                f"""
                image: {DOCKER_IMAGE}
                aliases:
                  multi:
                    script:
                      - echo multi
                      - echo line
                      - echo alias
                """
            )

        # ConfigError -> exit(128)
        self.run_scuba(["multi", "with", "args"], 128)

    def test_version(self) -> None:
        """Verify scuba prints its version for -v"""

        out, err = self.run_scuba(["-v"])

        name, ver = out.split()
        assert name == "scuba"
        assert ver == scuba.__version__

    def test_no_docker(self) -> None:
        """Verify scuba gracefully handles docker not being installed"""

        with open(".scuba.yml", "w") as f:
            f.write(f"image: {DOCKER_IMAGE}\n")

        args = ["/bin/echo", "-n", "my output"]

        old_PATH = os.environ["PATH"]
        os.environ["PATH"] = ""

        try:
            _, err = self.run_scuba(args, 2)
        finally:
            os.environ["PATH"] = old_PATH

    @mock.patch("subprocess.call")
    def test_dry_run(self, subproc_call_mock):
        """Verify scuba handles --dry-run and --verbose"""

        with open(".scuba.yml", "w") as f:
            f.write(f"image: {DOCKER_IMAGE}\n")

        args = ["--dry-run", "--verbose", "/bin/false"]

        _, err = self.run_scuba(args)

        assert not subproc_call_mock.called

        # TODO: Assert temp files are not cleaned up?

    def test_args(self) -> None:
        """Verify scuba handles cmdline args"""

        with open(".scuba.yml", "w") as f:
            f.write(f"image: {DOCKER_IMAGE}\n")

        with open("test.sh", "w") as f:
            f.write("#!/bin/sh\n")
            f.write('for a in "$@"; do echo $a; done\n')
        make_executable("test.sh")

        lines = ["here", "are", "some args"]

        out, _ = self.run_scuba(["./test.sh"] + lines)

        assert_seq_equal(out.splitlines(), lines)

    def test_created_file_ownership(self) -> None:
        """Verify files created under scuba have correct ownership"""

        with open(".scuba.yml", "w") as f:
            f.write(f"image: {DOCKER_IMAGE}\n")

        filename = "newfile.txt"

        self.run_scuba(["/bin/touch", filename])

        st = os.stat(filename)
        assert st.st_uid == os.getuid()
        assert st.st_gid == os.getgid()

    def _setup_test_tty(self) -> None:
        with open(".scuba.yml", "w") as f:
            f.write(f"image: {DOCKER_IMAGE}\n")

        with open("check_tty.sh", "w") as f:
            f.write("#!/bin/sh\n")
            f.write('if [ -t 1 ]; then echo "isatty"; else echo "notatty"; fi\n')
        make_executable("check_tty.sh")

    @skipUnlessTty()
    def test_with_tty(self) -> None:
        """Verify docker allocates tty if stdout is a tty."""
        self._setup_test_tty()

        out, _ = self.run_scuba(["./check_tty.sh"], mock_isatty=True)

        assert_str_equalish(out, "isatty")

    @skipUnlessTty()
    def test_without_tty(self) -> None:
        """Verify docker doesn't allocate tty if stdout is not a tty."""
        self._setup_test_tty()

        out, _ = self.run_scuba(["./check_tty.sh"])

        assert_str_equalish(out, "notatty")

    def test_redirect_stdin(self) -> None:
        """Verify stdin redirection works"""
        with open(".scuba.yml", "w") as f:
            f.write(f"image: {DOCKER_IMAGE}\n")

        test_str = "hello world"
        with TemporaryFile(prefix="scubatest-stdin", mode="w+t") as stdin:
            stdin.write(test_str)
            stdin.seek(0)
            out, _ = self.run_scuba(["cat"], stdin=stdin)

        assert_str_equalish(out, test_str)

    def _test_user(
        self,
        expected_uid,
        expected_username,
        expected_gid,
        expected_groupname,
        scuba_args=[],
    ):
        with open(".scuba.yml", "w") as f:
            f.write(f"image: {DOCKER_IMAGE}\n")

        args = scuba_args + [
            "/bin/sh",
            "-c",
            "echo $(id -u) $(id -un) $(id -g) $(id -gn)",
        ]
        out, _ = self.run_scuba(args)

        uid, username, gid, groupname = out.split()
        uid = int(uid)
        gid = int(gid)

        assert uid == expected_uid
        assert username == expected_username
        assert gid == expected_gid
        assert groupname == expected_groupname

    def test_user_scubauser(self) -> None:
        """Verify scuba runs container as the current (host) uid/gid"""
        self._test_user(
            expected_uid=os.getuid(),
            expected_username=getpwuid(os.getuid()).pw_name,
            expected_gid=os.getgid(),
            expected_groupname=getgrgid(os.getgid()).gr_name,
        )

    EXPECT_ROOT = dict(
        expected_uid=0,
        expected_username="root",
        expected_gid=0,
        expected_groupname="root",
    )

    def test_user_root(self) -> None:
        """Verify scuba -r runs container as root"""
        self._test_user(
            **self.EXPECT_ROOT,
            scuba_args=["-r"],
        )

    def test_user_run_as_root(self) -> None:
        '''Verify running scuba as root is identical to "scuba -r"'''

        with mock.patch("os.getuid", return_value=0) as getuid_mock, mock.patch(
            "os.getgid", return_value=0
        ) as getgid_mock:
            self._test_user(**self.EXPECT_ROOT)
            assert getuid_mock.called
            assert getgid_mock.called

    def test_user_root_alias(self) -> None:
        """Verify that aliases can set whether the container is run as root"""
        with open(".scuba.yml", "w") as f:
            f.write(
                f"""
                image: {DOCKER_IMAGE}
                aliases:
                  root_test:
                    root: true
                    script:
                      - echo $(id -u) $(id -un) $(id -g) $(id -gn)
                """
            )

        out, _ = self.run_scuba(["root_test"])
        uid, username, gid, groupname = out.split()

        assert int(uid) == 0
        assert username == "root"
        assert int(gid) == 0
        assert groupname == "root"

        # No one should ever specify 'root: false' in an alias, but Scuba should behave
        # correctly if they do
        with open(".scuba.yml", "w") as f:
            f.write(
                f"""
                image: {DOCKER_IMAGE}
                aliases:
                  no_root_test:
                    root: false
                    script:
                      - echo $(id -u) $(id -un) $(id -g) $(id -gn)
                """
            )

        out, _ = self.run_scuba(["no_root_test"])
        uid, username, gid, groupname = out.split()

        assert int(uid) == os.getuid()
        assert username == getpwuid(os.getuid()).pw_name
        assert int(gid) == os.getgid()
        assert groupname == getgrgid(os.getgid()).gr_name

    def _test_home_writable(self, scuba_args=[]):
        with open(".scuba.yml", "w") as f:
            f.write(f"image: {DOCKER_IMAGE}\n")

        args = scuba_args + [
            "/bin/sh",
            "-c",
            "echo success >> ~/testfile; cat ~/testfile",
        ]
        out, _ = self.run_scuba(args)

        assert_str_equalish(out, "success")

    def test_home_writable_scubauser(self) -> None:
        """Verify scubauser has a writable homedir"""

        # Run this test in /home/$username if applicable
        username = getpwuid(os.getuid()).pw_name
        homedir = os.path.expanduser("~")

        expected = os.path.join("/home", username)
        if homedir != expected:
            warnings.warn(
                f"Homedir ({homedir}) is not as expected ({expected}); "
                "test inconclusive"
            )

        with InTempDir(prefix="tmp-scubatest-", dir=homedir):
            self._test_home_writable()

    def test_home_writable_root(self) -> None:
        """Verify root has a writable homedir"""
        self._test_home_writable(["-r"])

    def test_arbitrary_docker_args(self) -> None:
        """Verify -d successfully passes arbitrary docker arguments"""

        with open(".scuba.yml", "w") as f:
            f.write(f"image: {DOCKER_IMAGE}\n")

        data = "Lorem ipsum dolor sit amet"
        data_path = "/lorem/ipsum"

        with NamedTemporaryFile(mode="wt") as tempf:
            tempf.write(data)
            tempf.flush()

            args = [
                f"-d=-v {tempf.name}:{data_path}:ro,z",
                "cat",
                data_path,
            ]
            out, _ = self.run_scuba(args)

        assert_str_equalish(out, data)

    def test_arbitrary_docker_args_merge_config(self) -> None:
        """Verify -d arguments are merged with docker_args in the config"""
        dummy = Path("dummy")
        dummy.touch()
        expfiles = set()
        tgtdir = "/tgtdir"

        def mount_dummy(name):
            assert name not in expfiles
            expfiles.add(name)
            return f'-v "{dummy.absolute()}:{tgtdir}/{name}"\n'

        with open(".scuba.yml", "w") as f:
            f.write(f"image: {DOCKER_IMAGE}\n")
            f.write("docker_args: " + mount_dummy("one"))

        args = [
            "-d=" + mount_dummy("two"),
            "ls",
            tgtdir,
        ]
        out, _ = self.run_scuba(args)

        files = set(out.splitlines())
        assert files == expfiles

    def test_nested_sript(self) -> None:
        """Verify nested scripts works"""
        with open(".scuba.yml", "w") as f:
            f.write(f"image: {DOCKER_IMAGE}\n")
            f.write("aliases:\n")
            f.write("  foo:\n")
            f.write("    script:\n")
            f.write('      - echo "This"\n')
            f.write('      - - echo "list"\n')
            f.write('        - echo "is"\n')
            f.write('        - echo "nested"\n')
            f.write('        - - echo "kinda"\n')
            f.write('          - echo "crazy"\n')

        test_str = "This list is nested kinda crazy"
        out, _ = self.run_scuba(["foo"])

        out = out.replace("\n", " ")
        assert_str_equalish(out, test_str)

    ############################################################################
    # Entrypoint

    def test_image_entrypoint(self) -> None:
        """Verify scuba doesn't interfere with the configured image ENTRYPOINT"""

        with open(".scuba.yml", "w") as f:
            f.write("image: scuba/entrypoint-test")

        out, _ = self.run_scuba(["cat", "entrypoint_works.txt"])
        assert_str_equalish("success", out)

    def test_image_entrypoint_multiline(self) -> None:
        """Verify entrypoints are handled correctly with multi-line scripts"""
        with open(".scuba.yml", "w") as f:
            f.write(
                """
                image: scuba/entrypoint-test
                aliases:
                  testalias:
                    script:
                      - cat entrypoint_works.txt
                      - echo $ENTRYPOINT_WORKS
                """
            )

        out, _ = self.run_scuba(["testalias"])
        assert_str_equalish("\n".join(["success"] * 2), out)

    def test_entrypoint_override(self) -> None:
        """Verify --entrypoint override works"""
        with open(".scuba.yml", "w") as f:
            f.write(
                """
                image: scuba/entrypoint-test
                aliases:
                  testalias:
                    script:
                      - echo $ENTRYPOINT_WORKS
                """
            )

        test_str = "This is output from the overridden entrypoint"

        with open("new.sh", "w") as f:
            f.write("#!/bin/sh\n")
            f.write(f'echo "{test_str}"\n')
        make_executable("new.sh")

        args = [
            "--entrypoint",
            os.path.abspath("new.sh"),
            "true",
        ]
        out, _ = self.run_scuba(args)
        assert_str_equalish(test_str, out)

    def test_entrypoint_override_none(self) -> None:
        """Verify --entrypoint override (to nothing) works"""
        with open(".scuba.yml", "w") as f:
            f.write(
                """
                image: scuba/entrypoint-test
                aliases:
                  testalias:
                    script:
                      - echo $ENTRYPOINT_WORKS
                """
            )

        args = [
            "--entrypoint",
            "",
            "testalias",
        ]
        out, _ = self.run_scuba(args)

        # Verify that ENTRYPOINT_WORKS was not set by the entrypoint
        # (because it didn't run)
        assert_str_equalish("", out)

    def test_yaml_entrypoint_override(self) -> None:
        """Verify entrypoint in .scuba.yml works"""
        with open(".scuba.yml", "w") as f:
            f.write(
                """
                image: scuba/entrypoint-test
                entrypoint: "./new.sh"
                """
            )

        test_str = "This is output from the overridden entrypoint"

        with open("new.sh", "w") as f:
            f.write("#!/bin/sh\n")
            f.write(f'echo "{test_str}"\n')
        make_executable("new.sh")

        args = [
            "true",
        ]
        out, _ = self.run_scuba(args)
        assert_str_equalish(test_str, out)

    def test_yaml_entrypoint_override_none(self) -> None:
        """Verify "none" entrypoint in .scuba.yml works"""
        with open(".scuba.yml", "w") as f:
            f.write(
                """
                image: scuba/entrypoint-test
                entrypoint:
                aliases:
                  testalias:
                    script:
                      - echo $ENTRYPOINT_WORKS
                """
            )

        args = [
            "testalias",
        ]
        out, _ = self.run_scuba(args)

        # Verify that ENTRYPOINT_WORKS was not set by the entrypoint
        # (because it didn't run)
        assert_str_equalish("", out)

    ############################################################################
    # Image override

    def test_image_override(self) -> None:
        """Verify --image works"""

        with open(".scuba.yml", "w") as f:
            # This image does not exist
            f.write("image: scuba/notheredoesnotexistbb7e344f9722\n")

        args = [
            "--image",
            DOCKER_IMAGE,
            "echo",
            "success",
        ]
        out, _ = self.run_scuba(args)
        assert_str_equalish("success", out)

    def test_image_override_with_alias(self) -> None:
        """Verify --image works with aliases"""

        with open(".scuba.yml", "w") as f:
            # These images do not exist
            f.write(
                """
                image: scuba/notheredoesnotexistbb7e344f9722
                aliases:
                  testalias:
                    image: scuba/notheredoesnotexist765205d09dea
                    script:
                      - echo multi
                      - echo line
                      - echo alias
                """
            )

        args = [
            "--image",
            DOCKER_IMAGE,
            "testalias",
        ]
        out, _ = self.run_scuba(args)
        assert_str_equalish("multi\nline\nalias", out)

    def test_yml_not_needed_with_image_override(self) -> None:
        """Verify .scuba.yml can be missing if --image is used"""

        # no .scuba.yml

        args = [
            "--image",
            DOCKER_IMAGE,
            "echo",
            "success",
        ]
        out, _ = self.run_scuba(args)
        assert_str_equalish("success", out)

    def test_complex_commands_in_alias(self) -> None:
        """Verify complex commands can be used in alias scripts"""
        test_string = "Hello world"
        os.mkdir("foo")
        with open("foo/bar.txt", "w") as f:
            f.write(test_string)
        with open(".scuba.yml", "w") as f:
            f.write(f"image: {DOCKER_IMAGE}\n")
            f.write("aliases:\n")
            f.write("  alias1:\n")
            f.write("    script:\n")
            f.write("      - cd foo && cat bar.txt\n")

        out, _ = self.run_scuba(["alias1"])
        assert_str_equalish(test_string, out)

    ############################################################################
    # Hooks

    def _test_one_hook(self, hookname, hookcmd, cmd, exp_retval=0):
        with open(".scuba.yml", "w") as f:
            f.write(f"image: {DOCKER_IMAGE}\n")
            f.write("hooks:\n")
            f.write(f"  {hookname}: {hookcmd}\n")

        args = ["/bin/sh", "-c", cmd]
        return self.run_scuba(args, exp_retval=exp_retval)

    def _test_hook_runs_as(self, hookname, exp_uid, exp_gid) -> None:
        out, _ = self._test_one_hook(
            hookname,
            "echo $(id -u) $(id -g)",
            "echo success",
        )
        out = out.splitlines()

        uid, gid = map(int, out[0].split())
        assert exp_uid == uid
        assert exp_gid == gid

        assert_str_equalish(out[1], "success")

    def test_user_hook_runs_as_user(self) -> None:
        """Verify user hook executes as user"""
        self._test_hook_runs_as("user", os.getuid(), os.getgid())

    def test_root_hook_runs_as_root(self) -> None:
        """Verify root hook executes as root"""
        self._test_hook_runs_as("root", 0, 0)

    def test_hook_failure_shows_correct_status(self) -> None:
        testval = 42
        out, err = self._test_one_hook(
            "root",
            f"exit {testval}",
            "dont care",
            exp_retval=SCUBAINIT_EXIT_FAIL,
        )
        assert re.match(f"^scubainit: .* exited with status {testval}$", err)

    ############################################################################
    # Environment

    def test_env_var_keyval(self) -> None:
        """Verify -e KEY=VAL works"""
        with open(".scuba.yml", "w") as f:
            f.write(f"image: {DOCKER_IMAGE}\n")
        args = [
            "-e",
            "KEY=VAL",
            "/bin/sh",
            "-c",
            "echo $KEY",
        ]
        out, _ = self.run_scuba(args)
        assert_str_equalish(out, "VAL")

    def test_env_var_key_only(self, monkeypatch):
        """Verify -e KEY works"""
        with open(".scuba.yml", "w") as f:
            f.write(f"image: {DOCKER_IMAGE}\n")
        args = [
            "-e",
            "KEY",
            "/bin/sh",
            "-c",
            "echo $KEY",
        ]
        monkeypatch.setenv("KEY", "mockedvalue")
        out, _ = self.run_scuba(args)
        assert_str_equalish(out, "mockedvalue")

    def test_env_var_sources(self, monkeypatch):
        """Verify scuba handles all possible environment variable sources"""
        with open(".scuba.yml", "w") as f:
            f.write(
                rf"""
                image: {DOCKER_IMAGE}
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
                """
            )

        args = [
            "-e",
            "EXTERNAL_1",
            "-e",
            "BAZ=From the command line",
            "al",
        ]

        monkeypatch.setenv("EXTERNAL_1", "External value 1")
        monkeypatch.setenv("EXTERNAL_2", "External value 2")
        monkeypatch.setenv("EXTERNAL_3", "External value 3")

        out, _ = self.run_scuba(args)

        # Convert key/pair output to dictionary
        result = dict(pair.split("=", 1) for pair in shlex.split(out))

        assert result == dict(
            FOO="Overridden",
            BAR="42",
            MORE="Hello world",
            EXTERNAL_1="External value 1",
            EXTERNAL_2="External value 2",
            EXTERNAL_3="External value 3",
            BAZ="From the command line",
        )

    def test_builtin_env__SCUBA_ROOT(self, in_tmp_path):
        """Verify SCUBA_ROOT is set in container"""
        with open(".scuba.yml", "w") as f:
            f.write(f"image: {DOCKER_IMAGE}\n")

        args = ["/bin/sh", "-c", "echo $SCUBA_ROOT"]
        out, _ = self.run_scuba(args)

        assert_str_equalish(in_tmp_path, out)

    ############################################################################
    # Shell Override

    def test_use_top_level_shell_override(self) -> None:
        """Verify that the shell can be overriden at the top level"""
        with open(".scuba.yml", "w") as f:
            f.write(
                f"""
                image: {DOCKER_IMAGE}
                shell: /bin/bash
                aliases:
                  check_shell:
                    script: readlink -f /proc/$$/exe
                """
            )

        out, _ = self.run_scuba(["check_shell"])
        # If we failed to override, the shebang would be #!/bin/sh
        assert_str_equalish("/bin/bash", out)

    def test_alias_level_shell_override(self) -> None:
        """Verify that the shell can be overriden at the alias level without affecting other aliases"""
        with open(".scuba.yml", "w") as f:
            f.write(
                f"""
                image: {DOCKER_IMAGE}
                aliases:
                  shell_override:
                    shell: /bin/bash
                    script: readlink -f /proc/$$/exe
                  default_shell:
                    script: readlink -f /proc/$$/exe
                """
            )
        out, _ = self.run_scuba(["shell_override"])
        assert_str_equalish("/bin/bash", out)

        out, _ = self.run_scuba(["default_shell"])
        # The way that we check the shell uses the resolved symlink of /bin/sh,
        # which is /bin/dash on Debian
        assert out.strip() in ["/bin/sh", "/bin/dash"]

    def test_cli_shell_override(self) -> None:
        """Verify that the shell can be overriden by the CLI"""
        with open(".scuba.yml", "w") as f:
            f.write(
                f"""
                image: {DOCKER_IMAGE}
                aliases:
                  default_shell:
                    script: readlink -f /proc/$$/exe
                """
            )

        out, _ = self.run_scuba(["--shell", "/bin/bash", "default_shell"])
        assert_str_equalish("/bin/bash", out)

    def test_shell_override_precedence(self) -> None:
        """Verify that shell overrides at different levels override each other as expected"""
        # Precedence expectations are (with "<<" meaning "overridden by"):
        # Top-level SCUBA_YML shell << alias-level SCUBA_YML shell << CLI-specified shell

        # Test top-level << alias-level
        with open(".scuba.yml", "w") as f:
            f.write(
                f"""
                image: {DOCKER_IMAGE}
                shell: /bin/this_does_not_exist
                aliases:
                  shell_override:
                    shell: /bin/bash
                    script: readlink -f /proc/$$/exe
                """
            )
        out, _ = self.run_scuba(["shell_override"])
        assert_str_equalish("/bin/bash", out)

        # Test alias-level << CLI
        with open(".scuba.yml", "w") as f:
            f.write(
                f"""
                image: {DOCKER_IMAGE}
                aliases:
                  shell_overridden:
                    shell: /bin/this_is_not_a_real_shell
                    script: readlink -f /proc/$$/exe
                """
            )
        out, _ = self.run_scuba(["--shell", "/bin/bash", "shell_overridden"])
        assert_str_equalish("/bin/bash", out)

        # Test top-level << CLI
        with open(".scuba.yml", "w") as f:
            f.write(
                f"""
                image: {DOCKER_IMAGE}
                shell: /bin/this_is_not_a_real_shell
                aliases:
                  shell_check: readlink -f /proc/$$/exe
                """
            )
        out, _ = self.run_scuba(["--shell", "/bin/bash", "shell_check"])
        assert_str_equalish("/bin/bash", out)

    ############################################################################
    # Volumes

    def test_volumes_basic(self) -> None:
        """Verify volumes can be added at top-level and alias"""

        # Create some temporary directories with a file in each
        topdata = Path("./topdata")
        topdata.mkdir()
        (topdata / "thing").write_text("from the top\n")

        aliasdata = Path("./aliasdata")
        aliasdata.mkdir()
        (aliasdata / "thing").write_text("from the alias\n")

        with open(".scuba.yml", "w") as f:
            f.write(
                f"""
                image: {DOCKER_IMAGE}
                volumes:
                  /topdata: {topdata.absolute()}
                aliases:
                  doit:
                    volumes:
                      /aliasdata: {aliasdata.absolute()}
                    script: "cat /topdata/thing /aliasdata/thing"
                """
            )

        out, _ = self.run_scuba(["doit"])
        out = out.splitlines()
        assert out == ["from the top", "from the alias"]

    def test_volumes_alias_override(self) -> None:
        """Verify volumes can be overridden by an alias"""

        # Create some temporary directories with a file in each
        topdata = Path("./topdata")
        topdata.mkdir()
        (topdata / "thing").write_text("from the top\n")

        aliasdata = Path("./aliasdata")
        aliasdata.mkdir()
        (aliasdata / "thing").write_text("from the alias\n")

        with open(".scuba.yml", "w") as f:
            f.write(
                f"""
                image: {DOCKER_IMAGE}
                volumes:
                  /data: {topdata.absolute()}
                aliases:
                  doit:
                    volumes:
                      /data: {aliasdata.absolute()}
                    script: "cat /data/thing"
                """
            )

        # Run a non-alias command
        out, _ = self.run_scuba(["cat", "/data/thing"])
        out = out.splitlines()
        assert out == ["from the top"]

        # Run the alias
        out, _ = self.run_scuba(["doit"])
        out = out.splitlines()
        assert out == ["from the alias"]

    def test_volumes_host_path_create(self) -> None:
        """Missing host paths should be created before starting Docker"""

        userdir = Path("./user")
        testfile = userdir / "test.txt"

        with open(".scuba.yml", "w") as f:
            f.write(
                f"""
                image: {DOCKER_IMAGE}
                volumes:
                  /userdir: {userdir.absolute()}
                """
            )

        self.run_scuba(["touch", "/userdir/test.txt"])

        assert testfile.exists(), "Test file was not created"

        info = userdir.stat()
        assert info.st_uid != 0, "Directory is owned by root"
        assert info.st_gid != 0, "Directory group is root"

    def test_volumes_host_path_permissions(self) -> None:
        """Host path permission errors should be ignored"""

        rootdir = Path("./root")
        userdir = rootdir / "user"
        testfile = userdir / "test.txt"

        rootdir.mkdir()

        with open(".scuba.yml", "w") as f:
            f.write(
                f"""
                image: {DOCKER_IMAGE}
                volumes:
                  /userdir: {userdir.absolute()}
                aliases:
                   doit:
                      root: true
                      script: "touch /userdir/test.txt"
                """
            )

        try:
            # Prevent current user from creating directory
            rootdir.chmod(0o555)
            self.run_scuba(["doit"])
        finally:
            # Restore permissions to allow deletion
            rootdir.chmod(0o755)

        assert testfile.exists(), "Test file was not created"

        info = userdir.stat()
        assert info.st_uid == 0, "Directory is owned by root"
        assert info.st_gid == 0, "Directory group is root"

    def test_volumes_host_path_failure(self) -> None:
        """Host path failures due to OS errors prevent Docker run"""

        rootdir = Path("./root")
        userdir = rootdir / "user"
        testfile = userdir / "test.txt"

        # rootdir is not a dir, it's a file
        rootdir.write_text("lied about the dir")

        with open(".scuba.yml", "w") as f:
            f.write(
                f"""
                image: {DOCKER_IMAGE}
                volumes:
                  /userdir: {userdir.absolute()}
                """
            )

        self.run_scuba(["touch", "/userdir/test.txt"], 128)

    def test_volumes_host_path_rel(self) -> None:
        """Volume host paths can be relative"""

        # Set up a subdir with a file to be read.
        userdir = Path("./user")
        userdir.mkdir(parents=True)

        test_message = "Relative paths work"
        (userdir / "test.txt").write_text(test_message)

        with open(".scuba.yml", "w") as f:
            f.write(
                f"""
                image: {DOCKER_IMAGE}
                volumes:
                  /userdir: ./{userdir}
                """
            )

        # Invoke scuba from a different subdir, for good measure.
        otherdir = Path("way/down/here")
        otherdir.mkdir(parents=True)
        os.chdir(otherdir)

        out, _ = self.run_scuba(["cat", "/userdir/test.txt"])
        assert out == test_message

    def test_volumes_hostpath_rel_above(self) -> None:
        """Volume host paths can be relative, above the scuba root dir"""
        # Directory structure:
        #
        # test-tmpdir/
        # |- user/                  # will be mounted at /userdir
        # |  |- test.txt
        # |- my/
        #    |- cool/
        #       |- project/         # scuba root
        #          |- .scuba.yml

        # Set up a subdir with a file to be read.
        userdir = Path("./user")
        userdir.mkdir(parents=True)

        test_message = "Relative paths work"
        (userdir / "test.txt").write_text(test_message)

        # Set up a subdir for scuba
        projdir = Path("my/cool/project")
        projdir.mkdir(parents=True)

        # Change to the project subdir and write the .scuba.yml file there.
        os.chdir(projdir)
        with open(".scuba.yml", "w") as f:
            f.write(
                f"""
                image: {DOCKER_IMAGE}
                volumes:
                  /userdir: ../../../{userdir}
                """
            )

        out, _ = self.run_scuba(["cat", "/userdir/test.txt"])
        assert out == test_message
