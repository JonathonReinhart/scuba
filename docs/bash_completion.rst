Bash Completion
===============

Scuba supports command-line completion using the `argcomplete`_ package.
Per the `argcomplete README`_, command-line completion can be
activated by:

- Running ``eval "$(register-python-argcomplete scuba)"`` manually to enable completion *in the current shell instance*
- Adding ``eval "$(register-python-argcomplete scuba)"`` to ``~/.bash_completion``
- Running ``activate-global-python-argcomplete --user`` to install the script ``~/.bash_completion.d/python-argcomplete``.

  .. note::

    The generated file must be sourced, which is *not* the default behavior.
    Adding the following code block to ``~/.bash_completion`` is one possible
    solution:

    .. code-block:: bash

        for bcfile in ~/.bash_completion.d/*; do
            [ -f "$bcfile" ] && . "$bcfile"
        done


- Running ``activate-global-python-argcomplete`` as ``root`` (or ``sudo``) to
  use ``argcomplete`` for *all* users

.. _argcomplete: https://github.com/kislyuk/argcomplete
.. _argcomplete README: https://github.com/kislyuk/argcomplete#global-completion
