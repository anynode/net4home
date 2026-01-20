# Home Assistant net4home Integration

This repository contains the custom component for integrating net4home devices with Home Assistant.
The net4home integration for Home Assistant allows you to connect to net4home hardware devices.

The integration of net4home in Home Assistant offers an unlimited number of possibilities for automation.  
The simple integration of an existing installation opens up a wide range of applications in conjunction with devices from other manufacturers.

## Prerequisites 

The integration requires one net4home Bus connector.
Each connection to a Bus connector is represented in Home Assistant as a **hub** device. After the hub is connected, net4home modules will appear as child devices. Entities are created based on the reported device type.
The `net4home` integration allows connections to more than one Bus connector. For each connector, a new integration entry needs to be created.

## Features

- Auto-discovery via Zeroconf
- Manual configuration (host, port, bus password, MI, OBJADR)
- Binary sensors (contact, motion, etc.)
- Localization support in English, German and Spanish
- Add modules via the options flow (module type, software version, EE text and MI)
- Add devices via the options flow (MI and module type)
- **Diagnostic sensors** for device configuration:
  - **PowerUp status** for switches and lights (dimmers) - shows the power-up behavior after power loss
  - **Minimum brightness** for dimmers - displays the configured minimum brightness percentage
  - **Timer** for timer actuators - shows the configured timer duration in seconds
  - **Run time** for covers (jalousies) - displays the configured run time in seconds
- **Options flow** allows updating MI and OBJADR without reconfiguration
- **Manual ENUM_ALL trigger** via options flow for device discovery

## Installation

To add the net4home integration to your Home Assistant instance, use this My button:

[![Open your Home Assistant instance and show the dashboard of a Supervisor add-on.](https://my.home-assistant.io/badges/supervisor_addon.svg)](https://my.home-assistant.io/redirect/supervisor_addon/?addon=core_configurator)

If the above My button doesn't work, you can also perform the following steps manually:
1. Copy the `net4home` folder into your Home Assistant configuration directory under `custom_components/`:
   ```
   custom_components/net4home/
   ```
2. Restart Home Assistant
3. Go to Settings → Devices & Services → Add Integration
4. Search for "net4home" and follow the setup wizard

## Configuration

The net4home Bus connector can be auto-discovered by Home Assistant. If an instance was found, it will be shown as Discovered. You can then set it up right away.

### Initial Setup

During the initial setup, you can configure:
- **Host**: IP address or hostname of the Bus connector
- **Port**: TCP port (default: 3478)
- **Password**: Bus password
- **MI**: Module ID (default: 1)
- **OBJADR**: Object address (default: 1)
- **Discover**: Option to trigger ENUM_ALL during setup

### Options

After the integration is set up, you can access the options via:
Settings → Devices & Services → net4home → Configure

In the options, you can:
- **Update MI**: Change the Module ID without reconfiguration
- **Update OBJADR**: Change the Object Address without reconfiguration
- **Trigger ENUM_ALL**: Manually trigger device discovery

## Supported device types 

- **Binary_sensor**: Contact sensors, motion detectors, and other binary inputs
- **Climate**: Thermostat and heating control (UP-TLH)
- **Cover**: Blinds and shutters control (HS-AJ3, HS-AJ4-500, etc.)
- **Light**: Dimmer controls with brightness support (HS-AD3, HS-AD3e, HS-AD1-1x10V)
- **Sensor**: Temperature, humidity, and illuminance sensors
- **Switch**: Relay switches and timer actuators (HS-AR6, UP-AR2, etc.)

> The implemented platforms do not cover the whole functionality of
> the net4home system.  Therefore the net4home integration offers a
> variety of events, device triggers and actions.  They are ideal to be
> used in automation scripts or for the template platforms.

## Diagnostic Information

The integration provides diagnostic sensors for each device type to display configuration information:

### Switches and Lights
- **PowerUp**: Shows the power-up behavior after power loss:
  - AUS (OFF)
  - EIN (ON)
  - wie vor Stromausfall (as before power loss)
  - keine Änderung (no change)
  - EIN mit 100% (ON with 100% - dimmers only)

### Lights (Dimmers)
- **PowerUp**: Power-up behavior (see above)
- **Minimum brightness**: Configured minimum brightness in percent (0-100%)

### Timer Actuators
- **PowerUp**: Power-up behavior (see above)
- **Timer**: Configured timer duration in seconds

### Covers (Jalousies)
- **Run time**: Configured run time in seconds

All diagnostic sensors are automatically updated when the device configuration is read from the bus.

## Setting up devices and entities

The `net4home` hardware modules are represented by Home Assistant _devices_. The periphery of each `net4home` module is represented by Home Assistant _entities_. Peripheries are, for example, the output ports, relays, and variables of a module.

## Requirements

To ensure stable and flawless functioning, the configuration in the net4home configurator should first be revised. 

Actually, everything should already be configured correctly. However, experience shows that we have to do a bit of rework here, as people have often retrofitted or adapted something. Over the years, there are certainly some things that can be tidied up with just a few clicks. This is the most important part of a clean integration. Reworking later is very time-consuming.

> Changes to status changes have no influence on the existing functions.

The **status change** flag must be set for the following actuators. This is important so that the HA always receives information about the current status for display. If, for example, a light is switched by a normal switch, the HA has no information here. There is also the status change, which is communicated to other bus devices.

The following modules are to be checked:
- HS-AR6
- UP-AR2
- HS-AJ3
- HS-AJ4-500
- HS-AD3
- HS-AD3e

## Services

The integration provides the following custom services:

- `net4home.debug_devices`: Log all registered devices to the Home Assistant log
- `net4home.clear_devices`: Clear all stored devices from the integration
- `net4home.enum_all`: Trigger device discovery (ENUM_ALL command)

## Version

Current version: **1.2.0**

## Support

For issues, feature requests, or contributions, please visit the [GitHub repository](https://github.com/anynode/net4home).
