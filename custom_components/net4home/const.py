"""Constants for the net4home integration."""

# Domain and network defaults
DOMAIN = "net4home"
DEFAULT_PORT = 3478
SERVICE_TYPE = "_n4hbuscon._tcp.local."

# Packet types (ptypes)
N4HIP_PT_PAKET = 4001               # n4hPacket
N4HIP_PT_PASSWORT_REQ = 4012        # Password handshake request citeturn4file0
N4HIP_PT_OOB_DATA_RAW = 4010        # Out-of-band data

# Security handshake response codes
# NOTE: Verify these values against your Busconnector configuration
N4H_IP_CLIENT_ACCEPTED = 0          # client accepted (placeholder)
N4H_IP_CLIENT_DENIED_WRONG_PASSWORD = -700  # wrong password citeturn6file0
N4H_IP_CLIENT_DENIED_WRONG_SW_VERSION = -701 # wrong software version

# Client DLL version identifier
DLL_REQ_VER = 1                     # must match server’s expected DLL version

# Configuration keys
DEFAULT_MI = 65281
DEFAULT_OBJADR = 32700
CONF_MI = "MI"
CONF_OBJADR = "OBJADR"
