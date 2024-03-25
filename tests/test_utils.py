import io
from itertools import chain
import os
import pytest
import shlex
from typing import List, Sequence

from .utils import assert_seq_equal

import scuba.utils


def _parse_cmdline(cmdline: str) -> List[str]:
    # Strip the formatting and whitespace
    lines = [l.rstrip("\\").strip() for l in cmdline.splitlines()]

    # Split each line, and return a flattened list of arguments
    return list(chain.from_iterable(map(shlex.split, lines)))


def _test_format_cmdline(args: Sequence[str]) -> None:
    # Call the unit-under-test to get the formatted command line
    result = scuba.utils.format_cmdline(args)

    # Parse the result back out to a list of arguments
    out_args = _parse_cmdline(result)

    # Verify that they match
    assert_seq_equal(out_args, args)


def test_format_cmdline() -> None:
    """format_cmdline works as expected"""

    _test_format_cmdline(
        [
            "something",
            "-a",
            "-b",
            "--long",
            "option text",
            "-s",
            "hort",
            (
                "a very long argument here that will end up on its own line because it"
                " is so wide and nothing else will fit at the default width"
            ),
            "and now",
            "some",
            "more",
            "stuff",
            "and even more stuff",
        ]
    )


def test_shell_quote_cmd() -> None:
    args = ["foo", "bar pop", '"tee ball"']

    result = scuba.utils.shell_quote_cmd(args)

    out_args = shlex.split(result)

    assert_seq_equal(out_args, args)


def test_parse_env_var() -> None:
    """parse_env_var returns a key, value pair"""
    result = scuba.utils.parse_env_var("KEY=value")
    assert result == ("KEY", "value")


def test_parse_env_var_more_equals() -> None:
    """parse_env_var handles multiple equals signs"""
    result = scuba.utils.parse_env_var("KEY=anotherkey=value")
    assert result == ("KEY", "anotherkey=value")


def test_parse_env_var_no_equals(monkeypatch: pytest.MonkeyPatch) -> None:
    """parse_env_var handles no equals and gets value from environment"""
    monkeypatch.setenv("KEY", "mockedvalue")
    result = scuba.utils.parse_env_var("KEY")
    assert result == ("KEY", "mockedvalue")


def test_parse_env_var_not_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """parse_env_var returns an empty string if not set"""
    monkeypatch.delenv("NOTSET", raising=False)
    result = scuba.utils.parse_env_var("NOTSET")
    assert result == ("NOTSET", "")


def test_flatten_list__not_list() -> None:
    with pytest.raises(ValueError):
        scuba.utils.flatten_list("abc")  # type: ignore[arg-type]


def test_flatten_list__not_nested() -> None:
    sample = [1, 2, 3, 4]
    result = scuba.utils.flatten_list(sample)
    assert result == sample


def test_flatten_list__nested_1() -> None:
    sample = [
        1,
        [2, 3],
        4,
        [5, 6, 7],
    ]
    exp = range(1, 7 + 1)
    result = scuba.utils.flatten_list(sample)
    assert_seq_equal(result, exp)


def test_flatten_list__nested_many() -> None:
    sample = [
        1,
        [2, 3],
        [4, 5, [6, 7, 8]],
        9,
        10,
        [11, [12, [13, [14, [15, [16, 17, 18]]]]]],
    ]
    exp = range(1, 18 + 1)
    result = scuba.utils.flatten_list(sample)
    assert_seq_equal(result, exp)


def test_get_umask() -> None:
    testval = 0o123  # unlikely default
    orig = os.umask(testval)
    try:
        # Ensure our test is valid
        assert orig != testval

        # Make sure it works
        assert scuba.utils.get_umask() == testval

        # Make sure it had no effect
        assert scuba.utils.get_umask() == testval
    finally:
        os.umask(orig)


def test_writeln() -> None:
    with io.StringIO() as s:
        scuba.utils.writeln(s, "hello")
        scuba.utils.writeln(s, "goodbye")
        assert s.getvalue() == "hello\ngoodbye\n"


def test_expand_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_VAR", "my favorite variable")
    assert (
        scuba.utils.expand_env_vars("This is $MY_VAR") == "This is my favorite variable"
    )
    assert (
        scuba.utils.expand_env_vars("What is ${MY_VAR}?")
        == "What is my favorite variable?"
    )


def test_expand_missing_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MY_VAR", raising=False)
    # Verify that a KeyError is raised for unset env variables
    with pytest.raises(KeyError) as kerr:
        scuba.utils.expand_env_vars("Where is ${MY_VAR}?")
    assert kerr.value.args[0] == "MY_VAR"


def test_expand_env_vars_dollars() -> None:
    # Verify that a ValueError is raised for bare, unescaped '$' characters
    with pytest.raises(ValueError):
        scuba.utils.expand_env_vars("Just a lonely $")

    # Verify that it is possible to get '$' characters in an expanded string
    assert scuba.utils.expand_env_vars(r"Just a lonely $$") == "Just a lonely $"
