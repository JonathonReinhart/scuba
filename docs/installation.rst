Installation
============

Install via pip
---------------
Scuba is hosted at `PyPI`_, and installation
via pip is the perferred method.

To install::

    $ sudo pip install scuba

To install with ``argcomplete`` (for :doc:`bash_completion` support)::

    $ sudo pip install scuba[argcomplete]

To uninstall::

    $ sudo pip uninstall scuba

Install from source
-------------------
Scuba can be built from source on Linux only (due to the fact that
``scubainit`` must be compiled):

1. Run ``make`` to build ``scubainit``
2. Run ``./run_unit_tests.py`` to run the unit tests
3. Run ``sudo python setup.py install`` to install scuba
4. Run ``./run_full_tests.py`` to test the installed version of scuba

If `musl-libc`_ is installed, it can be used to reduce the size of
``scubainit``, by overriding the ``CC`` environment variable in step 1::

    CC=/usr/local/musl/bin/musl-gcc make


.. note::
  Note that installing from source in this manner can lead to an installation
  with increased startup times for Scbua. See `#71`_ for more details. This
  can be remedied by forcing a `wheel`_ to be installed, as such:

  .. code-block:: bash
  
      export CC=/usr/local/musl/bin/musl-gcc    # (optional)
      sudo pip install wheel
      python setup.py bdist_wheel
      sudo pip install dist/scuba-<version>-py3-none-any.whl


.. _PyPI: https://pypi.python.org/pypi/scuba
.. _musl-libc: https://www.musl-libc.org/
.. _#71: https://github.com/JonathonReinhart/scuba/issues/71
.. _wheel: http://pythonwheels.com/
