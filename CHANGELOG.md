# Changelog

All notable changes to the net4home Home Assistant integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.1] - 2026-01-25

- minor updates

## [1.3.0] - 2026-01-19

### Removed
- Serial connection support - integration now only supports IP/TCP connections
- Removed `pyserial-asyncio-fast` dependency
- Removed serial port configuration from config flow
- Removed `discover_serial_ports()` helper function

### Changed
- Simplified connection handling to IP-only
- Improved disconnect handling with proper task cancellation and timeouts
- Fixed button visibility for MI devices (Read Device Config button now shows for all MI devices)

### Fixed
- Fixed syntax error in exception handling
- Fixed blocking issue when removing integration (proper task cleanup)

## [1.1.0] - 2026-01-13

### Added
- Automated version management system with cursor rules
- Pre-commit version bump script for automated version management
- Git ignore file for build artifacts and internal documentation
- Cursor configuration for development workflow

### Changed
- Improved development workflow with automated version bumping before GitHub commits
