from grp import getgrgid
import logging
import os
from pathlib import Path
from pwd import getpwuid
import pytest
import re
import shlex
import subprocess
import sys
from tempfile import TemporaryFile, NamedTemporaryFile
from textwrap import dedent
from typing import cast, IO, List, Optional, Sequence, TextIO, Tuple
from unittest import mock
import warnings

import scuba.__main__ as main
import scuba.dockerutil

from .const import DOCKER_IMAGE
from .utils import (
    assert_seq_equal,
    assert_str_equalish,
    InTempDir,
    make_executable,
    skipUnlessTty,
    PseudoTTY,
)

ScubaResult = Tuple[str, str]


SCUBA_YML = Path(".scuba.yml")
SCUBAINIT_EXIT_FAIL = 99


def write_script(path: Path, text: str) -> None:
    path.write_text(dedent(text) + "\n")
    make_executable(path)


def run_scuba(
    args: List[str],
    *,
    expect_return: int = 0,
    mock_isatty: bool = False,
    stdin: Optional[IO[str]] = None,
) -> ScubaResult:
    """Run scuba, checking its return value

    Returns scuba/docker stdout data.
    """

    # Capture both scuba and docker's stdout/stderr,
    # just as the user would see it.
    with TemporaryFile(prefix="scubatest-stdout", mode="w+t") as stdout:
        with TemporaryFile(prefix="scubatest-stderr", mode="w+t") as stderr:
            if mock_isatty:
                stdout = PseudoTTY(stdout)  # type: ignore[assignment]
                stderr = PseudoTTY(stderr)  # type: ignore[assignment]

            old_stdin = sys.stdin
            old_stdout = sys.stdout
            old_stderr = sys.stderr

            if stdin is None:
                sys.stdin = open(os.devnull, "w")
            else:
                sys.stdin = cast(TextIO, stdin)
            sys.stdout = cast(TextIO, stdout)
            sys.stderr = cast(TextIO, stderr)

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
                assert expect_return == retcode

                return stdout_data, stderr_data

            finally:
                sys.stdin = old_stdin
                sys.stdout = old_stdout
                sys.stderr = old_stderr


@pytest.mark.usefixtures("in_tmp_path")
class MainTest:
    pass


