Configuration
=============

Configuration is done using a `YAML`_ file named ``.scuba.yml`` in the root
directory of your project. It is expected that ``.scuba.yml`` will be
checked-in to version control.

An example ``.scuba.yml`` file might look like this:

.. code-block:: yaml

    image: gcc:5.1

    aliases:
      build: make -j4

In this example, running ``scuba build foo`` would execute ``make -j4 foo`` in
a ``gcc:5.1`` Docker container.


Scuba YAML File Reference
*************************

``.scuba.yml`` is a `YAML`_ file which defines project-specific settings,
allowing a project to use Scuba as part of manual command-line interaction.
As with many other YAML file schemas, most options are controlled by top-level
keys.

Top-level keys
~~~~~~~~~~~~~~

``image``
---------

The ``image`` node defines the Docker image from which Scuba containers are
created.

Example:

.. code-block:: yaml

    image: debian:8.2

The ``image`` node is usually necessary but, as of scuba 2.5, can be omitted
for ``.scuba.yml`` files in which only the ``aliases`` are intended to be used.


.. _conf_environment:

``environment``
---------------

The optional ``environment`` node allows environment variables to be specified.
This can be either a mapping (dictionary), or a list of ``KEY=VALUE`` pairs.
If a value is not specified, the value is taken from the external environment.

Examples:

.. code-block:: yaml

    environment:
      FOO: "This is foo"
      SECRET:

.. code-block:: yaml

    environment:
      - FOO=This is foo
      - SECRET


.. _conf_docker_args:

``docker_args``
---------------

The optional ``docker_args`` node allows additional docker arguments to be
specified.

Example:

.. code-block:: yaml

    docker_args: --privileged -v "/tmp/hello world:/tmp/hello world"

The value of ``docker_args`` is parsed as shell command line arguments using
`shlex.split <https://docs.python.org/3/library/shlex.html#shlex.split>`_.

The previous example could be equivalently written in YAML's `single-quoted
style <https://yaml.org/spec/1.2/spec.html#id2788097>`_:

.. code-block:: yaml

    docker_args: '--privileged -v "/tmp/hello world:/tmp/hello world"'

``volumes``
-----------
The optional ``volumes`` node allows additional `volumes
<https://docs.docker.com/storage/volumes/>`_ or bind-mounts to be specified.
``volumes`` is a mapping (dictionary) where each key is the container-path.
In the simple form, the value is a string, the host-path to be bind-mounted:

.. code-block:: yaml

    volumes:
      /var/lib/foo: /host/foo

In the complex form, the value is a mapping which must contain a ``hostpath``
subkey. It can also contain an ``options`` subkey with a comma-separated list
of volume options:

.. code-block:: yaml

    volumes:
      /var/lib/foo:
        hostpath: /host/foo
        options: ro,cached



.. _conf_aliases:

``aliases``
-----------

The optional ``aliases`` node is a mapping (dictionary) of bash-like aliases,
where each key is an alias, and each value is the command that will be run when
that alias is specified as the *user command* during scuba invocation. The
command is parsed like a shell command-line, and additional user arguments from
the command line are appended to the alias arguments. Aliases follow the
:ref:`common script schema<conf_common_script_schema>`.

Example:

.. code-block:: yaml

    aliases:
      build: make -j4

In this example, ``$ scuba build foo`` would execute ``make -j4 foo`` in the
container.

Aliases can also override the global ``image``, allowing aliases to use different
images. Example:

.. code-block:: yaml

    image: default_image
    aliases:

      # This one inherits the default, top-level 'image' and specifies "script" as a string
      default:
        script: cat /etc/os-release

      # This one specifies a different image to use and specifies "script" as a list
      different:
        image: alpine
        script:
          - cat /etc/os-release

Aliases can add to the top-level ``environment`` and override its values using
the same syntax:

.. code-block:: yaml

    environment:
      FOO: "Top-level"
    aliases:
      example:
        environment:
          FOO: "Override"
          BAR: "New"
        script:
          - echo $FOO $BAR

Aliases can extend the top-level ``docker_args``. The following example will
produce the docker arguments ``--privileged -v /tmp/bar:/tmp/bar`` when
executing the ``example`` alias:

.. code-block:: yaml

    docker_args: --privileged
    aliases:
      example:
        docker_args: -v /tmp/bar:/tmp/bar
        script:
          - ls -l /tmp/

Aliases can also opt to override the top-level ``docker_args``, replacing it with
a new value. This is achieved with the ``!override`` tag:

.. code-block:: yaml

    docker_args: -v /tmp/foo:/tmp/foo
    aliases:
      example:
        docker_args: !override -v /tmp/bar:/tmp/bar
        script:
          - ls -l /tmp/

The content of the ``docker_args`` key is re-parsed as YAML in order to allow
combining the ``!override`` tag with other tags; however, this requires quoting
the value, since YAML forbids a plain-style scalar from beginning with a ``!``
(see `the spec <https://yaml.org/spec/1.2/spec.html#id2788859>`_). In the next
example, the top-level alias is replaced with an explicit ``!!null`` tag, so
that no additional arguments are passed to docker when executing the ``example``
alias:

.. code-block:: yaml

    docker_args: -v /tmp/foo:/tmp/foo
    aliases:
      example:
        docker_args: !override '!!null'
        script:
          - ls -l /tmp/


Aliases can extend or override the top-level ``volumes``:

.. code-block:: yaml

    volumes:
      /var/lib/foo: /host/foo
    aliases:
      example:
        volumes:
          /var/lib/foo: /example/foo
          /var/lib/bar: /example/bar
        script:
          - ls -l /var/lib/foo /var/lib/bar



``hooks``
---------

