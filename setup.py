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
    path = os.path.join(proj_dir, path)
    with open(path, 'r') as f:
        return f.read()

################################################################################
# Dynamic versioning

def get_version():
    # CI builds
    # If CI_VERSION_BUILD_NUMBER is set, append that to the base version
    build_num = os.getenv('CI_VERSION_BUILD_NUMBER')
    if build_num:
        return '{}.{}'.format(scuba.version.BASE_VERSION, build_num)

    # Otherwise, use the auto-versioning
    return scuba.version.__version__

################################################################################

setup(
    name = 'scuba',
    version = get_version(),
    python_requires='>=3.5',
    description = 'Simplify use of Docker containers for building software',
    long_description = read_project_file('README.md'),
    long_description_content_type = 'text/markdown',
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
    extras_require = {
        'argcomplete': [
            'argcomplete>=1.10.1',
        ],
    },

    # http://stackoverflow.com/questions/17806485
    # http://stackoverflow.com/questions/21915469
    cmdclass = {
        'build_scubainit':  build_scubainit,
        'build':            build_hook,
    },
)
