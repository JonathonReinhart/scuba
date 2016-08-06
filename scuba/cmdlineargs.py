import argparse
import sys

__all__ = ['ListOptsAction']

class ListOptsAction(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        super(ListOptsAction, self).__init__(option_strings, dest, nargs=0, **kwargs)

    def __call__(self, parser, namespace, values, option_string):
        def get_long_opts():
            for act in parser._actions:
                # These aren't shown in help; don't auto-complete them either
                if act.help == argparse.SUPPRESS:
                    continue

                # These aren't options
                if len(act.option_strings) == 0:
                    continue

                # Prefer long opts, but show short if there is no long version
                longs = list(filter(lambda o: o.startswith('--'), act.option_strings))
                yield longs[0] if longs else act.option_strings[0]

        opts = sorted(get_long_opts(), key=lambda s: s.strip('-'))
        print('\n'.join(opts))
        sys.exit(0)
