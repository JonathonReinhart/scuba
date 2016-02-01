try:
    from shlex import quote as shell_quote
except ImportError:
    from pipes import quote as shell_quote


def format_cmdline(args, maxwidth=80):
    '''Format args into a shell-quoted command line.

    The result will be wrapped to maxwidth characters where possible,
    not breaking a single long argument.
    '''

    # Leave room for the space and backslash at the end of each line
    maxwidth -= 2

    def lines():
        line = ''
        for a in (shell_quote(a) for a in args):
            # If adding this argument will make the line too long,
            # yield the current line, and start a new one.
            if len(line) + len(a) + 1 > maxwidth:
                yield line
                line = ''

            # Append this argument to the current line, separating
            # it by a space from the existing arguments.
            if line:
                line += ' ' + a
            else:
                line = a

        yield line

    return ' \\\n'.join(lines())
