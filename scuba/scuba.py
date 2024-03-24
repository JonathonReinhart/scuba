from __future__ import annotations
import copy
import dataclasses
import os
import pprint
import shutil
import sys
import tempfile
from grp import getgrgid
from pathlib import Path
from pwd import getpwuid
from typing import cast, Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union
from typing import TextIO

from .config import ScubaConfig, OverrideMixin
from .config import ConfigError, ScubaVolume
from .dockerutil import get_image_command
from .dockerutil import get_image_entrypoint
from .dockerutil import make_vol_opt
from .utils import shell_quote_cmd, flatten_list, get_umask, writeln

VolumeTuple = Tuple[Path, Path, List[str]]


class ScubaError(Exception):
    pass


class ScubaDive:
    context: ScubaContext
    env_vars: Dict[str, str]
    volumes: List[VolumeTuple]
    options: List[str]
    docker_args: List[str]

    docker_cmd: List[str]

    def __init__(
        self,
        user_command: List[str],
        config: ScubaConfig,
        top_path: Path,
        top_rel: Path,
        docker_args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        as_root: bool = False,
        verbose: bool = False,
        image_override: Optional[str] = None,
        entrypoint: Optional[str] = None,
        shell_override: Optional[str] = None,
        keep_tempfiles: bool = False,
    ):
        self.as_root = as_root
        self.verbose = verbose
        self.entrypoint_override = entrypoint
        self.keep_tempfiles = keep_tempfiles

        # These will be added to docker run cmdline
        self.env_vars = env or {}
        self.volumes = []
        self.options = []
        self.docker_args = docker_args or []
        self.workdir: Optional[Path] = None

        self.__scubadir_hostpath: Optional[str] = None
        self.__scubadir_contpath: Optional[str] = None
        self.config = config

        # Mount scuba root directory at the same path in the container...
        self.add_volume(top_path, top_path)

        # ...and set the working dir relative to it
        self.set_workdir(top_path / top_rel)

        self.add_env("SCUBA_ROOT", str(top_path))

        try:
            # Process any aliases
            self.context = ScubaContext.process_command(
                cfg=self.config,
                command=user_command,
                image_override=image_override,
                shell_override=shell_override,
            )

            # Apply environment vars from .scuba.yml
            self.env_vars.update(self.context.environment)

            self.__make_scubadir()

            if self.is_remote_docker:
                """
                Docker is running remotely (e.g. boot2docker on OSX).
                We don't need to do any user setup whatsoever.

                TODO: For now, remote instances won't have any .scubainit

                See:
                https://github.com/JonathonReinhart/scuba/issues/17
                """
                raise ScubaError("Remote docker not supported (DOCKER_HOST is set)")

            # Docker is running natively
            self.__setup_native_run()
        except:
            self._cleanup()
            raise

    def __enter__(self) -> ScubaDive:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self._cleanup()

    def _cleanup(self) -> None:
        if self.__scubadir_hostpath and not self.keep_tempfiles:
            shutil.rmtree(self.__scubadir_hostpath)

    def __str__(self) -> str:
        data = dict(
            verbose=self.verbose,
            as_root=self.as_root,
            workdir=str(self.workdir),
            options=self.options,
            docker_args=self.docker_args,
            env_vars=self.env_vars,
            volumes=[f"{hp} => {cp} {opt}" for hp, cp, opt in self.__get_vol_opts()],
            context=dataclasses.asdict(self.context),
        )
        # TODO(#242) Use sort_dicts=False in Python >= 3.8
        return "ScubaDive\n" + pprint.pformat(data, width=100)

    @property
    def is_remote_docker(self) -> bool:
        return "DOCKER_HOST" in os.environ

    def add_env(self, name: str, val: Union[str, int]) -> None:
        """Add an environment variable to the docker run invocation"""
        if name in self.env_vars:
            raise KeyError(name)
        self.env_vars[name] = str(val)

    def add_volume(
        self,
        hostpath: Union[Path, str],
        contpath: Union[Path, str],
        options: Optional[List[str]] = None,
    ) -> None:
        """Add a volume (bind-mount) to the docker run invocation"""
        hostpath = Path(hostpath)
        contpath = Path(contpath)
        if options is None:
            options = []
        self.volumes.append((hostpath, contpath, options))

    def try_create_volumes(self) -> None:
        """Try to create non-existent host paths prior to docker run invocation

        This only creates user-defined volumes from configuration. The scubadir
        and the initial working directory either exist or are created as root by
        Docker.
        """
        # Cannot create local directories for a remote host
        if self.is_remote_docker:
            return

        for vol in self.context.volumes.values():
            if vol.host_path is None or vol.host_path.exists():
                continue

            try:
                # Create directories all the way to the target
                os.makedirs(vol.host_path, exist_ok=True)
            except PermissionError:
                # Docker will create this path later as root
                pass
            except OSError as err:
                raise ScubaError(f"Error creating volume host path: {err}") from err

    def add_option(self, option: str) -> None:
        """Add another option to the docker run invocation"""
        self.options.append(option)

    def set_workdir(self, workdir: Path) -> None:
        self.workdir = workdir

    def __locate_scubainit(self) -> str:
        """Determine path to scubainit binary"""
        pkg_path = os.path.dirname(__file__)

        scubainit_path = os.path.join(pkg_path, "scubainit")
        if not os.path.isfile(scubainit_path):
            raise ScubaError(f"scubainit not found at {scubainit_path!r}")
        return scubainit_path

    def __make_scubadir(self) -> None:
        """Make temp directory where all ancillary files are bind-mounted"""
        self.__scubadir_hostpath = tempfile.mkdtemp(prefix="scubadir")
        self.__scubadir_contpath = "/.scuba"
        self.add_volume(self.__scubadir_hostpath, self.__scubadir_contpath)

    def __setup_native_run(self) -> None:
        # These options are appended to mounted volume arguments
        # NOTE: This tells Docker to re-label the directory for compatibility
        # with SELinux. See `man docker-run` for more information.
        self.vol_opts = ["z"]

        # Pass variables to scubainit
        self.add_env("SCUBAINIT_UMASK", f"{get_umask():04o}")

        # Check if the CLI args specify "run as root", or if the command (alias) does
        if not self.as_root and not self.context.as_root:
            uid = os.getuid()
            gid = os.getgid()
            self.add_env("SCUBAINIT_UID", uid)
            self.add_env("SCUBAINIT_GID", gid)
            self.add_env("SCUBAINIT_USER", getpwuid(uid).pw_name)
            self.add_env("SCUBAINIT_GROUP", getgrgid(gid).gr_name)

        if self.verbose:
            self.add_env("SCUBAINIT_VERBOSE", 1)

        # Copy scubainit into the container
        # We make a copy because Docker 1.13 gets pissed if we try to re-label
        # /usr, and Fedora 28 gives an AVC denial.
        scubainit_cpath = self.copy_scubadir_file(
            "scubainit", self.__locate_scubainit()
        )

        # Hooks
        for name in (
            "root",
            "user",
        ):
            self.__generate_hook_script(name, self.context.shell)

        # allocate TTY if scuba's output is going to a terminal
        # and stdin is not redirected
        if sys.stdout.isatty() and sys.stdin.isatty():
            self.add_option("--tty")

        """
        Normally, if the user provides no command to "docker run", the image's
        default CMD is run. Because we set the entrypiont, scuba must emulate the
        default behavior itself.
        """
        if not self.context.script:
            # No user-provided command; we want to run the image's default command
            default_cmd = get_image_command(self.context.image)
            if not default_cmd:
                raise ScubaError("No command given and no image-specified command")
            self.context.script = [shell_quote_cmd(default_cmd)]

        # Make scubainit the real entrypoint, and use the defined entrypoint as
        # the docker command (if it exists)
        self.add_option(f"--entrypoint={scubainit_cpath}")

        self.docker_cmd = []
        if self.entrypoint_override is not None:
            # --entrypoint takes precedence
            if self.entrypoint_override != "":
                self.docker_cmd = [self.entrypoint_override]
        elif self.context.entrypoint is not None:
            # then .scuba.yml
            if self.context.entrypoint != "":
                self.docker_cmd = [self.context.entrypoint]
        else:
            ep = get_image_entrypoint(self.context.image)
            if ep:
                self.docker_cmd = list(ep)

        # The user command is executed via a generated shell script
        with self.open_scubadir_file("command.sh") as cmd_script:
            self.docker_cmd += [self.context.shell, cmd_script.container_path]
            writeln(cmd_script, "# Auto-generated from scuba")
            writeln(cmd_script, "set -e")
            for cmd in self.context.script:
                writeln(cmd_script, cmd)

    def open_scubadir_file(self, name: str) -> Any:
        """Opens a text file in the 'scubadir' for writing

        This file will automatically be bind-mounted into the container,
        at a path given by the 'container_path' property on the returned file object.
        """
        assert self.__scubadir_hostpath is not None
        assert self.__scubadir_contpath is not None

        path = os.path.join(self.__scubadir_hostpath, name)
        assert not os.path.exists(path)

        # Make any directories required
        os.makedirs(os.path.dirname(path), exist_ok=True)

        # TODO: How to represent TextIO plus container_path attribute?
        # Deriving from TextIO seemed to do nothing.
        f: Any = open(path, "w")
        f.container_path = os.path.join(self.__scubadir_contpath, name)

        return f

    def copy_scubadir_file(self, name: str, source: str) -> str:
        """Copies source into the scubadir

        Returns the container-path of the copied file
        """
        assert self.__scubadir_hostpath is not None
        assert self.__scubadir_contpath is not None

        dest = os.path.join(self.__scubadir_hostpath, name)
        assert not os.path.exists(dest)
        shutil.copy2(source, dest)

        return os.path.join(self.__scubadir_contpath, name)

    def __generate_hook_script(self, name: str, shell: str) -> None:
        script = self.config.hooks.get(name)
        if not script:
            return

        # Generate the hook script, mount it into the container, and tell scubainit
        with self.open_scubadir_file(f"hooks/{name}.sh") as f:
            self.add_env(f"SCUBAINIT_HOOK_{name.upper()}", f.container_path)

            writeln(f, f"#!{shell}")
            writeln(f, "# Auto-generated from .scuba.yml")
            writeln(f, "set -e")
            for cmd in script:
                writeln(f, cmd)

    def __get_vol_opts(self) -> Iterable[VolumeTuple]:
        for hostpath, contpath, options in self.volumes:
            yield hostpath, contpath, options + self.vol_opts

    def get_docker_cmdline(self) -> Sequence[str]:
        args = [
            "docker",
            "run",
            # interactive: keep STDIN open
            "-i",
            # remove container after exit
            "--rm",
        ]

        for name, val in self.env_vars.items():
            args.append(f"--env={name}={val}")

        for hostpath, contpath, options in self.__get_vol_opts():
            args.append(make_vol_opt(hostpath, contpath, options))

        for _, vol in self.context.volumes.items():
            args.append(vol.get_vol_opt())

        if self.workdir:
            args += ["-w", str(self.workdir)]

        args += self.options

        # .scuba.yml (top-level or alias)
        if self.context.docker_args is not None:
            args += self.context.docker_args

        # Command-line -d
        if self.docker_args:
            args += self.docker_args

        # Docker image
        args.append(self.context.image)

        # Command to run in container
        args += self.docker_cmd

        return args