The optional ``hooks`` node is a mapping (dictionary) of "hook" scripts that run
as part of ``scubainit`` before running the user command. They use the
:ref:`common script schema<conf_common_script_schema>`. The following hooks exist:

- ``root`` - Runs just before ``scubainit`` switches from ``root`` to ``scubauser``
- ``user`` - Runs just before ``scubainit`` executes the user command

Example:

.. code-block:: yaml

    hooks:
      root:
        script:
          - 'echo "HOOK: This runs before we switch users"'
          - id
      user: 'echo "HOOK: After switching users, uid=$(id -u) gid=$(id -g)"'


``shell``
---------

The optional ``shell`` node allows the default shell that Scuba uses in the 
container (``/bin/sh``) to be overridden by another shell. This is useful for
images that do not have a shell located at ``/bin/sh``.

Example:

.. code-block:: yaml

    shell: /busybox/sh

Aliases can also override the shell from the default or the top-level of
the ``.scuba.yml`` file:

.. code-block:: yaml

    aliases:
      my_shell:
        shell: /bin/cool_shell
        script:
          - echo "This is executing in cool_shell"
      busybox_shell:
        script:
          - echo "This is executing in scuba's default shell"


Alias-level keys
~~~~~~~~~~~~~~~~

``root``
--------

The optional ``root`` node allows an alias to specify whether its container
should be run as root:

.. code-block:: yaml

    aliases:
      root_check:
        root: true
        script:
          - echo 'Only root can do this!'
          - echo "I am UID $(id -u)"
          - cat /etc/shadow

.. _conf_common_script_schema:

Common script schema
~~~~~~~~~~~~~~~~~~~~
Several parts of ``.scuba.yml`` which define "scripts" use a common schema.
The *common script schema* can define a "script" in one of several forms:

The *simple* form is simply a single string value:

.. code-block:: yaml

    hooks:
      user: echo hello


The *complex* form is a mapping, which must contain a ``script`` subkey, whose
value is either single string value:

.. code-block:: yaml

    hooks:
      root:
        script: echo hello

... or a list of strings making up the script:

.. code-block:: yaml

    hooks:
      root:
        script:
          - 'echo hello!'
          - touch foo
          - 'echo goodbye :-('

Note that in any case, YAML strings do not need to be enclosed in quotes,
unless there are "confusing" characters (like a colon). In any case, it is
always safer to include quotes.


Accessing external YAML content
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
In addition to normal `YAML`_ synax, an additional constructor, ``!from_yaml``,
is available for use in ``.scuba.yml`` which allows a value to be retrieved
from an external YAML file. It has the following syntax:

.. code-block:: yaml

    !from_yaml filename key

Arguments:

- ``filename`` - The path of an external YAML file (relative to ``.scuba.yaml``)
- ``key`` - A dot-separated locator of the key to retrieve

This is useful for projects where a Docker image in which to build is already
specified in another YAML file, for example in `.gitlab-ci.yml`_. This
eliminates the redundancy between the configuration files. An example which
uses this:

.. code-block:: yaml
    :caption: .gitlab-ci.yml

    image: gcc:5.1

.. code-block:: yaml
    :caption: .scuba.yml

    image: !from_yaml .gitlab-ci.yml image

Here's a more elaborate example which defines multiple aliases which correspond
to jobs defined by ``.gitlab-ci.yml``:

.. code-block:: yaml
    :caption: .gitlab-ci.yml

    build_c:
      image: gcc:5.1
      script:
        - make something
        - make something-else

    build_py:
      image: python:3.7
      script:
        - setup.py bdist_wheel



.. code-block:: yaml
    :caption: .scuba.yml

    # Note that 'image' is not necessary if only invoking aliases

    aliases
      build_c:
        image: !from_yaml .gitlab-ci.yml build_c.image
        script: !from_yaml .gitlab-ci.yml build_c.script
      build_py:
        image: !from_yaml .gitlab-ci.yml build_py.image
        script: !from_yaml .gitlab-ci.yml build_py.script

An easier but less-flexible method is to simply import the entire job's
definition. This works becaue Scuba ignores unrecognized keys in an ``alias``:

.. code-block:: yaml
    :caption: .scuba.yml

    aliases
      build_c: !from_yaml .gitlab-ci.yml build_c
      build_py: !from_yaml .gitlab-ci.yml build_py

This example which concatenates two jobs from ``.gitlab-ci.yml`` into a single
alias. This works by flattening the effective ``script`` node that results by
including two elements that are lists.

.. code-block:: yaml
    :caption: .gitlab-ci.yml

    image: gcc:5.1

    part1:
      script:
        - make something
    part2:
      script:
        - make something-else

.. code-block:: yaml
    :caption: .scuba.yml

    image: !from_yaml .gitlab-ci.yml image

    aliases
      all_parts:
        script:
          - !from_yaml .gitlab-ci.yml part1.script
          - !from_yaml .gitlab-ci.yml part2.script


Dots (``.``) in a YAML *path* can be escaped using a backslash (which must be
doubled inside of quotes). This example shows how to reference job names
containing a ``.`` character:


.. code-block:: yaml
    :caption: .gitlab-ci.yml

    image: gcc:5.1

    .part1:
      script:
        - make something
    .part2:
      script:
        - make something-else

.. code-block:: yaml
    :caption: .scuba.yml

    image: !from_yaml .gitlab-ci.yml image

    aliases
      build_part1: !from_yaml .gitlab-ci.yml "\\.part1.script"
      build_part2: !from_yaml .gitlab-ci.yml "\\.part2.script"



Additional examples can be found in the ``example`` directory.


.. _YAML: http://yaml.org/
.. _.gitlab-ci.yml: http://doc.gitlab.com/ce/ci/yaml/README.html
