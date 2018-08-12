#!/usr/bin/env python
from __future__ import print_function
import scuba.version
from setuptools import setup, Command
from distutils.command.build import build
from setuptools.command.sdist import sdist 
from subprocess import check_call
import os


class build_scubainit(Command):
    description = 'Build scubainit binary'

    user_options=[]
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass

    def run(self):
        check_call(['make'])


class build_hook(build):
    def run(self):
        self.run_command('build_scubainit')
        build.run(self)

def read_project_file(path):
    proj_dir = os.path.dirname(__file__)
    path = os.path.join(proj_dir, 'README.md')
    with open(path, 'r') as f:
        return f.read()

setup(
    name = 'scuba',
    version = scuba.version.__version__,
    description = 'Simplify use of Docker containers for building software',
    long_description = read_project_file('README.md'),
    classifiers = [
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Operating System :: MacOS :: MacOS X',
        'Topic :: Software Development :: Build Tools',
    ],
    license = 'MIT',
    keywords = 'docker',
    author = 'Jonathon Reinhart',
    author_email = 'jonathon.reinhart@gmail.com',
    url = 'https://github.com/JonathonReinhart/scuba',
    packages = ['scuba'],
    package_data = {
        'scuba': [
            'scubainit',
        ],
    },
    include_package_data = True,    # https://github.com/pypa/setuptools/issues/1064
    zip_safe = False,   # http://stackoverflow.com/q/24642788/119527
    entry_points = {
        'console_scripts': [
            'scuba = scuba.__main__:main',
        ]
    },
    install_requires = [
        'PyYAML',
    ],

    # http://stackoverflow.com/questions/17806485
    # http://stackoverflow.com/questions/21915469
    cmdclass = {
        'build_scubainit':  build_scubainit,
        'build':            build_hook,
    },
)
