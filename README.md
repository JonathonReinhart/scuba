SCUBA
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

To install:

    $ sudo pip install .

To uninstall:

    $ sudo pip uninstall scuba

## Configuration

Configuration is done using a [YAML](http://yaml.org/) file named `.scuba.yml` in the root
directory of your project. It is expected that `.scuba.yml` be checked in to version control.

Required nodes:

- `image` - The Docker image to run

Optional nodes:

- `aliases` - A dictionary of bash-like aliases

An example `.scuba.yml` file might look like this:

```yaml
image: gcc:5.1
aliases:
  build: make -j4
```

This tells SCUBA:
- Use the `gcc:5.1` Docker image
- `build` is an alias for `make -j4`.
In this example, `scuba build foo` would execute `make -j4 foo` in a `gcc:5.1` container.

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
