# Manual Testing Requirements for net4home Integration

This document outlines the hardware, software, and procedures needed to manually test the net4home Home Assistant integration.

## Hardware Requirements

### 1. net4home Bus Connector

- Physical hardware device that connects to your network
- Must be accessible via TCP/IP on port 3478 (default)
- Must have a configured password for authentication
- Should have at least one net4home module connected to test device discovery

### 2. net4home Modules (optional but recommended)

For comprehensive testing, it's recommended to have at least one module of each supported type:

- **Binary sensor module** - For contact sensors, motion detectors, etc.
- **Switch/actuator module** - Such as HS-AR6, UP-AR2, HS-AJ3, HS-AJ4-500, HS-AD3, HS-AD3e
- **Light/dimmer module** - For testing dimming and brightness control
- **Cover/blind module** - For testing shutter and blind control
- **Climate/thermostat module** - For testing temperature control
- **Sensor module** - For temperature, humidity, and other sensor readings

## Software Requirements

### 1. Home Assistant Instance

You need a running Home Assistant instance that is compatible with custom components. The integration can be installed on:

- **Home Assistant OS (HassOS)** - Recommended for most users
- **Home Assistant Container (Docker)** - For Docker-based installations
- **Home Assistant Core (Python venv)** - For Python virtual environment installations
- **Home Assistant Supervised** - For supervised installations

### 2. Network Configuration

- Home Assistant and Bus Connector must be on the same network (or reachable via network routing)
- Firewall rules must allow TCP connection to Bus Connector on port 3478
- Ensure network connectivity can be verified (e.g., using ping or telnet)

## Installation Steps

### 1. Install the Integration

1. Copy the `custom_components/net4home/` folder to Home Assistant's `config/custom_components/` directory
2. Restart Home Assistant to load the custom component
3. The integration should appear in HACS (if using HACS) or be available for manual setup

**Note:** Ensure the folder structure is correct:
```
config/
  custom_components/
    net4home/
      __init__.py
      manifest.json
      ... (all other files)
```

### 2. Configure the Integration

1. Navigate to **Settings → Devices & Services → Add Integration**
2. Search for "net4home" or use auto-discovery if the Bus Connector is discoverable
3. Provide the following configuration:
   - **Host**: IP address of the Bus Connector (e.g., `192.168.1.100`)
   - **Port**: 3478 (default port)
   - **Password**: Bus Connector password (configured in net4home configurator)
   - **MI**: Module identifier (default: 65281)
   - **OBJADR**: Object address (default: 32700)

### 3. Add Devices/Modules

After the initial integration setup, you can add devices/modules:

1. Go to the integration's options (click on the integration, then click "Configure")
2. Use the options flow to add devices
3. For each device, provide:
   - Module type
   - Software version
   - EE text
   - MI (Module Identifier)
4. Alternatively, add devices by MI and module type directly

## Pre-Testing Configuration

### 1. net4home Configurator Setup

Before testing, ensure your net4home Bus Connector and modules are properly configured:

1. **Verify Bus Connector Configuration**
   - Open the net4home configurator software
   - Verify the Bus Connector is properly configured
   - Check network settings (IP address, port)
   - Verify password is set correctly

2. **Enable Status Change Flag for Actuators**
   
   The **status change** flag must be set for the following actuators to ensure Home Assistant receives state updates. This is critical for proper state synchronization:
   
   - HS-AR6
   - UP-AR2
   - HS-AJ3
   - HS-AJ4-500
   - HS-AD3
   - HS-AD3e
   
   **Why this matters:** If a light is switched by a physical switch, Home Assistant needs to be notified of the state change. Without the status change flag enabled, Home Assistant will not receive these updates.
   
   **Note:** Changes to status change settings do not affect existing net4home bus functions - they only enable communication to Home Assistant.

## Testing Checklist

### 1. Connection Testing

- [ ] Verify integration successfully connects to Bus Connector
- [ ] Check Home Assistant logs for connection errors
- [ ] Verify password authentication works correctly
- [ ] Test connection stability (leave connected for extended period)
- [ ] Test reconnection after network interruption

**How to verify:**
- Check the integration status in Settings → Devices & Services
- Look for error messages in Home Assistant logs
- Verify the integration shows as "Connected" or "Available"

### 2. Device Discovery

- [ ] Test auto-discovery of Bus Connector (if mDNS/Bonjour is enabled)
- [ ] Verify devices appear in Home Assistant after configuration
- [ ] Check device registry entries are created correctly
- [ ] Verify device names and models are displayed correctly
- [ ] Test manual device addition via options flow

