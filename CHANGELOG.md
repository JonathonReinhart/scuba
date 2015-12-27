# Change Log
All notable changes to this project will be documented in this file.
This project adheres to [Semantic Versioning](http://semver.org/).

## [Unreleased]

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


[Unreleased]: https://github.com/JonathonReinhart/scuba/compare/v1.1.2...HEAD
[1.1.2]: https://github.com/JonathonReinhart/scuba/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/JonathonReinhart/scuba/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/JonathonReinhart/scuba/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/JonathonReinhart/scuba/compare/v0.1.0...v1.0.0
