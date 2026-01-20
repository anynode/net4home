# Home Assistant Implementation

## Config flow on the Home Assistant

The config flow handler must ask for the following parameter to connect to the net4home Bus connector.

- Host or IP of the net4home Bus connector
- Port (Default: 3478)
- Password (Configured on the Bus connector side)
- MI of the client (Default: )
- OBJADR of the client (Default: )

### Zeroconf

The net4home Bus connector supports the Zeroconf  configuration. Servers can be discovered by using this protocol. 

The string is “_net4home_iremote._tcp”