**How to verify:**
- Go to Settings → Devices & Services → net4home
- Check that all configured devices are listed
- Click on a device to see its details and entities

### 3. Platform Testing

#### Binary Sensor
- [ ] Trigger sensor (open/close contact, motion detection, etc.)
- [ ] Verify state updates appear in Home Assistant immediately
- [ ] Check entity state in Developer Tools → States
- [ ] Verify device class is set correctly (opening, motion, etc.)

#### Switch
- [ ] Toggle switch ON via Home Assistant
- [ ] Verify physical device responds
- [ ] Toggle switch OFF via Home Assistant
- [ ] Verify state syncs correctly
- [ ] Test physical switch operation and verify HA state updates

#### Light
- [ ] Turn light ON/OFF via Home Assistant
- [ ] Test dimming control (set brightness level)
- [ ] Verify brightness updates in real-time
- [ ] Test physical dimmer control and verify HA reflects changes

#### Cover
- [ ] Open blinds/shutters via Home Assistant
- [ ] Close blinds/shutters via Home Assistant
- [ ] Test position control (if supported)
- [ ] Verify position updates correctly
- [ ] Test physical control and verify HA state synchronization

#### Climate
- [ ] Set target temperature via Home Assistant
- [ ] Verify current temperature reading
- [ ] Test mode changes (heat, cool, auto, etc.)
- [ ] Verify state updates correctly
- [ ] Test physical thermostat control and verify HA reflects changes

#### Sensor
- [ ] Read temperature sensor values
- [ ] Read humidity sensor values
- [ ] Verify sensor accuracy (compare with known values)
- [ ] Check sensor updates in real-time
- [ ] Verify sensor units are displayed correctly

### 4. State Synchronization

This is a critical test to ensure bidirectional communication works correctly:

- [ ] Change device state via physical switch/button
- [ ] Verify Home Assistant reflects the change within a few seconds
- [ ] Change state via Home Assistant UI
- [ ] Verify device responds correctly
- [ ] Test rapid state changes (toggle quickly)
- [ ] Verify no state is lost or delayed excessively

**Common issues:**
- If physical changes don't appear in HA: Check status change flag in configurator
- If HA changes don't affect device: Check device configuration and MI/OBJADR settings

### 5. Services Testing

Test the custom services provided by the integration:

#### `net4home.debug_devices`
- [ ] Call service via Developer Tools → Services
- [ ] Verify service logs all devices to Home Assistant log
- [ ] Check log output shows device IDs, types, and names correctly

**Service call example:**
```yaml
service: net4home.debug_devices
data:
  entry_id: <your_entry_id>  # Optional, defaults to first entry
```

#### `net4home.clear_devices`
- [ ] Call service to clear device list
- [ ] Verify devices are removed from configuration
- [ ] Verify integration reloads correctly

**Service call example:**
```yaml
service: net4home.clear_devices
data:
  entry_id: <your_entry_id>  # Optional, defaults to first entry
```

#### `net4home.enum_all`
- [ ] Call service to send ENUM_ALL command to bus
- [ ] Verify command is sent successfully
- [ ] Check logs for ENUM_ALL confirmation
- [ ] Verify any discovered devices appear

**Service call example:**
```yaml
service: net4home.enum_all
data:
  entry_id: <your_entry_id>  # Optional, defaults to first entry
```

### 6. Multi-Hub Testing (if applicable)

If you have multiple Bus Connectors:

- [ ] Add second Bus Connector as separate integration entry
- [ ] Verify both integrations work independently
- [ ] Test devices from both hubs simultaneously
- [ ] Verify no conflicts or interference between hubs
- [ ] Test removing one hub while keeping the other active

## Verification Methods

### 1. Home Assistant UI

**Devices & Services Page:**
- Navigate to Settings → Devices & Services
- Find the net4home integration
- Verify integration status shows as "Connected" or "Available"
- Click on the integration to see all devices
- Verify entities appear and update correctly
- Check device info (manufacturer: "net4home", model, etc.)

**Entity States:**
- Go to Developer Tools → States
- Search for entities with `net4home` in the entity ID
- Verify states update when devices change
- Check that state values are correct (ON/OFF, temperature values, etc.)

### 2. Logs

Enable debug logging to get detailed information about integration behavior:

**Add to `configuration.yaml`:**
```yaml
logger:
  default: info
  logs:
    custom_components.net4home: debug
```

**What to monitor in logs:**
- Connection establishment messages
- Packet sending/receiving (if debug enabled)
- Device discovery messages
- State update notifications
- Error messages and exceptions
- Reconnection attempts

