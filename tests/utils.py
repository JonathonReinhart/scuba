from nose.tools import *
from os.path import normpath

def assert_set_equal(a, b):
    assert_equal(set(a), set(b))

def assert_seq_equal(a, b):
    assert_equals(list(a), list(b))

def assert_paths_equal(a, b):
    assert_equals(normpath(a), normpath(b))

def assert_str_equalish(exp, act):
    exp = str(exp).strip()
    act = str(act).strip()
    assert_equal(exp, act)

def assert_startswith(s, prefix):
    s = str(s)
    prefix = str(prefix)
    if not s.startswith(prefix):
        raise AssertionError('"{0}" does not start with "{1}"'
                .format(escape_str(s), prefix))

def escape_str(s):
    # Python 3 won't let us use s.encode('string_escape') :-(
    replacements = [
        ('\a', '\\a'),
        ('\b', '\\b'),
        ('\f', '\\f'),
        ('\n', '\\n'),
        ('\r', '\\r'),
        ('\t', '\\t'),
        ('\v', '\\v'),
    ]

    for r in replacements:
        s = s.replace(*r)
    return s

class BetterAssertRaisesMixin(object):
    def assertRaises2(self, exc_type, func, *args, **kwargs):
        try:
            func(*args, **kwargs)
        except exc_type as e:
            return e
        else:
            self.fail('"{0}" was expected to throw "{1}" exception'
                          .format(func.__name__, exception_type.__name__))
