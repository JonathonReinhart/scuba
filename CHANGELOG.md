# Change Log
All notable changes to this project will be documented in this file.
This project adheres to [Semantic Versioning](http://semver.org/).

## [2.0.1] - 2017-01-17
### Fixed
- Fixed image entrypoint being ignored (#83)


## [2.0.0] - 2016-11-21
### Added
- Added support for enhanced aliases (#67)
- Added support for per-alias image specification (#68)
- Add bash completion support (#69)

### Changed
- All ancillary files are bind-mounted via single temp dir
- Hook scripts are moved to hooks/ subdirectory
- User commands always executed via shell (#66)
- Top-level directory mounted at same path in container (#70)
- Alias names cannot contain spaces
- Improve distributions (#74, #75, #76, #78)

### Removed
- Remove support for remote Docker instances (#64)
  Support for this was limited/broken as of 1.7.0 anyway; this officially
  removes support for it.

### Fixed
- Fixed inability to run an image that doesn't yet exist locally, broken in
  1.7.0 ([#79])

## [1.7.0] - 2016-05-19
### Added
- Add support for scubainit hooks

### Changed
- `scubainit` re-implemented as a C program, which does the following:
   - Creates the scubauser user/group
   - Sets the umask
   - Switches users then *execs* the user command
  This is to provide more control during initialization, without the artifacts
  caused by the use of 'su' in the .scubainit from 1.3.
- scubauser now has a proper writable home directory in the container (#45)

## [1.6.0] - 2016-02-06
### Added
- Add `-d` to pass arbitrary arguments to `docker run`


## [1.5.0] - 2016-02-01
### Added
- Add `-r` option to run container as root
- Add automated testing (both unit and system tests)
- Add support for Python 2.6 - 3.5
- Added to PyPi

### Changed
- Scuba is now a package, and setup.py installs it as such, including an
  auto-generated `console_script` wrapper.
- `--dry-run` output now shows an actual docker command-line.
- Only pass `--tty` to docker if scuba's stdout is a TTY.

### Fixed
- Better handle empty `.scuba.yml` and other YAML-related errors
- Fix numerous bugs when running under Python 3


## [1.4.0] - 2016-01-08
### Added
- Added `--verbose` and `--dry-run` options

### Removed
- umask is no longer set in the container. (See [#24])

### Fixed
- Problems introduced in v1.3.0 with Ctrl+C in images are fixed.
  The user command now runs as PID 1 again, as there is no more
  `.scubainit` script.


## [1.3.0] - 2016-01-07
### Added
- Set umask in container to the same as the host (local Docker only)

### Changed
- Change working directory from `/build` to `/scubaroot`
- Use `.scubainit` script to create `scubauser` user/group at container
  startup. This avoids the oddity of running as a uid not listed in
  `/etc/passwd`, avoiding various bugs (see [issue 11]). (local Docker only)


## [1.2.0] - 2015-12-27
### Added
- Search up the directory hierarchy for .scuba.yml; this allows invoking
  scuba from a project subdirectory.
- Add `!from_yaml` support to YAML loading; this allows specifying image
  from an external YAML file (e.g. `.gitlab-ci.yml`).
- Add CHANGELOG.md

### Changed
- Show better error message when docker cannot be executed


## [1.1.2] - 2015-12-22
### Fixed
- Don't pass `--user` option when remote docker is being used


## [1.1.1] - 2015-12-22
### Fixed
- Fix bug when `aliases` is not found in `.scuba.yml`


## [1.1.0] - 2015-12-20
### Added
- Support for Bash-like aliases, specified in `.scuba.yml`


## [1.0.0] - 2015-12-18
### Removed
- Remove the `command` node from `.scuba.yml` spec; it limits the usefulness
  of scuba by limiting the user to one command. Now command is specified on
  command line after scuba.

### Added
- Argument parsing to scuba (-v for version)
- Check for and reject extraneous nodes in `.scuba.yml`


## 0.1.0 - 2015-12-09
First versioned release


[Unreleased]: https://github.com/JonathonReinhart/scuba/compare/v2.0.1...HEAD
[2.0.1]: https://github.com/JonathonReinhart/scuba/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/JonathonReinhart/scuba/compare/v1.7.0...v2.0.0
[1.7.0]: https://github.com/JonathonReinhart/scuba/compare/v1.6.0...v1.7.0
[1.6.0]: https://github.com/JonathonReinhart/scuba/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/JonathonReinhart/scuba/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/JonathonReinhart/scuba/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/JonathonReinhart/scuba/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/JonathonReinhart/scuba/compare/v1.1.2...v1.2.0
[1.1.2]: https://github.com/JonathonReinhart/scuba/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/JonathonReinhart/scuba/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/JonathonReinhart/scuba/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/JonathonReinhart/scuba/compare/v0.1.0...v1.0.0

[issue 11]: https://github.com/JonathonReinhart/scuba/issues/11
[#24]: https://github.com/JonathonReinhart/scuba/pull/24
[#79]: https://github.com/JonathonReinhart/scuba/issues/79
