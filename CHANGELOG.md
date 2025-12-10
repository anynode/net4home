# Changelog

All notable changes to the net4home Home Assistant integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2024-12-XX

### Fixed
- **Critical**: Fixed task management and cleanup - Added `async_stop()` method to properly cancel listening tasks
- **Critical**: Fixed missing import for diagnostics redaction - Implemented custom redaction function
- **Critical**: Fixed connection cleanup - Reader is now properly closed in `async_disconnect()`
- **Important**: Fixed service unregistration - Services are now only unregistered when the last entry is removed (multi-entry support)
- **Important**: Fixed options update listener - Options changes now properly trigger integration reload
- **Important**: Fixed CancelledError handling - Listen task now handles cancellation gracefully
- **Minor**: Added connection state tracking - Commands now check connection state before sending
- **Minor**: Improved exception handling - More specific exception types and better error logging
- **Minor**: Added type hints throughout the API class for better code clarity

### Changed
- Improved error handling in listen loop with specific exception types
- Better logging for connection state and task management
- Services can now be safely used with multiple Bus connector entries

## [1.0.0] - 2024-XX-XX

### Added
- Initial release of net4home Home Assistant integration
- Support for net4home Bus connector integration
- Auto-discovery of Bus connectors via mDNS/Bonjour
- Manual configuration support (host, port, password, MI, OBJADR)
- Multi-hub support - Connect to multiple Bus connectors simultaneously

### Platform Support
- **Binary Sensor**: Contact sensors, motion detectors, and other binary inputs
- **Switch**: Relay switches and actuators (HS-AR6, UP-AR2, HS-AJ3, etc.)
- **Light**: Dimmer controls with brightness support
- **Cover**: Blinds and shutters control (HS-AJ3, HS-AJ4-500, etc.)
- **Climate**: Thermostat and heating control (UP-TLH)
- **Sensor**: Temperature, humidity, and illuminance sensors

### Features
- Device discovery via ENUM_ALL command
- Manual device addition via options flow
- State synchronization between physical devices and Home Assistant
- Custom services:
  - `net4home.debug_devices` - Log all registered devices
  - `net4home.clear_devices` - Clear stored devices
  - `net4home.enum_all` - Trigger device discovery
- Multi-language support (English, German, Spanish)
- Device registry integration
- Diagnostics support

### Requirements
- net4home Bus connector hardware
- Network connectivity to Bus connector (TCP/IP, port 3478)
- Home Assistant 2021.6 or later

---

## Version History

- **1.1.0** - Bug fixes and improvements for production stability
- **1.0.0** - Initial release