class TestMainBasic(MainTest):
    def test_basic(self) -> None:
        """Verify basic scuba functionality"""
        SCUBA_YML.write_text(f"image: {DOCKER_IMAGE}")

        args = ["/bin/echo", "-n", "my output"]
        out, _ = run_scuba(args)

        assert_str_equalish("my output", out)

    def test_no_cmd(self) -> None:
        """Verify scuba works with no given command"""
        SCUBA_YML.write_text("image: scuba/hello")

        out, _ = run_scuba([])
        assert_str_equalish(out, "Hello world")

    def test_no_image_cmd(self) -> None:
        """Verify scuba gracefully handles an image with no Cmd and no user command"""
        SCUBA_YML.write_text("image: scuba/scratch")

        # ScubaError -> exit(128)
        out, _ = run_scuba([], expect_return=128)

    def test_handle_get_image_command_error(self) -> None:
        """Verify scuba handles a get_image_command error"""
        SCUBA_YML.write_text("image: {DOCKER_IMAGE}")

        def mocked_gic(image: str) -> Optional[Sequence[str]]:
            raise scuba.dockerutil.DockerError("mock error")

        # http://alexmarandon.com/articles/python_mock_gotchas/#patching-in-the-wrong-place
        # http://www.voidspace.org.uk/python/mock/patch.html#where-to-patch
        with mock.patch("scuba.scuba.get_image_command", side_effect=mocked_gic):
            # DockerError -> exit(128)
            run_scuba([], expect_return=128)

    def test_config_error(self) -> None:
        """Verify config errors are handled gracefully"""
        SCUBA_YML.write_text("invalid_key: is no good")

        # ConfigError -> exit(128)
        run_scuba([], expect_return=128)

    def test_multiline_alias_no_args_error(self) -> None:
        """Verify config errors from passing arguments to multi-line alias are caught"""
        SCUBA_YML.write_text(
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
        run_scuba(["multi", "with", "args"], expect_return=128)

    def test_version(self) -> None:
        """Verify scuba prints its version for -v"""

        out, err = run_scuba(["-v"])

        name, ver = out.split()
        assert name == "scuba"
        assert ver == scuba.__version__

    def test_no_docker(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify scuba gracefully handles docker not being installed"""
        SCUBA_YML.write_text(f"image: {DOCKER_IMAGE}")

        args = ["/bin/echo", "-n", "my output"]

        monkeypatch.setenv("PATH", "")
        _, err = run_scuba(args, expect_return=2)

    @mock.patch("subprocess.call")
    def test_dry_run(self, subproc_call_mock: mock.Mock) -> None:
        print(f"subproc_call_mock is a {type(subproc_call_mock)}")
        """Verify scuba handles --dry-run and --verbose"""
        SCUBA_YML.write_text(f"image: {DOCKER_IMAGE}")

        args = ["--dry-run", "--verbose", "/bin/false"]
        _, err = run_scuba(args)

        assert not subproc_call_mock.called

        # TODO: Assert temp files are not cleaned up?

    def test_args(self) -> None:
        """Verify scuba handles cmdline args"""
        SCUBA_YML.write_text(f"image: {DOCKER_IMAGE}")
        test_script = Path("test.sh")

        write_script(
            test_script,
            """\
            #!/bin/sh
            for a in "$@"; do echo $a; done
            """,
        )

        lines = ["here", "are", "some args"]

        out, _ = run_scuba([f"./{test_script}"] + lines)

        assert_seq_equal(out.splitlines(), lines)

    def test_created_file_ownership(self) -> None:
        """Verify files created under scuba have correct ownership"""
        SCUBA_YML.write_text(f"image: {DOCKER_IMAGE}")
        filename = "newfile.txt"

        run_scuba(["/bin/touch", filename])

        st = os.stat(filename)
        assert st.st_uid == os.getuid()
        assert st.st_gid == os.getgid()


class TestMainStdinStdout(MainTest):
    CHECK_TTY_SCRIPT = Path("check_tty.sh")

    def _setup_test_tty(self) -> None:
        assert sys.stdin.isatty()

        SCUBA_YML.write_text(f"image: {DOCKER_IMAGE}")

        write_script(
            self.CHECK_TTY_SCRIPT,
            """\
            #!/bin/sh
            if [ -t 1 ]; then echo "isatty"; else echo "notatty"; fi
            """,
        )

    @skipUnlessTty()
    def test_with_tty(self) -> None:
        """Verify docker allocates tty if stdout is a tty."""
        self._setup_test_tty()

        out, _ = run_scuba([f"./{self.CHECK_TTY_SCRIPT}"], mock_isatty=True)

        assert_str_equalish(out, "isatty")

    @skipUnlessTty()
    def test_without_tty(self) -> None:
        """Verify docker doesn't allocate tty if stdout is not a tty."""
        self._setup_test_tty()

        out, _ = run_scuba([f"./{self.CHECK_TTY_SCRIPT}"])

        assert_str_equalish(out, "notatty")

    def test_redirect_stdin(self) -> None:
        """Verify stdin redirection works"""
        SCUBA_YML.write_text(f"image: {DOCKER_IMAGE}")

        test_str = "hello world"
        with TemporaryFile(prefix="scubatest-stdin", mode="w+t") as stdin:
            stdin.write(test_str)
            stdin.seek(0)
            out, _ = run_scuba(["cat"], stdin=stdin)

        assert_str_equalish(out, test_str)


class TestMainUser(MainTest):
    def _test_user(
        self,
        expected_uid: int,
        expected_username: str,
        expected_gid: int,
        expected_groupname: str,
        scuba_args: List[str] = [],
    ) -> None:
        SCUBA_YML.write_text(f"image: {DOCKER_IMAGE}")

        args = scuba_args + [
            "/bin/sh",
            "-c",
            "echo $(id -u) $(id -un) $(id -g) $(id -gn)",
        ]
        out, _ = run_scuba(args)

        uid_str, username, gid_str, groupname = out.split()
        uid = int(uid_str)
        gid = int(gid_str)

        assert uid == expected_uid
        assert username == expected_username
        assert gid == expected_gid
        assert groupname == expected_groupname

    def _test_user_expect_root(self, scuba_args: List[str] = []) -> None:
        return self._test_user(
            expected_uid=0,
            expected_username="root",
            expected_gid=0,
            expected_groupname="root",
            scuba_args=scuba_args,
        )

    def test_user_scubauser(self) -> None:
        """Verify scuba runs container as the current (host) uid/gid"""
        self._test_user(
            expected_uid=os.getuid(),
            expected_username=getpwuid(os.getuid()).pw_name,
            expected_gid=os.getgid(),
            expected_groupname=getgrgid(os.getgid()).gr_name,
        )

    def test_user_root(self) -> None:
        """Verify scuba -r runs container as root"""
        self._test_user_expect_root(scuba_args=["-r"])

    def test_user_run_as_root(self) -> None:
        '''Verify running scuba as root is identical to "scuba -r"'''

        with mock.patch("os.getuid", return_value=0) as getuid_mock, mock.patch(
            "os.getgid", return_value=0
        ) as getgid_mock:
            self._test_user_expect_root()
            assert getuid_mock.called
            assert getgid_mock.called

    def test_user_root_alias(self) -> None:
        """Verify that aliases can set whether the container is run as root"""
        SCUBA_YML.write_text(
            f"""
            image: {DOCKER_IMAGE}
            aliases:
              root_test:
                root: true
                script:
                  - echo $(id -u) $(id -un) $(id -g) $(id -gn)
            """
        )

        out, _ = run_scuba(["root_test"])
        uid, username, gid, groupname = out.split()

        assert int(uid) == 0
        assert username == "root"
        assert int(gid) == 0
        assert groupname == "root"

        # No one should ever specify 'root: false' in an alias, but Scuba should behave
        # correctly if they do
        SCUBA_YML.write_text(
            f"""
            image: {DOCKER_IMAGE}
            aliases:
              no_root_test:
                root: false
                script:
                  - echo $(id -u) $(id -un) $(id -g) $(id -gn)
            """
        )

        out, _ = run_scuba(["no_root_test"])
        uid, username, gid, groupname = out.split()

        assert int(uid) == os.getuid()
        assert username == getpwuid(os.getuid()).pw_name
        assert int(gid) == os.getgid()
        assert groupname == getgrgid(os.getgid()).gr_name


class TestMainHomedir(MainTest):
    def _test_home_writable(self, scuba_args: List[str] = []) -> None:
        SCUBA_YML.write_text(f"image: {DOCKER_IMAGE}")

        args = scuba_args + [
            "/bin/sh",
            "-c",
            "echo success >> ~/testfile; cat ~/testfile",
        ]
        out, _ = run_scuba(args)

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


class TestMainDockerArgs(MainTest):
    def test_arbitrary_docker_args(self) -> None:
        """Verify -d successfully passes arbitrary docker arguments"""
        SCUBA_YML.write_text(f"image: {DOCKER_IMAGE}")

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
            out, _ = run_scuba(args)

        assert_str_equalish(out, data)

    def test_arbitrary_docker_args_merge_config(self) -> None:
        """Verify -d arguments are merged with docker_args in the config"""
        dummy = Path("dummy")
        dummy.touch()
        expfiles = set()
        tgtdir = "/tgtdir"

        def mount_dummy(name: str) -> str:
            assert name not in expfiles
            expfiles.add(name)
            return f'-v "{dummy.absolute()}:{tgtdir}/{name}"\n'

        SCUBA_YML.write_text(
            f"""
            image: {DOCKER_IMAGE}
            docker_args: {mount_dummy('one')}
            """
        )

        args = [
            "-d=" + mount_dummy("two"),
            "ls",
            tgtdir,
        ]
        out, _ = run_scuba(args)

        files = set(out.splitlines())
        assert files == expfiles


class TestMainAliasScripts(MainTest):
    def test_complex_commands_in_alias(self) -> None:
        """Verify complex commands can be used in alias scripts"""
        test_dir = Path("foo")
        test_file = test_dir / "bar.txt"
        test_string = "Hello world"

        test_dir.mkdir()
        test_file.write_text(test_string)

        SCUBA_YML.write_text(
            f"""
            image: {DOCKER_IMAGE}
            aliases:
              alias1:
                script:
                  - cd {test_dir} && cat {test_file.name}
            """
        )

        out, _ = run_scuba(["alias1"])
        assert_str_equalish(test_string, out)

    def test_nested_sript(self) -> None:
        """Verify nested scripts works"""
        SCUBA_YML.write_text(
            f"""
            image: {DOCKER_IMAGE}
            aliases:
              foo:
                script:
                  - echo "This"
                  - - echo "list"
                    - echo "is"
                    - echo "nested"
                    - - echo "kinda"
                      - echo "crazy"
            """
        )

        test_str = "This list is nested kinda crazy"
        out, _ = run_scuba(["foo"])

        out = out.replace("\n", " ")
        assert_str_equalish(out, test_str)


class TestMainEntrypoint(MainTest):
    def test_image_entrypoint(self) -> None:
        """Verify scuba doesn't interfere with the configured image ENTRYPOINT"""
        SCUBA_YML.write_text("image: scuba/entrypoint-test")

        out, _ = run_scuba(["cat", "entrypoint_works.txt"])
        assert_str_equalish("success", out)

    def test_image_entrypoint_multiline(self) -> None:
        """Verify entrypoints are handled correctly with multi-line scripts"""
        SCUBA_YML.write_text(
            """
            image: scuba/entrypoint-test
            aliases:
              testalias:
                script:
                  - cat entrypoint_works.txt
                  - echo $ENTRYPOINT_WORKS
            """
        )

        out, _ = run_scuba(["testalias"])
        assert_str_equalish("\n".join(["success"] * 2), out)

    def test_entrypoint_override(self) -> None:
        """Verify --entrypoint override works"""
        SCUBA_YML.write_text(
            """
            image: scuba/entrypoint-test
            aliases:
              testalias:
                script:
                  - echo $ENTRYPOINT_WORKS
            """
        )

        test_script = Path("new.sh")
        test_str = "This is output from the overridden entrypoint"

        write_script(
            test_script,
            f"""\
            #!/bin/sh
            echo "{test_str}"
            """,
        )

        args = [
            "--entrypoint",
            str(test_script.absolute()),
            "true",
        ]
        out, _ = run_scuba(args)
        assert_str_equalish(test_str, out)

    def test_entrypoint_override_none(self) -> None:
        """Verify --entrypoint override (to nothing) works"""
        SCUBA_YML.write_text(
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
        out, _ = run_scuba(args)

        # Verify that ENTRYPOINT_WORKS was not set by the entrypoint
        # (because it didn't run)
        assert_str_equalish("", out)

    def test_yaml_entrypoint_override(self) -> None:
        """Verify entrypoint in .scuba.yml works"""
        test_script = Path("new.sh")
        test_str = "This is output from the overridden entrypoint"

        write_script(
            test_script,
            f"""\
            #!/bin/sh
            echo "{test_str}"
            """,
        )

        SCUBA_YML.write_text(
            f"""
            image: scuba/entrypoint-test
            entrypoint: "./{test_script}"
            """
        )

        out, _ = run_scuba(["true"])
        assert_str_equalish(test_str, out)

    def test_yaml_entrypoint_override_none(self) -> None:
        """Verify "none" entrypoint in .scuba.yml works"""
        SCUBA_YML.write_text(
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
        out, _ = run_scuba(args)

        # Verify that ENTRYPOINT_WORKS was not set by the entrypoint
        # (because it didn't run)
        assert_str_equalish("", out)


class TestMainImageOverride(MainTest):
    def test_image_override(self) -> None:
        """Verify --image works"""
        SCUBA_YML.write_text(
            # This image does not exist
            "image: scuba/notheredoesnotexistbb7e344f9722"
        )

        args = [
            "--image",
            DOCKER_IMAGE,
            "echo",
            "success",
        ]
        out, _ = run_scuba(args)
        assert_str_equalish("success", out)

    def test_image_override_with_alias(self) -> None:
        """Verify --image works with aliases"""
        SCUBA_YML.write_text(
            # These images do not exist
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
        out, _ = run_scuba(args)
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
        out, _ = run_scuba(args)
        assert_str_equalish("success", out)


class TestMainHooks(MainTest):
    def _test_one_hook(
        self,
        hookname: str,
        hookcmd: str,
        cmd: str,
        expect_return: int = 0,
    ) -> ScubaResult:
        SCUBA_YML.write_text(
            f"""
            image: {DOCKER_IMAGE}
            hooks:
              {hookname}: {hookcmd}
            """
        )

        args = ["/bin/sh", "-c", cmd]
        return run_scuba(args, expect_return=expect_return)

    def _test_hook_runs_as(self, hookname: str, exp_uid: int, exp_gid: int) -> None:
        out, _ = self._test_one_hook(
            hookname=hookname,
            hookcmd="echo $(id -u) $(id -g)",
            cmd="echo success",
        )
        out_lines = out.splitlines()

        uid, gid = map(int, out_lines[0].split())
        assert exp_uid == uid
        assert exp_gid == gid

        assert_str_equalish(out_lines[1], "success")

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
            expect_return=SCUBAINIT_EXIT_FAIL,
        )
        assert re.match(f"^scubainit: .* exited with status {testval}$", err)


class TestMainEnvironment(MainTest):
    def test_env_var_keyval(self) -> None:
        """Verify -e KEY=VAL works"""
        SCUBA_YML.write_text(f"image: {DOCKER_IMAGE}")
        args = [
            "-e",
            "KEY=VAL",
            "/bin/sh",
            "-c",
            "echo $KEY",
        ]
        out, _ = run_scuba(args)
        assert_str_equalish(out, "VAL")

    def test_env_var_key_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify -e KEY works"""
        SCUBA_YML.write_text(f"image: {DOCKER_IMAGE}")
        args = [
            "-e",
            "KEY",
            "/bin/sh",
            "-c",
            "echo $KEY",
        ]
        monkeypatch.setenv("KEY", "mockedvalue")
        out, _ = run_scuba(args)
        assert_str_equalish(out, "mockedvalue")

    def test_env_var_sources(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify scuba handles all possible environment variable sources"""
        SCUBA_YML.write_text(
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

        out, _ = run_scuba(args)

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

    def test_builtin_env__SCUBA_ROOT(self, in_tmp_path: Path) -> None:
        """Verify SCUBA_ROOT is set in container"""
        SCUBA_YML.write_text(f"image: {DOCKER_IMAGE}")

        args = ["/bin/sh", "-c", "echo $SCUBA_ROOT"]
        out, _ = run_scuba(args)

        assert_str_equalish(in_tmp_path, out)


class TestMainShellOverride(MainTest):
    def test_use_top_level_shell_override(self) -> None:
        """Verify that the shell can be overriden at the top level"""
        SCUBA_YML.write_text(
            f"""
            image: {DOCKER_IMAGE}
            shell: /bin/bash
            aliases:
              check_shell:
                script: readlink -f /proc/$$/exe
            """
        )

        out, _ = run_scuba(["check_shell"])
        # If we failed to override, the shebang would be #!/bin/sh
        assert_str_equalish("/bin/bash", out)

    def test_alias_level_shell_override(self) -> None:
        """Verify that the shell can be overriden at the alias level without affecting other aliases"""
        SCUBA_YML.write_text(
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
        out, _ = run_scuba(["shell_override"])
        assert_str_equalish("/bin/bash", out)

        out, _ = run_scuba(["default_shell"])
        # The way that we check the shell uses the resolved symlink of /bin/sh,
        # which is /bin/dash on Debian
        assert out.strip() in ["/bin/sh", "/bin/dash"]

    def test_cli_shell_override(self) -> None:
        """Verify that the shell can be overriden by the CLI"""
        SCUBA_YML.write_text(
            f"""
            image: {DOCKER_IMAGE}
            aliases:
              default_shell:
                script: readlink -f /proc/$$/exe
            """
        )
        out, _ = run_scuba(["--shell", "/bin/bash", "default_shell"])
        assert_str_equalish("/bin/bash", out)

    def test_shell_override_precedence(self) -> None:
        """Verify that shell overrides at different levels override each other as expected"""
        # Precedence expectations are (with "<<" meaning "overridden by"):
        # Top-level SCUBA_YML shell << alias-level SCUBA_YML shell << CLI-specified shell

        # Test top-level << alias-level
        SCUBA_YML.write_text(
            f"""
            image: {DOCKER_IMAGE}
            shell: /bin/this_does_not_exist
            aliases:
              shell_override:
                shell: /bin/bash
                script: readlink -f /proc/$$/exe
            """
        )
        out, _ = run_scuba(["shell_override"])
        assert_str_equalish("/bin/bash", out)

        # Test alias-level << CLI
        SCUBA_YML.write_text(
            f"""
            image: {DOCKER_IMAGE}
            aliases:
              shell_overridden:
                shell: /bin/this_is_not_a_real_shell
                script: readlink -f /proc/$$/exe
            """
        )
        out, _ = run_scuba(["--shell", "/bin/bash", "shell_overridden"])
        assert_str_equalish("/bin/bash", out)

        # Test top-level << CLI
        SCUBA_YML.write_text(
            f"""
            image: {DOCKER_IMAGE}
            shell: /bin/this_is_not_a_real_shell
            aliases:
              shell_check: readlink -f /proc/$$/exe
            """
        )
        out, _ = run_scuba(["--shell", "/bin/bash", "shell_check"])
        assert_str_equalish("/bin/bash", out)


class TestMainVolumes(MainTest):
    def test_volumes_basic(self) -> None:
        """Verify volumes can be added at top-level and alias"""

        # Create some temporary directories with a file in each
        topdata = Path("./topdata")
        topdata.mkdir()
        (topdata / "thing").write_text("from the top\n")

        aliasdata = Path("./aliasdata")
        aliasdata.mkdir()
        (aliasdata / "thing").write_text("from the alias\n")

        SCUBA_YML.write_text(
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

        out, _ = run_scuba(["doit"])
        assert out.splitlines() == ["from the top", "from the alias"]

    def test_volumes_alias_override(self) -> None:
        """Verify volumes can be overridden by an alias"""

        # Create some temporary directories with a file in each
        topdata = Path("./topdata")
        topdata.mkdir()
        (topdata / "thing").write_text("from the top\n")

        aliasdata = Path("./aliasdata")
        aliasdata.mkdir()
        (aliasdata / "thing").write_text("from the alias\n")

        SCUBA_YML.write_text(
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
        out, _ = run_scuba(["cat", "/data/thing"])
        assert out.splitlines() == ["from the top"]

        # Run the alias
        out, _ = run_scuba(["doit"])
        assert out.splitlines() == ["from the alias"]

    def test_volumes_host_path_create(self) -> None:
        """Missing host paths should be created before starting Docker"""

        userdir = Path("./user")
        testfile = userdir / "test.txt"

        SCUBA_YML.write_text(
            f"""
            image: {DOCKER_IMAGE}
            volumes:
              /userdir: {userdir.absolute()}
            """
        )

        run_scuba(["touch", "/userdir/test.txt"])

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

        SCUBA_YML.write_text(
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
            run_scuba(["doit"])
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

        SCUBA_YML.write_text(
            f"""
            image: {DOCKER_IMAGE}
            volumes:
              /userdir: {userdir.absolute()}
            """
        )

        run_scuba(["touch", "/userdir/test.txt"], expect_return=128)

    def test_volumes_host_path_rel(self) -> None:
        """Volume host paths can be relative"""

        # Set up a subdir with a file to be read.
        userdir = Path("./user")
        userdir.mkdir(parents=True)

        test_message = "Relative paths work"
        (userdir / "test.txt").write_text(test_message)

        SCUBA_YML.write_text(
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

        out, _ = run_scuba(["cat", "/userdir/test.txt"])
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
        SCUBA_YML.write_text(
            f"""
            image: {DOCKER_IMAGE}
            volumes:
              /userdir: ../../../{userdir}
            """
        )

        out, _ = run_scuba(["cat", "/userdir/test.txt"])
        assert out == test_message


class TestMainNamedVolumes(MainTest):
    VOLUME_NAME = "foo-volume"

    def _rm_volume(self) -> None:
        result = subprocess.run(
            ["docker", "volume", "rm", self.VOLUME_NAME],
            capture_output=True,
            text=True,
        )
        if result.returncode == 1 and re.match(r".*no such volume.*", result.stderr):
            return
        result.check_returncode()

    def setup_method(self) -> None:
        self._rm_volume()

    def teardown_method(self) -> None:
        self._rm_volume()

    def test_volumes_named(self) -> None:
        """Verify named volumes can be used"""
        vol_path = Path("/foo")
        test_path = vol_path / "test.txt"
        test_str = "it works!"

        SCUBA_YML.write_text(
            f"""
            image: {DOCKER_IMAGE}
            hooks:
              root: chmod 777 {vol_path}
            volumes:
              {vol_path}: {self.VOLUME_NAME}
            """
        )

        # Inoke scuba once: Write a file to the named volume
        run_scuba(["/bin/sh", "-c", f"echo {test_str} > {test_path}"])

        # Invoke scuba again: Verify the file is still there
        out, _ = run_scuba(["/bin/sh", "-c", f"cat {test_path}"])
        assert_str_equalish(out, test_str)
