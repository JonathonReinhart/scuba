#!/usr/bin/env python
from __future__ import print_function
import scuba.version
from setuptools import setup
from setuptools.command.build_py import build_py
import os.path
from subprocess import check_call

class BuildHook(build_py):
    def run(self):
        print('Building scubainit...')
        check_call(['make'])
        build_py.run(self)


setup(
    name = 'scuba',
    version = scuba.version.__version__,
    description = 'Simplify use of Docker containers for building software',
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
    data_files = [
        ('/etc/bash_completion.d', ['bash_completion/scuba']),
    ],
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
        'build_py': BuildHook,
    },
)
