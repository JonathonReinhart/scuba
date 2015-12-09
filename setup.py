#!/usr/bin/env python

from distutils.core import setup

setup(name='SCUBA',
      version='0.1',
      description='Simplify use of Docker containers for building software',
      author='Jonathon Reinhart',
      author_email='jonathon.reinhart@gmail.com',
      url='https://github.com/JonathonReinhart/scuba',
      scripts=['src/scuba'],
      install_requires=[
          'PyYAML',
      ],
     )
