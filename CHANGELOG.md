# Change Log
All notable changes to this project will be documented in this file.
This project adheres to [Semantic Versioning](http://semver.org/).

## [Unreleased]

## [1.2.0] - 2015-12-27
### Added
- Search up the directory hierarchy for .scuba.yml; this allows invoking
  scuba from a project subdirectory.
- Add `!from_yaml` support to YAML loading; this allows specifying image
  from an external YAML file (e.g. `.gitlab-ci.yml`).
- Add CHANGELOG

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


[Unreleased]: https://github.com/JonathonReinhart/scuba/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/JonathonReinhart/scuba/compare/v1.1.2...v1.2.0
[1.1.2]: https://github.com/JonathonReinhart/scuba/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/JonathonReinhart/scuba/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/JonathonReinhart/scuba/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/JonathonReinhart/scuba/compare/v0.1.0...v1.0.0
