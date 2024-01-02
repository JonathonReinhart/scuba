import scuba.version
from setuptools import setup, Command
from distutils.command.build import build
from setuptools.command.develop import develop
from subprocess import check_call
import os

################################################################################
# Build Hooks


class build_scubainit(Command):
    description = "Build scubainit binary"

    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        check_call(["make"])


class build_hook(build):
    def run(self):
        self.run_command("build_scubainit")
        super().run()


class develop(develop):
    def run(self):
        self.run_command("build_scubainit")
        super().run()


################################################################################
# Dynamic versioning


def get_version():
    # CI builds
    # If CI_VERSION_BUILD_NUMBER is set, append that to the base version
    build_num = os.getenv("CI_VERSION_BUILD_NUMBER")
    if build_num:
        return f"{scuba.version.BASE_VERSION}.{build_num}"

    # Otherwise, use the auto-versioning
    return scuba.version.__version__


################################################################################

setup(
    #####
    # Dynamic core metadata, in addition to pyproject.toml [project]
    version=get_version(),
    #####
    # Setuptools-specific config
    # We could put this in pyproject.toml [tool.setuptools], but choose not to:
    # - The functionality is still in beta and requires setuptools >= 61.0.0
    # - We need setup.py to provide build_hook, so we might as well keep all
    #   setuptools-specific config here, in one file.
    packages=["scuba"],
    package_data={
        "scuba": [
            "scubainit",
        ],
    },
    include_package_data=True,  # https://github.com/pypa/setuptools/issues/1064
    zip_safe=False,  # http://stackoverflow.com/q/24642788/119527
    # http://stackoverflow.com/questions/17806485
    # http://stackoverflow.com/questions/21915469
    cmdclass={
        "build_scubainit": build_scubainit,
        "build": build_hook,
        "develop": develop,
    },
)
