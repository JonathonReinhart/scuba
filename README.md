SCUBA  [![Build Status](https://travis-ci.org/JonathonReinhart/scuba.svg?branch=master)](https://travis-ci.org/JonathonReinhart/scuba) [![codecov.io](https://codecov.io/github/JonathonReinhart/scuba/coverage.svg?branch=master)](https://codecov.io/github/JonathonReinhart/scuba?branch=master) [![PyPI](https://img.shields.io/pypi/v/scuba.svg)](https://pypi.python.org/pypi/scuba)
-----

Simple Container-Utilizing Build Apparatus

SCUBA is a simple tool that makes it easier to use Docker containers in everyday development.
It is intended to be used by developers in 'make' or 'scons' based build environments, where
the entire build environment is encapsulated in a Docker container.

Its purpose is to lower the barrier to using Docker for everyday builds. SCUBA keeps you from
having to remember a complex `docker run` command line, and turns this

    $ docker run -it --rm -v $(pwd):/build:z -w /build -u $(id -u):$(id -g) gcc:5.1 make myprogram

into this:

    $ scuba make myprogram

## Installation

### Install via pip
Scuba is [hosted at PyPI](https://pypi.python.org/pypi/scuba).

To install:

    $ sudo pip install scuba

To uninstall:

    $ sudo pip uninstall scuba

### Install from source
Scuba can be built from source on Linux only (due to the fact that `scubainit`
must be compiled):

1. Run `make` to build `scubainit`
2. Run `./run_nosetests.sh` to run the unit tests
3. Run `sudo python setup.py install` to install scuba
4. Run `./run_full_tests.py` to test the installed version of scuba

If [musl-libc] is installed, it can be used to reduce the size of `scubainit`,
by overriding the `CC` environment variable in step 1:

`CC=/usr/local/musl/bin/musl-gcc make`


## Configuration

Configuration is done using a [YAML](http://yaml.org/) file named `.scuba.yml` in the root
directory of your project. It is expected that `.scuba.yml` be checked in to version control.

Required nodes:

- `image` - The Docker image to run

Optional nodes:

- `aliases` - A dictionary of bash-like aliases
- `hooks` - "Hooks" that run as part of `scubainit` before running the user command

An example `.scuba.yml` file might look like this:

```yaml
image: gcc:5.1

aliases:
  build: make -j4


# These hooks run during scubainit
hooks:

  # The "root" hook runs just before we switch users
  root:
    # This uses the complex form, with a 'script' subkey,
    # which is a list of command strings making up the script.
    script:
      - 'echo "HOOK: This runs before we switch users"'
      - id

  # The "user" hook runs just before we execute the user command.
  # This uses the simple form, which is just a single command string.
  user: 'echo "HOOK: After switching users, uid=$(id -u) gid=$(id -g)"'
```

This tells SCUBA:
- Use the `gcc:5.1` Docker image
- `build` is an alias for `make -j4`.

In this example, `scuba build foo` would execute `make -j4 foo` in a `gcc:5.1` container.
Prior to running `make`, the hooks would execute, echoing messages about the user ID.

### Extended syntax
In addition to normal YAML syntax, an additional constructor, `!from_yaml`, is available for `.scuba.yml` which allows a key to be retrieved from an external YAML file. Is has the following syntax:
```yaml
!from_yaml filename key
```
where `filename` is the path of an external YAML file, and `key` is a dot-separated locator of the key to retrieve.

This is useful for projects where a Docker image in which to build is already specified in another YAML file, for example in [`.gitlab-ci.yml`](http://doc.gitlab.com/ce/ci/yaml/README.html). This eliminates the redundancy between the configuration files. An example which uses this:

**`.gitlab-ci.yml`**
```yaml
image: gcc:5.1
# ...
```

**`.scuba.yml`**
```yaml
image: !from_yaml .gitlab-ci.yml image
```


## License

This software is released under the [MIT License](https://opensource.org/licenses/MIT).




[musl-libc]: https://www.musl-libc.org/
