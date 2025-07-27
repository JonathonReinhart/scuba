#!/usr/bin/env python3
import argparse
import black
import glob
import subprocess
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.resolve()
SCUBAINIT_DIR = PROJECT_DIR / "scubainit"
PYTHON_CODE = (
    "scuba",
    "tests",
    "*.py",
)


def _run_black(fix: bool) -> bool:
    args = []
    for pat in PYTHON_CODE:
        args += glob.glob(pat, root_dir=PROJECT_DIR)

    if not fix:
        # check only
        args = args + [
            "--check",
            "--color",
            "--diff",
        ]

    status = black.main(args, standalone_mode=False)

    if status == 0:
        return True
    if status == 1:
        return False
    raise Exception(f"Unexpected exit status: {status}")


def _rust_fmt(fix: bool) -> bool:
    args = [
        "cargo",
        "fmt",
    ]

    if not fix:
        # check only
        args += [
            "--check",
        ]

    status = subprocess.call(args, cwd=SCUBAINIT_DIR)
    if status == 0:
        print("Ok")
        return True
    if status == 1:
        return False
    raise Exception(f"Unexpected exit status: {status}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Modify files to fix formatting",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    ok = True

    print(f"\n{'Fixing' if args.fix else 'Checking'} Python code formatting...")
    ok &= _run_black(args.fix)

    print(f"\n{'Fixing' if args.fix else 'Checking'} Rust code formatting...")
    ok &= _rust_fmt(args.fix)

    if not ok:
        print("\nTo fix, rerun with --fix")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
