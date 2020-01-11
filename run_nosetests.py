#!/usr/bin/env python
import os
import sys
import nose
import argparse

def remove_f(path):
    '''Same as rm -f'''
    try:
        os.unlink(path)
    except OSError as oe:
        pass

def exclude_sys_path(path):
    path = os.path.realpath(path)
    sys.path = [p for p in sys.path if not os.path.realpath(p) == path]


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-local-import', action='store_true',
            help = 'Remove the current directory from sys.path')
    return ap.parse_known_args()

def main():
    args, otherargs = parse_args()

    if args.no_local_import:
        # Remove the current directory from the import path
        exclude_sys_path('.')

    remove_f('.coverage')

    nose.main(
        argv = [
            'nosetests',

            '-v',
            '--with-coverage',
            '--cover-inclusive',
            '--cover-package=scuba',
            '--detailed-errors',
            '--process-timeout=60',
        ] + otherargs,
    )

if __name__ == '__main__':
    main()
