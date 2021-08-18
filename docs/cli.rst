Command-Line Interface
======================

.. code-block::

   scuba [-h]
         [-d DOCKER_ARGS] [-e ENV_VARS] [--entrypoint ENTRYPOINT]
         [--image IMAGE] [--shell SHELL] [-n] [-r] [-v] [-V]
         COMMAND... | ALIAS...


Positional Arguments:
  **COMMAND**
        The command (and arguments) to run in the container

  **ALIAS**
        Alternatively, an :ref:`alias<conf_aliases>` to run

Options:
  -h, --help            Show help message and exit
  -d DOCKER_ARGS, --docker-arg DOCKER_ARGS
                        Pass additional arguments to ``docker run``.
                        These are appended to any :ref:`conf_docker_args` from
                        ``.scuba.yml``.
  -e ENV_VARS, --env ENV_VARS
                        Environment variables to pass to docker.
                        These are merged with (and override) any
                        :ref:`conf_environment` variables from ``.scuba.yml``.
  --entrypoint ENTRYPOINT
                        Override the default ``ENTRYPOINT`` of the image
  --image IMAGE         Override Docker image specified in ``.scuba.yml``
  --shell SHELL         Override shell used in Docker container
  -n, --dry-run         Don't actually invoke docker; just print the docker cmdline
  -r, --root            Run container as root
  -v, --version         Show scuba version and exit
  -V, --verbose         Be verbose
