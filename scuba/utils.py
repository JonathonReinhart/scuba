import os
from shlex import quote as shell_quote
import string
from typing import Iterable, TextIO, Tuple


def shell_quote_cmd(cmdlist: Iterable[str]) -> str:
    return " ".join(map(shell_quote, cmdlist))


def format_cmdline(args: Iterable[str], maxwidth: int = 80) -> str:
    """Format args into a shell-quoted command line.

    The result will be wrapped to maxwidth characters where possible,
    not breaking a single long argument.
    """

    # Leave room for the space and backslash at the end of each line
    maxwidth -= 2

    def lines() -> Iterable[str]:
        line = ""
        for a in (shell_quote(a) for a in args):
            # If adding this argument will make the line too long,
            # yield the current line, and start a new one.
            if len(line) + len(a) + 1 > maxwidth:
                yield line
                line = ""

            # Append this argument to the current line, separating
            # it by a space from the existing arguments.
            if line:
                line += " " + a
            else:
                line = a

        yield line

    return " \\\n".join(lines())


def parse_env_var(s: str) -> Tuple[str, str]:
    """Parse an environment variable string

    Returns a key-value tuple

    Apply the same logic as `docker run -e`:
    "If the operator names an environment variable without specifying a value,
    then the current value of the named variable is propagated into the
    container's environment
    """
    parts = s.split("=", 1)
    if len(parts) == 2:
        k, v = parts
        return (k, v)

    k = parts[0]
    return (k, os.getenv(k, ""))


def flatten_list(x: list) -> list:
    if not isinstance(x, list):
        raise ValueError("argument is not a list")
    result = []
    for i in x:
        if isinstance(i, list):
            for j in flatten_list(i):
                result.append(j)
        else:
            result.append(i)
    return result


def get_umask() -> int:
    # Same logic as bash/builtins/umask.def
    val = os.umask(0o22)
    os.umask(val)
    return val


def writeln(f: TextIO, line: str) -> None:
    f.write(line + "\n")


def expand_env_vars(in_str: str) -> str:
    """Expand environment variables in a string

    Can raise `KeyError` if a variable is referenced but not defined, similar to
    bash's nounset (set -u) option"""
    return string.Template(in_str).substitute(os.environ)
