#!/usr/bin/env python

from distutils.core import setup

setup(
    name = 'SCUBA',
    version = '1.4.0',
    description = 'Simplify use of Docker containers for building software',
    author = 'Jonathon Reinhart',
    author_email = 'jonathon.reinhart@gmail.com',
    url = 'https://github.com/JonathonReinhart/scuba',
    packages = ['scuba'],
    entry_points = {
        'console_scripts': [
            'scuba = scuba.__main__:main',
        ]
    },
    install_requires = [
        'PyYAML',
    ],
)
