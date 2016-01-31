#!/usr/bin/env python
import scuba.version
from setuptools import setup

setup(
    name = 'SCUBA',
    version = scuba.version.__version__,
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
