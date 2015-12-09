SCUBA
-----

Simple Container-Utilizing Build Apparatus

SCUBA is a simple tool that makes it easier to use Docker containers in everyday development.
It is intended to be used by developers in 'make' or 'scons' based build environments, where
the entire build environment is encapsulated in a Docker container.

Its purpose is to lower the barrier to using Docker for everyday builds. SCUBA keeps you from
having to remember a verbose `docker run` command line, and turns this

    $ docker run -it --rm -v $(pwd):/build:z -w /build -u $(id -u):$(id -g) name/image make -j4 myprogram

into this:

    $ scuba myprogram

## Requirements

- Python 2.6 or 2.7
   - [PyYAML](http://pyyaml.org/)

## Installation

Simply put `scuba` from the `src` directory somewhere in your `$PATH` (e.g. `/usr/local/bin`).

## Configuration

Configuration is done using a [YAML](http://yaml.org/) file named `.scuba.yml` in the root
directory of your project. It is expected that `.scuba.yml` be checked in to version control.
`.scuba.yml` currently has two required nodes:

- `image` - The Docker image to run
- `command` - The command to run inside the container (in the current directory)


A `.scuba.yml` file might look like this:

```yaml
image: gcc:5.1
command: make -j4
```

This tells SCUBA:
- Use the `gcc:5.1` Docker image
- Run `make -j4`, plus whatever you specify on the command-line to scuba

## License

This software is released under the [MIT License](https://opensource.org/licenses/MIT).
