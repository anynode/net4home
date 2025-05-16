# Home Assistant net4home Integration

This repository contains the custom component for integrating net4home devices with Home Assistant.

## Features

- Auto-discovery via Zeroconf (`_net4home_iremote._tcp.local.`)
- Manual configuration (host, port, bus password, MI, OBJADR)
- Binary sensors (contact, motion, etc.)
- (Future) Additional platforms: `sensor`, `switch`, `light`, `climate`, `scene`

## Installation

1. Copy the `net4home` folder into your Home Assistant configuration directory under `custom_components/`:

   ```bash
   cp -R custom_components/net4home/ ~/.homeassistant/custom_components/
