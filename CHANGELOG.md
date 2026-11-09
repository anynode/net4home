# Changelog

All notable changes to the net4home Home Assistant integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.4] - 2026-11-09

### Fixed
- HS-Time firmware 4.03/1.22 does not answer the module-info read when it ends with an extra zero. The read is `25 FF` again. The object address is taken from the minute clock when the short reply has none, and the profile mask, sunrise and sunset are queried at that address.

## [1.3.3] - 2026-11-09

### Fixed
- HS-Time firmware 4.03/1.22 answers the module-info read with 3 bytes and no object address. The integration now uses the module number (MI0264 is object 26401) and still reads the profile mask, sunrise and sunset. A stored address is kept. Newer firmware that sends the address is unchanged.

## [1.3.2] - 2026-11-09

### Fixed
- HS-Time user software is read from both version notations (`4.03/1.22` and `4.03/122`). Firmware before 2.01 keeps the 16-line schedule and sunrise/sunset at base +17/+18. From 2.01 the table has 48 lines and the sun values are at base +49/+50.

## [1.3.1] - 2026-01-25

### Added
- Startup switches for reading group info and module info (config options)
- `enum_all` service with schema
- Jalousie position from the actor status (0..100, 0xFF = unknown) and a run-time based estimate
- `set_position` for covers with a configured run time, position restored after restart
- Group entities show `groups`, `address` and `members` attributes with translations
- German, English and Spanish translations for exceptions, abort messages and attributes

### Changed
- Connection: timeout while connecting, `ConfigEntryNotReady` on failed start, platforms are set up only after a connection
- Entities become unavailable when the bus connection is lost; commands fail with an error while disconnected
- Reconnect in rounds with increasing delays
- `should_poll` is off for all entities, updates are pushed
- Measurement sensors use `state_class` measurement
- Config flow: unique id `host:port`, test connection is closed, duplicate entries are aborted
- First start searches the bus when no modules are stored, then reads module info and groups
- Setup offers Local when the net4home Server add-on announces service `net4home`, without asking for host, port or password
- Diagnostics redact host, password, title and unique id
- Manifest: single `PLATFORMS` list, `issue_tracker` and `loggers` added
- `api.py` split into protocol, packet dispatch and command modules

### Removed
- Unused `hub.py`

### Fixed
- Group entities did not receive member state updates
- Jalousie shows an unknown state after a stop when the position is unknown

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
