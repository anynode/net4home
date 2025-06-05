
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

- Manual configuration (host, port, bus password, MI, OBJADR)
- Binary sensors (contact, motion, etc.)
- Localization support in English, German and Spanish
- Add modules via the options flow (module type, software version, EE text and MI)
- Add devices via the options flow (MI and module type)

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

## Installation

To add the net4home integration to your Home Assistant instance, use this My button:

If the above My button doesn’t work, you can also perform the following steps manually:
1. Copy the `net4home` folder into your Home Assistant configuration directory under `custom_components/`:

## Configuration

The net4home Bus connector can be auto-discovered by Home Assistant. If an instance was found, it will be shown as Discovered. You can then set it up right away.

## Supported device types 

- Binary_sensor
- Climate
- Cover
- Light
- Sensor
- Switch

> The implemented platforms do not cover the whole functionality of
> the net4home system.  Therefore the net4home integration offers a
> variety of events, device triggers and actions.  They are ideal to be
> used in automation scripts or for the template platforms.

## Setting up devices and entites

The `net4home` hardware modules are represented by Home Assistant _devices_. The periphery of each `net4home` module is represented by Home Assistant _entities_. Peripheries are, for example, the output ports, relays, and variables of a module. 