@dataclasses.dataclass
class ScubaContext:
    image: str
    environment: Dict[str, str]  # key: value
    volumes: Dict[Path, ScubaVolume]
    shell: str
    docker_args: List[str]
    script: Optional[List[str]] = None  # TODO: drop Optional?
    entrypoint: Optional[str] = None
    as_root: bool = False

    @classmethod
    def process_command(
        cls,
        cfg: ScubaConfig,
        command: Sequence[str],
        image_override: Optional[str] = None,
        shell_override: Optional[str] = None,
    ) -> ScubaContext:
        """Processes a user command using aliases

        Arguments:
            cfg         ScubaConfig object
            command     A user command list (e.g. argv)
            image_override       Override the image from .scuba.yml
            shell_override       Override the shell from .scuba.yml

        Returns: A ScubaContext object
        """

        image = None
        shell = None
        script = None
        entrypoint = cfg.entrypoint
        environment = copy.copy(cfg.environment)
        docker_args = copy.copy(cfg.docker_args) or []
        volumes: Dict[Path, ScubaVolume] = copy.copy(cfg.volumes or {})
        as_root = False

        if command:
            alias = cfg.aliases.get(command[0])
            if not alias:
                # Command is not an alias; use it as-is.
                script = [shell_quote_cmd(command)]
            else:
                # Using an alias
                # Does this alias override the image and/or entrypoint?
                if alias.image:
                    image = alias.image
                if alias.entrypoint is not None:
                    entrypoint = alias.entrypoint
                if alias.shell is not None:
                    shell = alias.shell
                if alias.as_root:
                    as_root = True

                if isinstance(alias.docker_args, OverrideMixin) or docker_args is None:
                    docker_args = cast(List[str], alias.docker_args)
                elif alias.docker_args is not None:
                    docker_args.extend(alias.docker_args)

                if alias.volumes is not None:
                    volumes.update(alias.volumes)

                # Merge/override the environment
                if alias.environment:
                    environment.update(alias.environment)

                if len(alias.script) > 1:
                    # Alias is a multiline script; no additional
                    # arguments are allowed in the scuba invocation.
                    if len(command) > 1:
                        raise ConfigError(
                            "Additional arguments not allowed with multi-line aliases"
                        )
                    script = alias.script

                else:
                    # Alias is a single-line script; perform substituion
                    # and add user arguments.
                    script = [alias.script[0] + " " + shell_quote_cmd(command[1:])]

            script = flatten_list(script)

        # If a shell was given on the CLI, it should override the shell set by
        # the alias or top-level config
        if shell_override:
            shell = shell_override

        # If an image was given, it overrides what might have been set by an alias
        if image_override:
            image = image_override

        # If the image was still not set, then try to get it from the confg,
        # which will raise a ConfigError if it is not set
        if image is None:
            image = cfg.image

        if shell is None:
            shell = cfg.shell

        return cls(
            image=image,
            script=script,
            entrypoint=entrypoint,
            environment=environment,
            shell=shell,
            docker_args=docker_args,
            volumes=volumes,
            as_root=as_root,
        )