**Log locations:**
- Home Assistant logs: `config/home-assistant.log`
- Integration logs: Look for `[net4home]` prefixed messages
- In Home Assistant UI: Settings → System → Logs

**Key log messages to look for:**
- `"Connect with net4home Bus connector at <host>:<port>"` - Successful connection
- `"Credentials to Bus connector sent. Waiting for approval..."` - Authentication in progress
- `"Entity dispatched for <device_id>"` - Device entity created
- `"[BinarySensor] Update <device_id> → ON/OFF"` - State updates

### 3. Developer Tools

Home Assistant provides several developer tools for testing:

**States:**
- Developer Tools → States
- Search for `net4home` entities
- Monitor state changes in real-time
- Verify state values match expected device states

**Services:**
- Developer Tools → Services
- Test `net4home.debug_devices`, `net4home.clear_devices`, `net4home.enum_all`
- Verify services execute without errors
- Check service responses in logs

**Events:**
- Developer Tools → Events
- Listen for net4home events (if any are fired)
- Monitor device triggers and automation events

**YAML:**
- Developer Tools → YAML
- Test service calls via YAML configuration
- Useful for automation testing

## Troubleshooting Resources

### Common Issues and Solutions

#### Connection Issues

**Problem:** Integration cannot connect to Bus Connector

**Solutions:**
- Verify Bus Connector IP address is correct
- Check network connectivity: `ping <bus_connector_ip>`
- Test port accessibility: `telnet <bus_connector_ip> 3478` (should connect)
- Verify firewall allows TCP connection on port 3478
- Check Bus Connector is powered on and network cable is connected
- Verify password is correct in integration configuration

#### Authentication Failures

**Problem:** Connection established but authentication fails

**Solutions:**
- Verify password matches Bus Connector configuration
- Check password doesn't contain special characters that need escaping
- Verify Bus Connector allows connections from Home Assistant's IP
- Check Bus Connector logs (if available) for authentication errors

#### Devices Not Appearing

**Problem:** Integration connects but no devices appear

**Solutions:**
- Use `net4home.enum_all` service to discover devices
- Manually add devices via integration options flow
- Verify devices are properly configured in net4home configurator
- Check MI (Module Identifier) values are correct
- Verify devices are connected to the Bus Connector
- Check Home Assistant logs for device discovery messages

#### State Updates Not Working

**Problem:** Physical device changes don't appear in Home Assistant

**Solutions:**
- Verify "status change" flag is enabled for actuators in net4home configurator
- Check device configuration (MI, OBJADR) is correct
- Verify device is properly connected to bus
- Check Home Assistant logs for state update messages
- Test with `net4home.debug_devices` to verify device is registered

#### State Changes Not Affecting Device

**Problem:** Home Assistant state changes don't control physical device

**Solutions:**
- Verify device MI and OBJADR are correct
- Check device is online and responding in net4home configurator
- Verify device type is correctly configured in integration
- Test device directly with net4home configurator to verify it works
- Check Home Assistant logs for command sending errors

### Network Connectivity Testing

**Test TCP connection:**
```bash
telnet <bus_connector_ip> 3478
```

**Test with Python (if available):**
```python
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
result = s.connect_ex(('<bus_connector_ip>', 3478))
if result == 0:
    print("Port is open")
else:
    print("Port is closed or filtered")
s.close()
```

### Log Analysis

**Key log patterns to search for:**

**Successful connection:**
```
Connect with net4home Bus connector at <host>:<port>
```

**Device updates:**
```
[BinarySensor] Update <device_id> → ON
[Switch] Update <device_id> → OFF
```

**Errors:**
```
Error in async_setup_entry
Error sending data
Connection lost
```

**Reconnection attempts:**
```
Try to reconnect - attempt X/5
```

### Getting Help

If issues persist:

1. **Enable debug logging** (see Logs section above)
2. **Collect relevant log entries** - Focus on errors and warnings
3. **Document device configuration** - MI, OBJADR, module types
4. **Test network connectivity** - Verify basic TCP/IP connection works
5. **Check net4home configurator** - Verify devices work independently
6. **Document steps to reproduce** - What actions cause the issue?

### Additional Resources

- **Home Assistant logs:** `config/home-assistant.log`
- **Integration logs:** Check for `[net4home]` prefixed messages
- **Network connectivity:** Test with `telnet <bus_connector_ip> 3478`
- **Bus Connector status:** Check net4home configurator for device status
- **Home Assistant Community:** For integration-specific support
- **net4home Documentation:** For Bus Connector and module configuration

