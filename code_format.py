#!/usr/bin/env python3
import argparse
import black


def _run_black(fix: bool) -> bool:
    args = [
        # TODO(#203): Remove target-version when we add pyproject.toml
        "--target-version=py37",
        ".",
    ]

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

    print(f"{'Fixing' if args.fix else 'Checking'} code formatting...")
    ok = _run_black(args.fix)
    if not ok:
        print("\nTo fix, rerun with --fix")


if __name__ == "__main__":
    main()
