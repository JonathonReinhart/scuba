try:
    from shlex import quote as shell_quote
except ImportError:
    from pipes import quote as shell_quote

def format_cmdline(args, maxwidth=80):
    def lines():
        line = ''
        for a in (shell_quote(a) for a in args):
            if len(line) + len(a) > maxwidth:
                yield line
                line = ''
            line += ' ' + a

    return ' \\\n'.join(lines())[1:]
