# Contributing Guide
*This file is incomplete. Feel free to open an issue if there is missing
information you desire.*

## Dev environment

1. Download and install [docker-ce](https://docs.docker.com/engine/install/debian/#install-using-the-repository)
2. Download and install [rust](https://www.rust-lang.org/tools/install)
<!-- Specific python version? -->
3. Download and install python3 and pip
4. Run `source ./dev_bootstrap.sh`
5. Run `test-docker-images/build_all.sh`

## Build and test

1. See docs/installation for more details on building
2. Run `make` to build scubainit
3. Run `./ci/test_setup.sh` to build docker images necessary for unit testing
4. Run `./run_unit_tests.sh`, `static_analysis.sh` and `run_full_tests.py` to test

## Code Format
Scuba is compliant with the [Black](https://black.readthedocs.io/)
code style. Code format in PRs is verified by a GitHub action.

To check code formatting:
```
$ ./code_format.py
```

To fix code formatting:
```
$ ./code_format.py --fix
```
