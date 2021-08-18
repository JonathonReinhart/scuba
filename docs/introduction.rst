Introduction
============
Scuba makes it easier to use Docker containers in everyday development.  It is
intended to be used by developers in ``make`` or ``scons``-based build
environments, where the entire build environment is encapsulated in a Docker
container.

Its purpose is to lower the barrier to using Docker for everyday builds. Scuba
keeps you from having to remember a complex ``docker run`` command line, and
turns this::

    $ docker run -it --rm -v $(pwd):/build:z -w /build -u $(id -u):$(id -g) gcc:5.1 make myprogram

into this::

    $ scuba make myprogram

Scuba references a ``.scuba.yml`` file which is intended to be checked-in to
your project's version control, which ensures that all developers are always
using the exact correct version of the the Docker build environment for a given
commit.
