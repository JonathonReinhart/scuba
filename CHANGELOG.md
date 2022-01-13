# Change Log
All notable changes to this project will be documented in this file.
This project adheres to [Semantic Versioning](http://semver.org/).

## [2.10.0] - 2022-01-12
### Added
- Add ability to use environment variables in volume paths (#192)


## [2.9.0] - 2021-09-15
### Added
- Add ability to specify volumes in `.scuba.yml` (#186)


## [2.8.0] - 2021-08-18
### Added
- Add ability to specify additional docker arguments in `.scuba.yml` (#177)

### Changed
- Switched testing framework from from `nose` to `pytest`


## [2.7.0] - 2020-06-08
### Changed
- Switched to using `argcomplete` to provide Bash command line completion (#162)


## [2.6.1] - 2020-04-24
### Fixed
- scubainit ignores matching passwd/group/shadow file entries when creating the
  user. This allows transparently running scuba as root. (#164)
- Fixed bug where scubainit incorrectly displayed the exit status of a failed
  hook script. (#165)
- Fixed bug where user home directory was not writable when scuba workdir
  existed below the home directory. (#169)


## [2.6.0] - 2020-03-25
### Added
- Add ability to override the shell in which the scuba-generated
  script is run, via command line option (`--shell`) or via
  `.scuba.yml` (#159)
- Add ability to specify in `.scuba.yml` that a particular alias
  should run as root (#159)


## [2.5.0] - 2020-03-05
### Changed
- Use username/groupname of invoking user inside container (#153)
- Ignore already existing UID/GIDs (#139)
- Allow top-level `image` to be omitted in `.scuba.yml` (#158)

### Fixed
- Fixed deprecation error with `collections.Mapping` (#156)

### Removed
- Drop support for Python 2 (#154)


## [2.4.2] - 2020-02-24
### Changed
- Use GitHub Actions instead of Travis CI for publishing releases


## [2.4.1] - 2020-02-21
### Added
- Cache yaml files loaded by `!from_yaml`
### Removed
- Drop support for Python 3.4


## [2.4.0] - 2020-01-06
### Added
- Enable scuba to override entrypoint via `--entrypoint` or `.scuba.yml` (#125)
- Add support for nested scripts (#128)
- Add `SCUBA_ROOT` environment variable (#129)
- Add support for escaped dots in `!from_yml` (#137)

### Changed
- Don't run image entrypoint for each line in a mult-line alias (#121)
- Use `yaml.SafeLoader` for loading config (#133)

### Removed
- Drop support for Python 2.6, 3.2, and 3.3 (#119, #130)


## [2.3.0] - 2018-09-10
### Added
- Add -e/--env command-line option (#111)
- Add support for setting environment in .scuba.yml (#120)

### Changed
- Implemented auto-versioning using Git and Travis (#112)

### Fixed
- Copy scubainit to allow SELinux relabeling (#117)


## [2.2.0] - 2018-03-07
### Changed
- Allow `script` to be a single string value in the "common script schema"
  which applies to hooks and aliases (#102)

### Fixed
- Display nicer error message if no command is given and image doesn't specify a `Cmd` (#104)
- Don't mangle && in scripts (#100)
- Don't allocate tty if stdin is redirected (#95)

## [2.1.0] - 2017-04-03
### Added
- Added `--image` option (#87)


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
- Added to PyPI

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


[Unreleased]: https://github.com/JonathonReinhart/scuba/compare/v2.10.0...HEAD
[2.10.0]: https://github.com/JonathonReinhart/scuba/compare/v2.9.0...v2.10.0
[2.9.0]: https://github.com/JonathonReinhart/scuba/compare/v2.8.0...v2.9.0
[2.8.0]: https://github.com/JonathonReinhart/scuba/compare/v2.7.0...v2.8.0
[2.7.0]: https://github.com/JonathonReinhart/scuba/compare/v2.6.1...v2.7.0
[2.6.1]: https://github.com/JonathonReinhart/scuba/compare/v2.6.0...v2.6.1
[2.6.0]: https://github.com/JonathonReinhart/scuba/compare/v2.5.0...v2.6.0
[2.5.0]: https://github.com/JonathonReinhart/scuba/compare/v2.4.2...v2.5.0
[2.4.2]: https://github.com/JonathonReinhart/scuba/compare/v2.4.1...v2.4.2
[2.4.1]: https://github.com/JonathonReinhart/scuba/compare/v2.4.0...v2.4.1
[2.4.0]: https://github.com/JonathonReinhart/scuba/compare/v2.3.0...v2.4.0
[2.3.0]: https://github.com/JonathonReinhart/scuba/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/JonathonReinhart/scuba/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/JonathonReinhart/scuba/compare/v2.0.1...v2.1.0
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
