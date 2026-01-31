"""Support for net4home integration."""
import asyncio
import struct
import logging
import binascii
import time
from typing import Tuple, Optional
from datetime import datetime


from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import slugify

from .helpers import register_device_in_registry
from .models import Net4HomeDevice  
from .n4htools import compress_section, decode_d2b, n4h_parse, platine_typ_to_name_a, get_function_and_address_count

from .const import (
    N4H_IP_PORT,
    DEFAULT_MI,
    DEFAULT_OBJADR,
    N4HIP_PT_PAKET,
    N4HIP_PT_PASSWORT_REQ,
    N4HIP_PT_OOB_DATA_RAW,
    MAX_N4H_PAKET_LEN,
    HEADER_SIZE,
    RESERVED1_DEFAULT,
    TYPE8_SIZE,
    SKIP_BYTE_SIZE,
    ADDRESS_SIZE,
    DDATALEN_SIZE,
    TRAILER_SIZE,
    STANDARD_PAYLOAD_LEN,
    D0_SET_IP,
    D0_ENUM_ALL,
    D0_ACK_TYP,
    D0_GET_TYP,
    D0_ACK,
    D0_NOACK,
    D0_SET,
    D0_INC,
    D0_DEC,
    D0_TOGGLE,
    D0_REQ,
    D0_ACTOR_ACK,
    D0_SET_N,
    D0_SENSOR_ACK,
    D0_VALUE_ACK,
    D0_VALUE_REQ,
    D0_STATUS_INFO,
    D0_RD_ACTOR_DATA,
    D0_RD_ACTOR_DATA_ACK,
    D0_RD_SENSOR_DATA_ACK,
    D0_RD_SENSOR_DATA,
    D0_RD_MODULSPEC_DATA,
    D0_RD_MODULSPEC_DATA_ACK,
    D0_WR_MODULSPEC_DATA,
    D0_ENABLE_CONFIGURATION,
    D1_ENABLE_CONFIGURATION_OK_BYTE,
    OUT_HW_NR_IS_ONOFF,
    OUT_HW_NR_IS_TIMER,
    OUT_HW_NR_IS_JAL,
    OUT_HW_NR_IS_DIMMER,
    IN_HW_NR_IS_TEMP,
    IN_HW_NR_IS_HUMIDITY,
    IN_HW_NR_IS_LICHT_ANALOG,
    IN_HW_NR_IS_RF_TAG_READER,
    VAL_IS_MIN_TAG_WORD_SA,
    VAL_IS_MIN_TAG_WORD_SU,
    D10_CONFIG_ENABLE_BIT,
    D10_FCONFIG_ENABLE_BIT,
    BROADCASTIP,
    MI_ENUM_ALL,
    sa2_T8_IP,
    SEND_AS_IP,
    SEND_AS_OBJ_GRP,
    CI_LCD_OPT_BLINK,
    CI_LCD_OPT_BUZZER_ON,
    LCD_STR_LEN_1,
    PLATINE_HW_IS_LCD3,
    PLATINE_HW_IS_BELL2,
    D2_OPT_DNR,
    D2_OPT_INTERRUPT,
)


_LOGGER = logging.getLogger(__name__)

# Receive data from Bus connector
class N4HPacketReceiver:
    """Receive and parse packets from the bus connector."""
    
    def __init__(self):
        """Initialize the packet receiver."""
        self._buffer = bytearray()

    def receive_raw_command(self, data: bytes):
        """Receive raw command data and parse into packets."""
        self._buffer.extend(data)
        packets = []

        while True:
            if len(self._buffer) < 4:
                break  # Not enough data for length header

            payload_len = int.from_bytes(self._buffer[:4], 'little')

            if len(self._buffer) < payload_len + 4:
                break  # Not yet full packet received

            full_packet = self._buffer[:payload_len + 4]
            compressed_payload = full_packet[4:4 + payload_len]

            try:
                decompressed, length = decomp_section_c_exact(
                    compressed_payload,
                    offset=0,
                    length=len(compressed_payload),
                    max_out_len=2048,
                    use_cs=False
                )

                if len(decompressed) >= 2:
                    ptype = struct.unpack('<h', decompressed[0:2])[0]

                    if ptype == N4HIP_PT_PAKET:
                        packets.append((ptype, decompressed))
                    elif ptype == N4HIP_PT_OOB_DATA_RAW:
                        _LOGGER.debug("Raw OOB data packets received.")
                        
                    elif ptype == N4HIP_PT_PASSWORT_REQ:
                        _LOGGER.debug(f"Password ACK empfangen")
                    else:
                        _LOGGER.debug(f"Ignored packet type: {ptype}")

                else:
                    _LOGGER.warning("Dekomprimierter Block zu kurz (< 8 Byte)")

            except Exception as e:
                _LOGGER.error(f"Dekomprimierung fehlgeschlagen: {e}")

            del self._buffer[:payload_len + 4]

        return packets



class DecompressionError(Exception):
    """Exception raised when decompression fails."""
    
    def __init__(self, code: int, detail: int):
        """Initialize decompression error."""
        super().__init__(f"Decompression error {code}, detail: {detail}")
        self.code = code
        self.detail = detail

def decomp_section_c_exact(data: bytes, offset: int, length: int, max_out_len: int, use_cs: bool) -> Tuple[bytes, int]:
    """Decompress a section using the C exact algorithm."""
    result = bytearray()
    cs_calc = 0
    i = offset
    g_pout_pos = 0
    ende = False
    err = False

    while i < length and g_pout_pos < max_out_len and not ende and not err:
        b = data[i]

        if (b & 0xC0) == 0xC0:
            if i + 4 >= length:
                raise DecompressionError(-98, i)
            cs_rx = (
                (data[i + 1] << 24)
                | (data[i + 2] << 16)
                | (data[i + 3] << 8)
                | data[i + 4]
            )
            i += 5
            ende = True
            if use_cs and cs_rx != cs_calc:
                raise DecompressionError(-100, cs_rx - cs_calc)

        elif (b & 0xC0) == 0x00:
            if i + 1 >= length:
                raise DecompressionError(-97, i)
            cclen = ((data[i] << 8) | data[i + 1]) & 0x3FFF
            i += 2
            for j in range(cclen):
                if i < length:
                    val = data[i]
                    result.append(val)
                    cs_calc += val
                    g_pout_pos += 1
                    i += 1
                else:
                    raise DecompressionError(-11, i)

        elif (b & 0xC0) == 0x40:
            if i + 2 >= length:
                raise DecompressionError(-95, i)
            cclen = ((data[i] << 8) | data[i + 1]) & 0x3FFF
            val = data[i + 2]
            i += 3
            for _ in range(cclen):
                result.append(val)
                cs_calc += val
                g_pout_pos += 1

        elif (b & 0xC0) == 0x80:
            raise DecompressionError(-2, i)

        else:
            raise DecompressionError(-5, i)

    if not err and ende and len(result) <= max_out_len:
        return bytes(result), len(result)

    raise DecompressionError(-220, i)


# Send data to Bus connector
class N4HPacketSender:
    """Send packets to the bus connector."""
    
    def __init__(self, writer: asyncio.StreamWriter):
        """Initialize the packet sender with a stream writer."""
        self._writer = writer

    async def send_raw_command(self, ipdst: int, ddata: bytes, objsource: int = 0, mi: int = 65281, type8: int = SEND_AS_OBJ_GRP):
        """
        Send a command to the bus.
        
        Addressing:
        - ipdst: Target address (can be MI or OBJ address)
          * MI address: < 0x8000 (32768), e.g. 0x0099 for module MI0099
          * OBJ address: Can be < 0x8000 (e.g. 27232) or >= 0x8000 for groups
          * Special values: 0x7FFF (32767) = Broadcast, 0xFFFF (65535) = ENUM_ALL
        - mi: MI address of sender (always MI address, < 0x8000)
        - objsource: OBJ address of sender (can be 0 for module commands)
        - type8: Address type (SEND_AS_IP=1 for MI addresses, 0 for OBJ addresses)
        """
        _LOGGER.debug(
            f"[IP] Sending command: "
            f"ipsrc=0x{mi:04X}, ipdst=0x{ipdst:04X}, objsrc={objsource}, "
            f"datalen={len(ddata)}, type8={type8}"
        )
        
        try:
            # === Paketaufbau im Hexstring
            # Header: 8 Bytes
            sendbus = struct.pack('<H', N4HIP_PT_PAKET).hex().upper()  # N4HIP_PT_PAKET (2 Bytes, little endian: 0x0FA1)
            sendbus += struct.pack('<H', RESERVED1_DEFAULT).hex().upper()  # Reserved1 (2 Bytes)
            sendbus += struct.pack('<I', STANDARD_PAYLOAD_LEN).hex().upper()  # Payload-Länge (4 Bytes, little endian)
            # Header Ende (HEADER_SIZE Bytes total)
            
            # === Packet data after header (as expected in n4h_parse)
            # type8: First byte after header (sa2_T8_IP=1 for MI addresses)
            sendbus += f"{type8:02X}"    # type8 (TYPE8_SIZE byte)
            sendbus += "00"              # Skip byte (SKIP_BYTE_SIZE byte, result[1] is skipped)
            
            # === Encode addresses (as expected in n4h_parse: result[2:4], result[4:6], result[6:8])
            sendbus += decode_d2b(mi)    # ipsrc (ADDRESS_SIZE Bytes, little endian)
            sendbus += decode_d2b(ipdst) # ipdest (ADDRESS_SIZE Bytes, little endian)
            sendbus += decode_d2b(objsource) # objsrc (ADDRESS_SIZE Bytes, little endian)

            # === Prepare DDATA: first byte = length, then the actual payload
            full_ddata = bytes([len(ddata)]) + ddata

            # === Pad to MAX_N4H_PAKET_LEN bytes (MAX_N4H_PAKET_LEN * 2 hex characters)
            ddata_hex = full_ddata.hex().upper().ljust(MAX_N4H_PAKET_LEN * 2, "0")
            sendbus += ddata_hex

            # === Abschluss mit csRX, csCalc, length, posb (TRAILER_SIZE bytes)
            sendbus += "00" * TRAILER_SIZE

            # === Kompression & Verpackung
            compressed = compress_section(sendbus)
            final_bytes = bytes.fromhex(compressed)

            # === Logging
            ddata_list = " ".join(ddata.hex()[i:i+2].upper() for i in range(0, len(ddata.hex()), 2))
            log_line = (
                f"SEND: ipsrc=0x{mi:04X}, ipdst=0x{ipdst:04X}, objsrc={objsource}, "
                f"datalen={len(ddata)}, ddata=[{ddata_list}], "
                f"final_bytes={compressed}"
            )
            # _LOGGER.debug(log_line)
            
            # === Senden
            _LOGGER.debug(
                f"[IP] Writing {len(final_bytes)} bytes to connection "
                f"(compressed hex: {final_bytes[:32].hex() if len(final_bytes) >= 32 else final_bytes.hex()})"
            )
            self._writer.write(final_bytes)
            await self._writer.drain()
            _LOGGER.debug(f"[IP] Data sent successfully ({len(final_bytes)} bytes)")

        except Exception as e:
            _LOGGER.error(f"[IP] Error sending data (raw): {e}", exc_info=True)
    
    
class Net4HomeApi:
    """Main API class for net4home bus connector communication."""
    
    def __init__(
        self,
        hass,
        host,
        port: int = N4H_IP_PORT,
        password: str = "",
        mi: int = DEFAULT_MI,
        objadr: int = DEFAULT_OBJADR,
        entry_id: Optional[str] = None,
        entry=None,
        auto_discovery_enabled: bool = True,
    ):
        """Initialize the net4home API."""
        self._hass = hass
        self._entry_id = entry_id
        self._host = host
        self._port = port
        self._password = password
        self._mi = mi
        self._objadr = objadr
        self._reader = None
        self._writer = None
        self._packet_receiver = N4HPacketReceiver()
        self._packet_sender: Optional[N4HPacketSender] = None
        self.devices: dict[str, Net4HomeDevice] = {}
        self._reconnect_enabled = True      
        self._entry = entry
        self._auto_discovery_enabled = auto_discovery_enabled
        
        # Detail retrieval queue management
        self._detail_queue: Optional[asyncio.Queue] = None
        self._detail_queue_task: Optional[asyncio.Task] = None
        self._detail_queue_running = False
        self._detail_rate_limit = 2.0  # Seconds between queries (reduced for more traffic)
        self._detail_initial_delay = 3.0  # Initial delay after start (reduced)
        self._detail_fetch_timeout = 5.0  # Max seconds per device so one stuck device does not block the queue
        
        # ENUM_ALL state management (for small systems: 3 rounds) (for small systems: 3 rounds)
        self._enum_state: int = 0  # 0 = not active, 1-3 = round number
        self._enum_timeout_task: Optional[asyncio.Task] = None
        self._enum_timeout_seconds: float = 0.5  # 500ms timeout (fixed)
        
        # Track MI addresses we've already sent ENUM to (to avoid spam)
        self._enum_sent_to: set[int] = set()
        
        # Track MI devices we've sent auto-discovery queries to (to avoid spam)
        self._discovery_pending: set[str] = set()
        
        # Listener task management
        self._listen_task: Optional[asyncio.Task] = None

    async def async_connect(self):
        """Connect to the net4home bus connector."""
        await self._async_connect_ip()

    async def _async_connect_ip(self):
        """Connect via IP/TCP."""
        self._reader, self._writer = await asyncio.open_connection(self._host, self._port)
        _LOGGER.info(f"Connect with net4home Bus connector at {self._host}:{self._port}")
        
        # "420000000008ac0f0000cd564c77400c000021203732363343423543464343333646323630364344423338443945363135394535401b0000080700000087000000c000000aac"

        packet_bytes = binascii.unhexlify(
            "420000000008ac0f0000cd564c77400c000021203732363343423543464343333646323630364344423338443945363135394535401b0000080700000087000000c000000aac"
        )

        self._writer.write(packet_bytes)
        await self._writer.drain()
        _LOGGER.debug("Credentials to Bus connector sent. Waiting for approval...")

        self._packet_sender = N4HPacketSender(self._writer)

    async def async_reconnect(self, max_attempts: int = 5, base_delay: float = 5.0) -> None:
        """Attempt to reconnect to the bus connector."""
        _LOGGER.debug(f"[IP] Starting reconnect process (max {max_attempts} attempts)")
        
        for attempt in range(1, max_attempts + 1):
            delay = base_delay * attempt
            _LOGGER.warning(f"[IP] Try to reconnect - attempt {attempt}/{max_attempts} in {delay:.1f}s...")

            await asyncio.sleep(delay)

            try:
                # Close existing connection if any
                if self._writer:
                    _LOGGER.debug(f"[IP] Closing existing connection before reconnect")
                    try:
                        if hasattr(self._writer, 'is_closing') and not self._writer.is_closing():
                            self._writer.close()
                            if hasattr(self._writer, 'wait_closed'):
                                await self._writer.wait_closed()
                            _LOGGER.debug(f"[IP] Existing connection closed")
                    except Exception as e:
                        _LOGGER.warning(f"[IP] Error closing existing connection: {e}")
                
                _LOGGER.debug(f"[IP] Attempting to establish new connection (attempt {attempt})")
                await self.async_connect()
                
                # Check connection status
                is_connected = self._writer is not None and not self._writer.is_closing()
                _LOGGER.debug(f"[IP] Connection check: writer={self._writer is not None}, is_closing={self._writer.is_closing() if self._writer else 'N/A'}")
                
                if is_connected:
                    _LOGGER.info(f"[IP] Reconnect successful on attempt {attempt}")

                    _LOGGER.debug(f"[IP] Requesting status for {len(self.devices)} devices")
                    for device in self.devices.values():
                        if device.device_type == "switch":
                            await self.async_request_status(device.device_id)
                        if device.device_type == "light":
                            await self.async_request_status(device.device_id)
                    _LOGGER.debug(f"[IP] Status requests completed")
                    return
                else:
                    _LOGGER.warning(f"[IP] Connection established but status check failed")
            except Exception as e:
                _LOGGER.error(f"[IP] Reconnect failed (Try {attempt}): {e}", exc_info=True)

        _LOGGER.error(f"[IP] Maximale Reconnect-Versuche erreicht. Keine Verbindung zum Bus möglich.")


    async def async_disconnect(self):
        """Disconnect from the net4home bus connector."""
        _LOGGER.debug("[IP] Starting disconnect process")
        
        # Stop reconnect to prevent reconnection attempts
        self._reconnect_enabled = False
        _LOGGER.debug("[IP] Reconnect disabled")
        
        # Cancel ENUM_ALL timeout if active
        if self._enum_timeout_task:
            _LOGGER.debug("[IP] Cancelling ENUM_ALL timeout task")
            self._enum_timeout_task.cancel()
            try:
                await self._enum_timeout_task
            except asyncio.CancelledError:
                pass
            self._enum_timeout_task = None
        self._enum_state = 0
        
        # Cancel and wait for listener task to finish
        if self._listen_task and not self._listen_task.done():
            _LOGGER.debug("[IP] Cancelling listener task")
            self._listen_task.cancel()
            try:
                # Wait for task to finish with timeout
                await asyncio.wait_for(self._listen_task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                _LOGGER.debug("[IP] Listener task cancelled or timed out")
            except Exception as e:
                _LOGGER.warning(f"[IP] Error waiting for listener task: {e}")
            self._listen_task = None
        
        # Close writer connection with timeout
        if self._writer:
            _LOGGER.debug("[IP] Closing writer connection")
            try:
                self._writer.close()
                if hasattr(self._writer, 'wait_closed'):
                    # Use timeout to prevent blocking
                    try:
                        await asyncio.wait_for(self._writer.wait_closed(), timeout=2.0)
                        _LOGGER.debug("[IP] Connection to net4home Bus connector closed successfully")
                    except asyncio.TimeoutError:
                        _LOGGER.warning("[IP] Timeout waiting for connection to close, forcing close")
                        # Force close if timeout
                        if hasattr(self._writer, 'transport') and self._writer.transport:
                            try:
                                self._writer.transport.abort()
                            except Exception:
                                pass
                else:
                    _LOGGER.debug("[IP] Writer closed (no wait_closed method)")
            except Exception as e:
                _LOGGER.warning(f"[IP] Error closing connection: {e}", exc_info=True)
            finally:
                self._writer = None
        else:
            _LOGGER.debug("[IP] No writer to close")
        
        # Clean up reader
        if self._reader:
            try:
                if hasattr(self._reader, 'transport') and self._reader.transport:
                    self._reader.transport.abort()
            except Exception as e:
                _LOGGER.debug(f"[IP] Error closing reader transport: {e}")
            self._reader = None
        
        _LOGGER.debug("[IP] Disconnect process completed")

    async def async_listen(self):
        """Listen for incoming packets from the bus connector."""
        _LOGGER.debug("[IP] Start listening for bus packets")
        
        packet_count = 0
        no_data_count = 0
        while True:
                try:
                    _LOGGER.debug(f"[IP] Waiting for data from reader...")
                    
                    data = await self._reader.read(4096)
                    
                    if not data:
                        no_data_count += 1
                        _LOGGER.warning(
                            f"[IP] Connection to net4home Bus connector closed "
                            f"(no data received, count: {no_data_count})"
                        )
                        
                        if self._reconnect_enabled:
                            _LOGGER.debug(f"[IP] Reconnect enabled, attempting reconnect...")
                            await self.async_reconnect()
                        else:
                            _LOGGER.info(f"[IP] Reconnect disabled – leaving listener")
                            break
                    else:
                        no_data_count = 0  # Reset counter on successful read
                        packet_count += 1
                        _LOGGER.info(
                            f"[IP] Received {len(data)} bytes "
                            f"(packet #{packet_count}, hex: {data[:min(32, len(data))].hex()})"
                        )
                        
                        # Process the received data
                        packets = self._packet_receiver.receive_raw_command(data)
                        _LOGGER.debug(
                            f"[IP] Packet receiver processed data: "
                            f"{len(packets)} packets extracted from {len(data)} bytes"
                        )
                        
                        for ptype, payload in packets:
                            try:
                                ret, paket = n4h_parse(payload)
                            except Exception as e:
                                _LOGGER.error(f"[IP] Parsing error: {e}", exc_info=True)
                                continue

                            if paket is None:
                                _LOGGER.warning(
                                    f"[IP] Unable to parse a legit bus packet - {ret} - "
                                    f"{payload[:32].hex() if len(payload) >= 32 else payload.hex()}"
                                )
                                continue

                            if paket.ddatalen != 0:
                                # Identify the action what we have to do
                                b0 = paket.ddata[0]
                                _LOGGER.debug(f"Processing packet: b0={b0} (0x{b0:02X}), ddatalen={paket.ddatalen}, ipsrc={paket.ipsrc:04X}, objsrc={paket.objsrc}")
                                
                                # Auto-discover unknown MI devices that are sending packets
                                # If we receive a packet from an MI device we don't know about, query it
                                if self._auto_discovery_enabled and paket.ipsrc > 0 and paket.ipsrc < 0xFF00:  # Valid MI address range
                                    mi_device_id = f"MI{paket.ipsrc:04X}"
                                    if mi_device_id not in self.devices and mi_device_id not in self._discovery_pending:
                                        # Unknown MI device - send discovery query (only once per device)
                                        _LOGGER.info(f"Auto-discovering unknown MI device {mi_device_id} (detected from packet b0=0x{b0:02X})")
                                        self._discovery_pending.add(mi_device_id)
                                        try:
                                            await self._packet_sender.send_raw_command(
                                                ipdst=paket.ipsrc,
                                                ddata=bytes([D0_ENABLE_CONFIGURATION, 0xD3, 0x00]),
                                                objsource=self._objadr,
                                                mi=self._mi,
                                                type8=SEND_AS_IP,
                                            )
                                            _LOGGER.debug(f"Sent D0_ENABLE_CONFIGURATION to {mi_device_id} for auto-discovery")
                                        except Exception as e:
                                            _LOGGER.error(f"Failed to send discovery query to {mi_device_id}: {e}")
                                
                                # UP-TLH/UP-T: Commands sent TO the device (by any bus participant) – update from ipdest
                                if b0 == D0_SET and len(paket.ddata) >= 3:
                                    device = self._find_up_tlh_by_objadr(paket.ipdest)
                                    if device:
                                        # ddata[1] = Sollwert_High, ddata[2] = Sollwert_Low (Doku High/Low)
                                        sollwert_temp = (paket.ddata[1] * 256 + paket.ddata[2]) / 10.0
                                        device.targettemp = sollwert_temp
                                        dispatch_id = device.device_id.upper()
                                        _LOGGER.debug(f"D0_SET to OBJ{paket.ipdest}: setpoint {sollwert_temp}°C for {dispatch_id}")
                                        async_dispatcher_send(self._hass, f"net4home_update_{dispatch_id}", {"targettemp": sollwert_temp})
                                        async_dispatcher_send(self._hass, f"net4home_update_{dispatch_id}_targettemp", sollwert_temp)
                                
                                if b0 == D0_WR_MODULSPEC_DATA and len(paket.ddata) >= 6 and paket.ddata[1] == 0xF0:
                                    device_id_mi = f"MI{paket.ipdest:04X}"
                                    device = self.get_known_device(device_id_mi)
                                    if device and device.model in ("UP-TLH", "UP-T"):
                                        presetday = (paket.ddata[2] * 256 + paket.ddata[3]) / 10.0
                                        presetnight = (paket.ddata[4] * 256 + paket.ddata[5]) / 10.0
                                        device.presetday = presetday
                                        device.presetnight = presetnight
                                        dispatch_id = device.device_id.upper()
                                        _LOGGER.debug(f"D0_WR_MODULSPEC_DATA 0xF0 to MI{paket.ipdest:04X}: presetday={presetday}°C, presetnight={presetnight}°C for {dispatch_id}")
                                        async_dispatcher_send(self._hass, f"net4home_update_{dispatch_id}", {"presetday": presetday, "presetnight": presetnight})
                                        async_dispatcher_send(self._hass, f"net4home_update_{dispatch_id}_presetday", presetday)
                                        async_dispatcher_send(self._hass, f"net4home_update_{dispatch_id}_presetnight", presetnight)
                                
                                if b0 == D0_SET_N and len(paket.ddata) >= 2:
                                    device = self._find_up_tlh_by_objadr(paket.ipdest)
                                    if device:
                                        status = paket.ddata[1]
                                        heat_active = (status & 1) != 0
                                        cool_active = (status & 2) != 0
                                        if heat_active and cool_active:
                                            hvac_mode = "heat_cool"
                                        elif heat_active:
                                            hvac_mode = "heat"
                                        elif cool_active:
                                            hvac_mode = "cool"
                                        else:
                                            hvac_mode = "off"
                                        dispatch_id = device.device_id.upper()
                                        update_data = {"hvac_mode": hvac_mode, "heat_active": heat_active, "cool_active": cool_active}
                                        _LOGGER.debug(f"D0_SET_N to OBJ{paket.ipdest}: hvac_mode={hvac_mode} for {dispatch_id}")
                                        async_dispatcher_send(self._hass, f"net4home_update_{dispatch_id}", update_data)
                                
                                # Discovered a module, maybe we know it (enum all or enum for a single module)
                                if b0 == D0_ACK_TYP:
                                    # Reset ENUM_ALL timeout if enumeration is active
                                    if self._enum_state > 0 and self._enum_timeout_task:
                                        self._enum_timeout_task.cancel()
                                        self._enum_timeout_task = asyncio.create_task(
                                            self._wait_for_timeout()
                                        )
                                        _LOGGER.debug(f"[ENUM_ALL] Timer reset due to D0_ACK_TYP (round {self._enum_state})")
                                    
                                    #  b0 -> D0_ACK_TYP
                                    #  b1 -> Modultyp
                                    #  b2 -> ns 
                                    #  b3 -> na (number of channels)
                                    #  b4 ->
                                    #  b5 -> IPK Version (lo)
                                    #  b6 ->
                                    #  b7 -> Version (hi)
                                    #  b8 -> Version (lo)
                                    #  b9 -> IPK Version (hi)
                                    # b10 ->  Config Status 

                                    b10 = paket.ddata[10] 
                                    
                                    device_id = f"MI{paket.ipsrc:04X}"
                                    objadr = None 
                                    model = platine_typ_to_name_a(paket.ddata[1])
                                    sw_version = ""
                                    name = device_id
                                    device_type="module"
                                
                                    major = paket.ddata[9]
                                    subsystem = paket.ddata[5]
                                    minor_raw1 = paket.ddata[7]
                                    minor_raw = paket.ddata[8]
                                    sw_version = f"{major}.{'%02d' % subsystem}/{minor_raw1}.{minor_raw:02d}"                            
                                    
                                    if b10 & D10_CONFIG_ENABLE_BIT:
                                        mode = "config"
                                    elif b10 & D10_FCONFIG_ENABLE_BIT:    
                                        mode = "factory"
                                    else:    
                                        mode = "normal"
                                    
                                    # UP-TLH and UP-T are climate modules with temperature/comfort sensors
                                    if model in ("UP-TLH", "UP-T"):
                                        device_type="climate"
                                        # IMPORTANT: objadr will be set later from the 0xF1 packet (D0_RD_MODULSPEC_DATA_ACK)
                                        # Initially set to None so sensors are not created with wrong objadr
                                        objadr=None
                                    
                                    # UP-RF is an RF-Key reader module
                                    elif model in ("UP-RF", "UP-RF-S4AR1"):
                                        device_type="rf_reader"
                                        objadr=paket.objsrc
                                    
                                    # HS-Safety is an alarm control panel module
                                    elif model == "HS-Safety":
                                        device_type="alarm_control_panel"
                                        objadr=paket.objsrc
                                    
                                    # HS-Time is a time control module with sunrise/sunset sensors
                                    elif model == "HS-Time":
                                        device_type="sensor"  # Treated as sensor module
                                        # objadr will be set later from the 0xFF packet (D0_RD_MODULSPEC_DATA_ACK)
                                        objadr=None
                                        
                                    # _LOGGER.debug(f"ACK_TYP received for device: {device_id} ({device_type}) ({model}) ({objadr}) ({sw_version})")

                                    # Extract module type information from D0_ACK_TYP before registration
                                    module_type = None
                                    ns = None
                                    na = None
                                    nm = None
                                    ng = None
                                    
                                    # Check if we can access index 9 (IPK version) for 16-bit nm calculation
                                    svwIPK = 0
                                    if len(paket.ddata) > 9:
                                        svwIPK = paket.ddata[9]  # IPK version (hi)
                                    
                                    if len(paket.ddata) > 1:
                                        module_type = paket.ddata[1]  # Module type
                                    if len(paket.ddata) > 2:
                                        ns = paket.ddata[2]  # Number of sensors
                                    if len(paket.ddata) > 3:
                                        na = paket.ddata[3]  # Number of actuators
                                    if len(paket.ddata) > 12:
                                        ng = paket.ddata[12]  # Group table length
                                    if len(paket.ddata) > 13:
                                        nm = paket.ddata[13]  # ModuleSpec table length
                                        # Consider 16-bit flag for ModulSpec (from NET3)
                                        if svwIPK >= 3:  # from NET3
                                            if len(paket.ddata) > 11 and (paket.ddata[11] & 0x01):  # D11_ACK_TYP_MS16BIT
                                                nm = nm * 4
                                    
                                    try:
                                        await register_device_in_registry(
                                            hass=self._hass,
                                            entry=self._entry,
                                            device_id=device_id,
                                            name=name,
                                            model=model,
                                            sw_version=sw_version,
                                            hw_version="",
                                            device_type=device_type, 
                                            via_device="",
                                            api=self,
                                            objadr=objadr,
                                            module_type=module_type,
                                            ns=ns,
                                            na=na,
                                            nm=nm,
                                            ng=ng,
                                        )
                                        
                                        # Remove from discovery pending set (auto-discovery was successful)
                                        self._discovery_pending.discard(device_id)
                                        
                                        # Module type information is already stored during registration
                                        # Just verify it was set correctly and log
                                        device = self.devices.get(device_id)
                                        if device:
                                            # Update if not already set (shouldn't happen, but safety check)
                                            if device.module_type is None and module_type is not None:
                                                device.module_type = module_type
                                            if device.ns is None and ns is not None:
                                                device.ns = ns
                                            if device.na is None and na is not None:
                                                device.na = na
                                            if device.nm is None and nm is not None:
                                                device.nm = nm
                                            if device.ng is None and ng is not None:
                                                device.ng = ng
                                            
                                            if len(paket.ddata) < 14:
                                                _LOGGER.debug(
                                                    f"D0_ACK_TYP packet shorter than expected for {device_id}: "
                                                    f"{len(paket.ddata)} bytes (expected 14+), using defaults for missing fields"
                                                )
                                            
                                            _LOGGER.debug(
                                                f"Stored module info for {device_id}: "
                                                f"type={device.module_type}, ns={device.ns}, na={device.na}, "
                                                f"ng={device.ng}, nm={device.nm}, packet_len={len(paket.ddata)}"
                                            )
                                        
                                        # Request sensor data for UP-RF devices to discover sensor object addresses
                                        # (These requests are fast and can be done immediately)
                                        if device_type == "rf_reader":
                                            # Request sensor data for channels 0 and 1 (command 1 and command 2)
                                            await self.async_request_sensor_data(device_id, channel=0)
                                            await self.async_request_sensor_data(device_id, channel=1)
                                        
                                        # Add device to detail queue (for further detail queries)
                                        await self.async_queue_device_for_details(device_id)
                                            
                                    except Exception as e:
                                        _LOGGER.error(f"Error during registration of device (module) {device_id}: {e}")

                                elif b0 == D0_ACTOR_ACK:
                                    # For UP-TLH/UP-T: D0_ACTOR_ACK comes from OBJ addresses (objadr, objadr+1, objadr+2)
                                    # But sensors are created on the MI device, so we need to find the MI device
                                    device_id = f"MI{paket.ipsrc:04X}"
                                    device = self.get_known_device(device_id)

                                    if not device:
                                        # Fallback: Versuche OBJ-Device
                                        device_id = f"OBJ{paket.objsrc:05d}"
                                        device = self.get_known_device(device_id)
                                        if not device:
                                            # Unknown MI device: Try to discover it by sending ENUM command
                                            # This can happen if a module sends D0_ACTOR_ACK before being discovered by ENUM_ALL
                                            mi_address = paket.ipsrc
                                            
                                            # Rate limit: Only send ENUM once per MI address
                                            if mi_address not in self._enum_sent_to:
                                                self._enum_sent_to.add(mi_address)
                                                _LOGGER.info(f"D0_ACTOR_ACK from unknown MI device {device_id}, sending ENUM to discover it")
                                                try:
                                                    # Send ENUM command to this specific module
                                                    await self._packet_sender.send_raw_command(
                                                        ipdst=mi_address,
                                                        ddata=bytes([D0_ENUM_ALL]),
                                                        objsource=0,
                                                        mi=self._mi,
                                                        type8=SEND_AS_IP,
                                                    )
                                                    _LOGGER.debug(f"Sent ENUM command to {device_id} (MI address 0x{mi_address:04X})")
                                                except Exception as e:
                                                    _LOGGER.error(f"Error sending ENUM to {device_id}: {e}")
                                                    # Remove from set on error so we can retry later
                                                    self._enum_sent_to.discard(mi_address)
                                            else:
                                                _LOGGER.debug(f"D0_ACTOR_ACK from unknown MI device {device_id}, ENUM already sent, waiting for D0_ACK_TYP")
                                            continue

                                    # For multi-channel actor modules (e.g. HS-AD1-1x10V): D0_ACTOR_ACK refers to the channel (OBJ), not the module (MI).
                                    # Commands go to the actor (OBJ); UP-TLH/UP-T (climate) keep using MI and are unchanged.
                                    if device.device_type == 'module':
                                        obj_device_id = f"OBJ{paket.objsrc:05d}"
                                        obj_device = self.get_known_device(obj_device_id)
                                        if obj_device:
                                            device_id = obj_device_id
                                            device = obj_device
                                        else:
                                            continue  # OBJ channel not yet registered, skip

                                    if device.device_type == 'rf_reader':
                                        continue  # UP-RF: no actor entities, RF-Key updates via D0_VALUE_ACK

                                    # _LOGGER.debug(f"D0_ACTOR_ACK for *** {device_id}: {device.device_type} - obj {device.objadr} - {paket.objsrc}")

                                    if device.device_type == 'climate':
                                        # For UP-TLH/UP-T: Determine sensor type based on objadr relationship
                                        # According to documentation: objadr + 0 = setpoint (targettemp), objadr + 1 = day value (presetday), objadr + 2 = night value (presetnight)
                                        # paket.objsrc is the object address from which the packet comes
                                        sensor_key = None
                                        if device.objadr is not None:
                                            if paket.objsrc == device.objadr:
                                                sensor_key = "targettemp"
                                            elif paket.objsrc == device.objadr + 1:
                                                sensor_key = "presetday"
                                            elif paket.objsrc == device.objadr + 2:
                                                sensor_key = "presetnight"

                                        if sensor_key:
                                            # According to documentation: Setpoint_Temperature = (ddata[1] + ddata[2] * 256) / 10.0 (Little Endian)
                                            # ddata[1] = Setpoint Low, ddata[2] = Setpoint High
                                            # BUT: In practice the byte order seems to be swapped
                                            # Test: 20°C = 200 = 0x00C8 (Little Endian: lo=0xC8, hi=0x00)
                                            # But we see 5,120.0°C = 51,200 = 0xC800 (hi=0xC8, lo=0x00)
                                            # This means: ddata[1] contains the High Byte, ddata[2] contains the Low Byte
                                            # Correct calculation: (ddata[2] + ddata[1] * 256) / 10.0
                                            if len(paket.ddata) >= 4:
                                                # The bytes are actually swapped compared to the documentation
                                                # ddata[1] = High Byte, ddata[2] = Low Byte
                                                hi = paket.ddata[1]  # Actually High Byte
                                                lo = paket.ddata[2]  # Actually Low Byte
                                                # Calculation: (Low Byte + High Byte * 256) / 10.0
                                                temp = (lo + hi * 256) / 10.0
                                                
                                                # ddata[3] contains status bits: Bit 0 = heating controller, Bit 1 = cooling controller
                                                status_byte = paket.ddata[3]
                                                heat_active = (status_byte & 0x01) != 0  # Bit 0
                                                cool_active = (status_byte & 0x02) != 0  # Bit 1
                                                
                                                # Determine HVAC Mode based on status bits
                                                if heat_active and cool_active:
                                                    hvac_mode = "heat_cool"
                                                elif heat_active:
                                                    hvac_mode = "heat"
                                                elif cool_active:
                                                    hvac_mode = "cool"
                                                else:
                                                    hvac_mode = "off"
                                                
                                                _LOGGER.debug(f"D0_ACTOR_ACK for {device_id}: {sensor_key} = {temp}°C, status=0x{status_byte:02X} (heat={heat_active}, cool={cool_active}, mode={hvac_mode})")
                                                if sensor_key == "targettemp":
                                                    device.targettemp = temp
                                                elif sensor_key == "presetday":
                                                    device.presetday = temp
                                                elif sensor_key == "presetnight":
                                                    device.presetnight = temp
                                                # Send updates to the MI device (where sensors were created); use uppercase for dispatcher key
                                                dispatch_id = device_id.upper()
                                                update_data = {
                                                    sensor_key: temp,
                                                    "hvac_mode": hvac_mode,
                                                    "heat_active": heat_active,
                                                    "cool_active": cool_active
                                                }
                                                _LOGGER.debug(f"Climate update {dispatch_id}: hvac_mode={hvac_mode}, {sensor_key}={temp}")
                                                async_dispatcher_send(self._hass, f"net4home_update_{dispatch_id}", update_data)
                                                async_dispatcher_send(self._hass, f"net4home_update_{dispatch_id}_{sensor_key}", temp)
                                            else:
                                                _LOGGER.warning(f"D0_ACTOR_ACK packet too short for climate: {len(paket.ddata)} bytes, expected at least 4")
                                        else:
                                            _LOGGER.debug(f"D0_ACTOR_ACK for {device_id}: No matching sensor type (objadr={device.objadr}, paket.objsrc={paket.objsrc})")

                                    else:
                                        # Check if packet has enough data (need at least 3 bytes)
                                        if len(paket.ddata) < 3:
                                            _LOGGER.warning(f"D0_ACTOR_ACK packet too short: {len(paket.ddata)} bytes, expected at least 3")
                                            continue
                                        
                                        dispatch_key = f"net4home_update_{device_id.upper()}"
                                        if device.device_type == 'switch':
                                            is_on = paket.ddata[2] == 1
                                            _LOGGER.debug(f"D0_ACTOR_ACK for {device_id}: {'ON' if is_on else 'OFF'}")
                                            async_dispatcher_send(self._hass, dispatch_key, is_on)
                                            
                                        elif device.device_type == 'timer':
                                            is_on = paket.ddata[2] == 1
                                            _LOGGER.debug(f"D0_ACTOR_ACK for {device_id}: {'ON' if is_on else 'OFF'}")
                                            async_dispatcher_send(self._hass, dispatch_key, is_on)
                                            
                                        elif device.device_type == 'cover':
                                            is_closed = paket.ddata[2] != 1 
                                            _LOGGER.debug(f"D0_ACTOR_ACK für {device_id}: {'CLOSED' if is_closed else 'OPEN'}")
                                            async_dispatcher_send(self._hass, dispatch_key, is_closed)

                                        elif device.device_type == 'light':
                                            is_on = paket.ddata[2] >> 7
                                            brightness_value = round((paket.ddata[2] & 0x7F) * 255 / 100)
                                            _LOGGER.debug(f"STATUS_INFO_ACK for {device_id}: {'ON' if is_on else 'OFF'} {round((paket.ddata[2] & 0x7F))}%")
                                            async_dispatcher_send(self._hass, dispatch_key, {"is_on": is_on, "brightness": brightness_value})

                                        elif device.device_type == 'binary_sensor':
                                            is_closed = paket.ddata[2] != 1 
                                            _LOGGER.debug(f"STATUS_INFO_ACK for {device_id}: {'CLOSED' if is_closed else 'OPEN'}")
                                            async_dispatcher_send(self._hass, dispatch_key, is_closed)
                                            
                                        else:
                                            # Only log warning for unhandled device types
                                            _LOGGER.warning(f"Unhandled device type in D0_ACTOR_ACK: {device.device_type} ({device.model}) for {device_id}")

                                elif b0 == D0_RD_ACTOR_DATA_ACK:
                                    _LOGGER.debug(f"D0_RD_ACTOR_DATA_ACK identified Type: {paket.ddata[2]}")
                                    
                                    b1  = paket.ddata[1] + 1 # channel
                                    b2  = paket.ddata[2]     # actor type
                                    b8  = paket.ddata[8]     # OBJ hi
                                    b9  = paket.ddata[9]     # OBJ lo
                                    

                                    device_id = f"OBJ{(b8*256+b9):05d}"
                                    objadr = (b8 << 8) + b9
                                    via_device = f"MI{paket.ipsrc:04X}"
                                    is_dimmer = False
                                    is_jal = False

                                    device_obj = self.devices.get(via_device)
                                    
                                    # Wenn das MI-Device nicht existiert, erstelle es automatisch
                                    # (kann passieren, wenn die Abfrage von einem externen Programm kommt)
                                    if not device_obj:
                                        _LOGGER.warning(
                                            f"MI device {via_device} not found when registering OBJ device {device_id}. "
                                            f"Creating MI device automatically."
                                        )
                                        # Erstelle ein minimales MI-Device
                                        await register_device_in_registry(
                                            hass=self._hass,
                                            entry=self._entry,
                                            device_id=via_device,
                                            name=via_device,
                                            model="Unknown",
                                            sw_version="",
                                            hw_version="",
                                            device_type="module",
                                            via_device="",
                                            api=self,
                                            objadr=None,
                                        )
                                        device_obj = self.devices.get(via_device)
                                        if device_obj:
                                            _LOGGER.info(f"Created MI device {via_device} for OBJ device {device_id}")
                                        else:
                                            _LOGGER.error(f"Failed to create MI device {via_device}")
                                            continue
                                    
                                    # Check module type for dimmer detection
                                    if device_obj and device_obj.model in ('HS-AD1-1x10V', 'HS-AD3e', 'HS-AD3'):
                                        is_dimmer = True
                                        _LOGGER.debug(f"Dimmer module detected: {device_obj.model} for {device_id}, b2={b2}")
                                        
                                    if device_obj and device_obj.model in ('HS-AJ3', 'HS-AJ1', 'HS-AJ4-500', 'HS-AJ3-6'):
                                        is_jal = True
                                    
                                    # Also check if the via_device already has dimmer devices (then it is a dimmer module)
                                    if via_device in self.devices:
                                        via_device_obj = self.devices[via_device]
                                        # Check if there are already dimmer channels
                                        for existing_device in self.devices.values():
                                            if existing_device.via_device == via_device and existing_device.device_type == "light":
                                                is_dimmer = True
                                                _LOGGER.debug(f"Dimmer module detected through existing Light entities for {device_id}, b2={b2}")
                                                break
                                    
                                    # Timer entries have priority and are detected regardless of module type
                                    # IMPORTANT: Timer check must occur BEFORE dimmer check
                                    # Timer is also detected on dimmer modules if b2 == OUT_HW_NR_IS_TIMER
                                    if b2 == OUT_HW_NR_IS_TIMER:
                                        _LOGGER.info(f"OUT_HW_NR_IS_TIMER identified: {device_id} (module: {device_obj.model if device_obj else 'unknown'}, is_dimmer={is_dimmer}, b2={b2})")

                                        # Module details
                                        b3  = paket.ddata[3]     # time1 hi
                                        b4  = paket.ddata[4]     # time1 lo
                                        b5  = paket.ddata[5]     # Power Up (0=OFF, 1=ON, 2=ASBEFORE, 3=NoChange, 4=ON100% ) 
                                        b6  = paket.ddata[6]     # min
                                        b7  = paket.ddata[7]     # Status update
                                        b10 = paket.ddata[10]     # time2 hi
                                        b11 = paket.ddata[11]    # time2 lo
                                        b12 = paket.ddata[12]    # inverted
                                        t1  = b3*256+b4 # time1

                                        try:
                                            await register_device_in_registry(
                                                hass=self._hass,
                                                entry=self._entry,
                                                device_id=device_id,
                                                name = f"CH{b1}_{device_id[3:]}",
                                                model="Timer",
                                                sw_version="",
                                                hw_version="",
                                                device_type="switch",
                                                via_device=via_device,
                                                api=self,
                                                objadr=objadr,
                                                send_state_changes = bool(b7),
                                            )
                                            # Store powerup status and timer time1 in device (also for already existing devices)
                                            if device_id in self.devices:
                                                self.devices[device_id].powerup_status = b5
                                                self.devices[device_id].timer_time1 = t1
                                                _LOGGER.debug(f"Powerup status for {device_id} stored: {b5}, Timer time1: {t1}s")
                                                # Sende Signal zur Aktualisierung der Diagnose-Sensoren
                                                async_dispatcher_send(self._hass, f"net4home_diagnostic_update_{device_id}")
                                            else:
                                                _LOGGER.warning(f"Device {device_id} not found in api.devices, cannot store powerup status")
                                            _LOGGER.debug(f"OUT_HW_NR_IS_TIMER identified: {device_id} - CH{b1} t1{t1} - State change {bool(b7)} - Powerup: {b5}")
                                        except Exception as e:
                                            _LOGGER.error(f"Error during registration of TIMER device (channel) {device_id}: {e}")
                                    
                                    # Wenn OUT_HW_NR_IS_ONOFF und is_dimmer, dann als Dimmer behandeln
                                    elif b2 == OUT_HW_NR_IS_ONOFF and is_dimmer:
                                        _LOGGER.debug(f"OUT_HW_NR_IS_ONOFF identified as DIMMER: {device_id}")
                                        
                                        # Module details
                                        b3  = paket.ddata[3]     # time1 hi
                                        b4  = paket.ddata[4]     # time1 lo
                                        b5  = paket.ddata[5]     # Power Up (0=OFF, 1=ON, 2=ASBEFORE, 3=NoChange, 4=ON100% ) 
                                        b6  = paket.ddata[6]     # min
                                        b7  = paket.ddata[7]     # Status update
                                        b10 = paket.ddata[10]    # time2 hi
                                        b11 = paket.ddata[11]    # time2 lo
                                        b12 = paket.ddata[12]    # inverted
                                        t1  = b3*256+b4 # time1

                                        try:
                                            await register_device_in_registry(
                                                hass=self._hass,
                                                entry=self._entry,
                                                device_id=device_id,
                                                name = f"CH{b1}_{device_id[3:]}",
                                                model="Licht",
                                                sw_version="",
                                                hw_version="",
                                                device_type="light",
                                                via_device=via_device,
                                                api=self,
                                                objadr=objadr,
                                                send_state_changes = bool(b7),
                                            )
                                            # Store powerup status and MinHell in device (also for already existing devices)
                                            if device_id in self.devices:
                                                self.devices[device_id].powerup_status = b5
                                                self.devices[device_id].min_hell = b6
                                                _LOGGER.debug(f"Powerup status for {device_id} saved: {b5}, MinHell: {b6}%")
                                                # Sende Signal zur Aktualisierung der Diagnose-Sensoren
                                                async_dispatcher_send(self._hass, f"net4home_diagnostic_update_{device_id}")
                                            else:
                                                _LOGGER.warning(f"Device {device_id} not found in api.devices, cannot store powerup status")
                                            _LOGGER.debug(f"OUT_HW_NR_IS_ONOFF (as DIMMER) identified: {device_id} - CH{b1} t1{t1} - State change {bool(b7)} - Powerup: {b5} - MinHell: {b6}%")
                                        except Exception as e:
                                            _LOGGER.error(f"Error during registration of DIMMER device (channel) {device_id}: {e}", exc_info=True)

                                    # We have a classic switch with ON/OFF feature
                                    # IMPORTANT: Only for real ON/OFF actors, NOT for dimmers (they have OUT_HW_NR_IS_DIMMER)
                                    elif b2 == OUT_HW_NR_IS_ONOFF and not is_dimmer:
                                        _LOGGER.debug(f"OUT_HW_NR_IS_ONOFF identified: {device_id}")

                                        # Module details
                                        b3  = paket.ddata[3]     # time1 hi
                                        b4  = paket.ddata[4]     # time1 lo
                                        b5  = paket.ddata[5]     # Power Up (0=OFF, 1=ON, 2=ASBEFORE, 3=NoChange, 4=ON100% ) 
                                        b6  = paket.ddata[6]     # min
                                        b7  = paket.ddata[7]     # Status update
                                        b10 = paket.ddata[8]     # time2 hi
                                        b11 = paket.ddata[9]     # time2 lo
                                        b12 = paket.ddata[10]    # inverted
                                        t1  = b3*256+b4 # time1
                                        
                                        model="Schalter"
                                        device_type="switch"
                                        
                                        try:
                                            _LOGGER.debug(
                                                f"Registering OBJ device {device_id} with via_device={via_device}, "
                                                f"parent_exists={via_device in self.devices}"
                                            )
                                            await register_device_in_registry(
                                                hass=self._hass,
                                                entry=self._entry,
                                                device_id=device_id,
                                                name = f"CH{b1}_{device_id[3:]}",
                                                model=model,
                                                sw_version="",
                                                hw_version="",
                                                device_type=device_type,
                                                via_device=via_device,
                                                api=self,
                                                objadr=objadr,
                                                send_state_changes = bool(b7),
                                            )
                                            # Store powerup status in device (also for already existing devices)
                                            if device_id in self.devices:
                                                self.devices[device_id].powerup_status = b5
                                                _LOGGER.debug(f"Powerup status for {device_id} stored: {b5}")
                                                # Sende Signal zur Aktualisierung der Diagnose-Sensoren
                                                async_dispatcher_send(self._hass, f"net4home_diagnostic_update_{device_id}")
                                            else:
                                                _LOGGER.warning(f"Device {device_id} not found in api.devices, cannot store powerup status")
                                            _LOGGER.debug(f"OUT_HW_NR_IS_ONOFF identified: {device_id} - CH{b1} t1{t1} - State change {bool(b7)} - Powerup: {b5}")
                                        except Exception as e:
                                            _LOGGER.error(f"Error during registration of ONOFF device (channel) {device_id}: {e}", exc_info=True)

                                    # We have a dimmer
                                    elif b2 == OUT_HW_NR_IS_DIMMER:
                                        _LOGGER.debug(f"OUT_HW_NR_IS_DIMMER identified: {device_id}")

                                        # Module details
                                        b3  = paket.ddata[3]     # time1 hi
                                        b4  = paket.ddata[4]     # time1 lo
                                        b5  = paket.ddata[5]     # Power Up (0=OFF, 1=ON, 2=ASBEFORE, 3=NoChange, 4=ON100% ) 
                                        b6  = paket.ddata[6]     # min
                                        b7  = paket.ddata[7]     # Status update
                                        b10 = paket.ddata[10]    # time2 hi
                                        b11 = paket.ddata[11]    # time2 lo
                                        b12 = paket.ddata[12]    # inverted
                                        t1  = b3*256+b4 # time1

                                        try:
                                            await register_device_in_registry(
                                                hass=self._hass,
                                                entry=self._entry,
                                                device_id=device_id,
                                                name = f"CH{b1}_{device_id[3:]}",
                                                model="Licht",
                                                sw_version="",
                                                hw_version="",
                                                device_type="light",
                                                via_device=via_device,
                                                api=self,
                                                objadr=objadr,
                                                send_state_changes = bool(b7),
                                            )
                                            # Store powerup status and MinHell in device (also for already existing devices)
                                            if device_id in self.devices:
                                                self.devices[device_id].powerup_status = b5
                                                self.devices[device_id].min_hell = b6
                                                _LOGGER.debug(f"Powerup status for {device_id} saved: {b5}, MinHell: {b6}%")
                                                # Sende Signal zur Aktualisierung der Diagnose-Sensoren
                                                async_dispatcher_send(self._hass, f"net4home_diagnostic_update_{device_id}")
                                            else:
                                                _LOGGER.warning(f"Device {device_id} not found in api.devices, cannot store powerup status")
                                            _LOGGER.debug(f"OUT_HW_NR_IS_DIMMER identified: {device_id} - CH{b1} t1{t1} - State change {bool(b7)} - Powerup: {b5} - MinHell: {b6}%")
                                        except Exception as e:
                                            _LOGGER.error(f"Error during registration of DIMMER device (channel) {device_id}: {e}", exc_info=True)

                                    # We have a cover 
                                    elif b2 == OUT_HW_NR_IS_JAL or is_jal:

                                        _LOGGER.debug(f"OUT_HW_NR_IS_JAL Paket : {' '.join(f'{b:02X}' for b in paket.ddata)}")

                                        # Module details
                                        b3  = paket.ddata[3]     # time1 hi
                                        b4  = paket.ddata[4]     # time1 lo
                                        b7  = paket.ddata[7]     # Status update
                                        t1  = b3*256+b4 # time1 (Run time for covers)
                                        
                                        _LOGGER.debug(f"OUT_HW_NR_IS_JAL identified: {device_id}")

                                        try:
                                            await register_device_in_registry(
                                                hass=self._hass,
                                                entry=self._entry,
                                                device_id=device_id,
                                                name = f"CH{b1}_{device_id[3:]}",
                                                model="Jalousie",
                                                sw_version="",
                                                hw_version="",
                                                device_type="cover",
                                                via_device=via_device,
                                                api=self,
                                                objadr=objadr,
                                                send_state_changes = bool(b7),
                                            )
                                            # Store run time (Timer1) in device (also for already existing devices)
                                            if device_id in self.devices:
                                                self.devices[device_id].timer_time1 = t1
                                                _LOGGER.debug(f"Run time for {device_id} stored: {t1}s")
                                                # Sende Signal zur Aktualisierung der Diagnose-Sensoren
                                                async_dispatcher_send(self._hass, f"net4home_diagnostic_update_{device_id}")
                                            else:
                                                _LOGGER.warning(f"Device {device_id} not found in api.devices, cannot store run time")
                                            _LOGGER.debug(f"OUT_HW_NR_IS_JAL identified: {device_id} - CH{b1} - State change {bool(b7)} - Run time: {t1}s")
                                        except Exception as e:
                                            _LOGGER.error(f"Error during registration of COVER device (channel) {device_id}: {e}")

                                elif b0 == D0_RD_SENSOR_DATA_ACK:

                                    EE_IN_TAB_ADRFKT_LEN   = 5
                                    EE_IN_TAB_ADR_OFFSET   = 0
                                    EE_IN_TAB_FKT_OFFSET   = 2

                                    EE_OFFSET_PIN_IS       = 0 + 2
                                    EE_OFFSET_FKT1         = EE_OFFSET_PIN_IS + 1
                                    EE_OFFSET_FKT2         = EE_OFFSET_FKT1   + EE_IN_TAB_ADRFKT_LEN
                                    EE_OFFSET_ADR          = EE_OFFSET_FKT2   + EE_IN_TAB_ADRFKT_LEN
                                    EE_OFFSET_MEM_STATE    = EE_OFFSET_ADR    + 2

                                    EE_OFFSET_TIMER                 = EE_OFFSET_MEM_STATE + 1
                                    EE_NCNO_INV                     = EE_OFFSET_TIMER     + 2
                                    EE_OFFSET_FKT3                  = EE_NCNO_INV         + 1
                                    EE_OFFSET_FKT4                  = EE_OFFSET_FKT3      + 5

                                    # Check minimum required length (need at least EE_OFFSET_ADR+2 for objadr)
                                    # EE_OFFSET_ADR = 13, so we need at least 15 bytes
                                    min_required = EE_OFFSET_ADR + 2
                                    if len(paket.ddata) < min_required:
                                        _LOGGER.warning(f"D0_RD_SENSOR_DATA_ACK packet too short: {len(paket.ddata)} bytes, need at least {min_required} bytes")
                                        continue
                                    
                                    pin_typ = paket.ddata[EE_OFFSET_PIN_IS]
                                    #_LOGGER.debug(f"D0_RD_SENSOR_DATA_ACK identified: Typ: {pin_typ} - {' '.join(f'{b:02X}' for b in paket.ddata)}")

                                    channel = paket.ddata[1] + 1
                                    function_count, _ = get_function_and_address_count(pin_typ)

                                    objadr = paket.ddata[EE_OFFSET_ADR]*256+paket.ddata[EE_OFFSET_ADR+1]
                                    
                                    # EE_NCNO_INV is optional - only available in longer packets (19+ bytes)
                                    # For shorter packets (like UP-RF with 15 bytes), default to False
                                    if len(paket.ddata) >= EE_NCNO_INV + 1:
                                        detected_inverted = bool(paket.ddata[EE_NCNO_INV])
                                    else:
                                        detected_inverted = False
                                    
                                    #_LOGGER.debug(f"Erkannte objadr: {objadr} (Offset {EE_OFFSET_ADR})")

                                    device_id = f"OBJ{objadr:05d}"
                                    via_device = f"MI{paket.ipsrc:04X}"
                                    device_obj = self.devices.get(via_device)
                                    
                                    # Wenn das MI-Device nicht existiert, erstelle es automatisch
                                    # (kann passieren, wenn die Abfrage von einem externen Programm kommt)
                                    if not device_obj:
                                        _LOGGER.warning(
                                            f"MI device {via_device} not found when registering OBJ device {device_id}. "
                                            f"Creating MI device automatically."
                                        )
                                        # Erstelle ein minimales MI-Device
                                        await register_device_in_registry(
                                            hass=self._hass,
                                            entry=self._entry,
                                            device_id=via_device,
                                            name=via_device,
                                            model="Unknown",
                                            sw_version="",
                                            hw_version="",
                                            device_type="module",
                                            via_device="",
                                            api=self,
                                            objadr=None,
                                        )
                                        device_obj = self.devices.get(via_device)
                                        if device_obj:
                                            _LOGGER.info(f"Created MI device {via_device} for OBJ device {device_id}")
                                        else:
                                            _LOGGER.error(f"Failed to create MI device {via_device}")
                                            continue

                                    #_LOGGER.debug(f"D0_RD_SENSOR_DATA_ACK → model: {device_id}, objadr: {objadr}, via: {via_device}, model: {getattr(device_obj, 'model', 'UNKNOWN')}")

                                    is_sensor = False
                                    if device_obj and device_obj.model in ('UP-S4',):
                                        is_sensor = True

                                    if is_sensor:
                                        try:
                                            _LOGGER.debug(
                                                f"Registering OBJ sensor device {device_id} with via_device={via_device}, "
                                                f"parent_exists={via_device in self.devices}"
                                            )
                                            await register_device_in_registry(
                                                hass=self._hass,
                                                entry=self._entry,
                                                device_id=device_id,
                                                name=f"CH{channel}_{device_id[3:]}",
                                                model="Sensor",
                                                sw_version="",
                                                hw_version="",
                                                device_type="binary_sensor",
                                                via_device=via_device,
                                                api=self,
                                                objadr=objadr,
                                                inverted=detected_inverted,  
                                            )
                                            #_LOGGER.debug(f"SENSOR registration for  → model: {device_id}, objadr: {objadr}, via: {via_device}, model: {getattr(device_obj, 'model', 'UNKNOWN')}")
                                        except Exception as e:
                                            _LOGGER.error(f"Error during SENSOR registration for {device_id}: {e}", exc_info=True)
                                    
                                    # For UP-RF devices, we don't register OBJ addresses as separate devices
                                    # The RF-Key sensor will be created directly on the MI device
                                    if device_obj and device_obj.model in ('UP-RF', 'UP-RF-S4AR1'):
                                        # Store OBJ address mapping for RF-Key message routing
                                        # We'll map OBJ addresses to the parent MI device in D0_VALUE_ACK handler
                                        _LOGGER.debug(f"UP-RF sensor object address detected: {device_id} (OBJ={objadr}) for {via_device}, channel: {channel}")

                                elif b0 == D0_SENSOR_ACK:
                                    # _LOGGER.debug(f"D0_SENSOR_ACK identified: Typ: {paket.ddata[1]} - {' '.join(f'{b:02X}' for b in paket.ddata)}")
                                    device_id = f"OBJ{paket.objsrc:05d}"
                                    device = self.devices.get(device_id)

                                    if not device:
                                        continue
                                    
                                    is_closed = paket.ddata[2] == 1

                                    _LOGGER.debug(f"D0_ACTOR_ACK for {device_id}: {is_closed}")
                                    async_dispatcher_send(self._hass, f"net4home_update_{device_id.upper()}", is_closed)

                                elif b0 == D0_RD_MODULSPEC_DATA_ACK:
                                    _LOGGER.debug(f"D0_RD_MODULSPEC_DATA_ACK identified: Typ: {paket.ddata[1]} - {' '.join(f'{b:02X}' for b in paket.ddata)}")

                                    b1  = paket.ddata[1] 
                                    obj_heat = None
                                    obj_cool = None
                                    presetday = None
                                    presetnight = None
                                    
                                    # Initialize b2 and b3 in case they are used later
                                    b2 = None
                                    b3 = None

                                    device_id = f"MI{paket.ipsrc:04X}"
                                    device = self.get_known_device(device_id)
                                    if not device:
                                        _LOGGER.warning(f"D0_RD_MODULSPEC_DATA_ACK: Device {device_id} not found")
                                        continue
                                    # Use normalized id for dispatcher so sensors (listening on device_id.upper()) receive updates
                                    dispatch_id = device.device_id.upper()
                                    model = device.model or ""
                                    objadr = device.objadr if device else None
                                    
                                    # Module-specific evaluation based on device.model
                                    # See docs/modulspec.md for details
                                    
                                    # 1. UP-TLH / UP-T: Spezielle Indizes und Sensoren
                                    if model in ('UP-TLH', 'UP-T'):
                                        _LOGGER.debug(f"D0_RD_MODULSPEC_DATA_ACK UP_TLH")
                                        # Special indices (0xF0, 0xF1) only for UP-TLH/UP-T
                                        if b1 == 0xF0:  # Tag/Nachtwert (UP-TLH/UP-T)
                                            _LOGGER.debug(f"D0_RD_MODULSPEC_DATA_ACK UP_TLH -> F0")
                                            if len(paket.ddata) >= 6:
                                                # Laut Dokumentation: Tagwert = (ddata[2] * 256 + ddata[3]) / 10.0
                                                # ddata[2] = Tagwert High, ddata[3] = Tagwert Low
                                                # Nachtwert = (ddata[4] * 256 + ddata[5]) / 10.0
                                                # ddata[4] = Nachtwert High, ddata[5] = Nachtwert Low
                                                presetday = (paket.ddata[2] * 256 + paket.ddata[3]) / 10.0
                                                presetnight = (paket.ddata[4] * 256 + paket.ddata[5]) / 10.0
                                                device.presetday = presetday
                                                device.presetnight = presetnight
                                                _LOGGER.info(
                                                    f"D0_RD_MODULSPEC_DATA_ACK 0xF0 {dispatch_id}: presetday={presetday}°C, presetnight={presetnight}°C, "
                                                    f"dispatching to net4home_update_{dispatch_id}_presetday/presetnight"
                                                )
                                                # Send updates to climate device and individual sensors (use dispatch_id so entities receive)
                                                async_dispatcher_send(self._hass, f"net4home_update_{dispatch_id}", {"presetday": presetday, "presetnight": presetnight})
                                                async_dispatcher_send(self._hass, f"net4home_update_{dispatch_id}_presetday", presetday)
                                                async_dispatcher_send(self._hass, f"net4home_update_{dispatch_id}_presetnight", presetnight)
                                            else:
                                                _LOGGER.warning(f"D0_RD_MODULSPEC_DATA_ACK packet too short for 0xF0: {len(paket.ddata)} bytes")
                                            continue
                                        
                                        if b1 == 0xF1:  # Heat/Cool Objektadressen (UP-TLH/UP-T)
                                            _LOGGER.debug(f"D0_RD_MODULSPEC_DATA_ACK UP_TLH -> F1")
                                            if len(paket.ddata) >= 10:
                                                b2 = paket.ddata[2]
                                                b3 = paket.ddata[3]
                                                b6 = paket.ddata[6]  # heat (hi)
                                                b7 = paket.ddata[7]  # heat (lo)
                                                b8 = paket.ddata[8]  # cool (hi)
                                                b9 = paket.ddata[9]  # cool (lo)
                                                objadr = (b2 << 8) + b3
                                                obj_heat = (b6 << 8) + b7
                                                obj_cool = (b8 << 8) + b9
                                                
                                                # CRITICAL FIX: If objadr is 0, calculate fallback from MI address
                                                # Pattern: MI0263 → objadr=26301 (263*100+1), MI0003 → objadr=301 (3*100+1)
                                                if objadr == 0:
                                                    mi_addr = paket.ipsrc
                                                    objadr = mi_addr * 100 + 1
                                                    _LOGGER.info(f"D0_RD_MODULSPEC_DATA_ACK 0xF1: objadr was 0, using fallback: MI{mi_addr:04X} * 100 + 1 = {objadr}")
                                                
                                                _LOGGER.debug(f"D0_RD_MODULSPEC_DATA_ACK 0xF1: objadr={objadr}, obj_heat={obj_heat}, obj_cool={obj_cool}")
                                                # Store objadr in device object for later use when b1 < 0x80
                                                device.objadr = objadr
                                                # Persist objadr to config so D0_SET and other listeners work after HA restart without Read Device
                                                try:
                                                    devices = dict(self._entry.options.get("devices", {}))
                                                    if device_id in devices:
                                                        devices[device_id]["objadr"] = objadr
                                                        new_options = dict(self._entry.options)
                                                        new_options["devices"] = devices
                                                        self._hass.config_entries.async_update_entry(self._entry, options=new_options)
                                                        _LOGGER.debug(f"Saved objadr={objadr} for {device_id} to config entry (UP-TLH 0xF1)")
                                                except Exception as e:
                                                    _LOGGER.error(f"Failed to save objadr for {device_id}: {e}")
                                                
                                                # Sende D0_REQ an die Basisadresse, um targettemp zu lesen
                                                # Laut Dokumentation: D0_REQ, 0, 0 → Sollwert-Objektadresse (objadr + 0)
                                                await self._packet_sender.send_raw_command(
                                                    ipdst=objadr,
                                                    ddata=bytes([D0_REQ, 0x00, 0x00]),
                                                    objsource=self._objadr,
                                                    mi=self._mi,
                                                )
                                                _LOGGER.debug(f"Sent D0_REQ for targettemp to {device_id} (OBJ={objadr}) after 0xF1")
                                            else:
                                                _LOGGER.warning(f"D0_RD_MODULSPEC_DATA_ACK packet too short for 0xF1: {len(paket.ddata)} bytes")
                                            continue
                                        
                                        # UP-TLH / UP-T: Sensors (b1 < 0x80: Index 0, 1, 2 for Temp, Lux, Humidity)
                                        # IMPORTANT: objadr must come from the 0xF1 packet (stored in device.objadr)
                                        if b1 < 0x80:
                                            # Use objadr from device.objadr (was set at 0xF1)
                                            if device.objadr is None:
                                                _LOGGER.warning(f"D0_RD_MODULSPEC_DATA_ACK UP-TLH/UP-T b1={b1:02X}: objadr not yet set (0xF1 packet missing?)")
                                                continue
                                            
                                            objadr = device.objadr
                                            _LOGGER.debug(f"D0_RD_MODULSPEC_DATA_ACK UP_TLH -> 80   *********************************")
                                            
                                            # Calculate sensor object address using FIXED offsets
                                            # Sensor 0 (temperature) = objadr + 3
                                            # Sensor 1 (illuminance) = objadr + 4
                                            # Sensor 2 (humidity) = objadr + 5
                                            if b1 == 0:
                                                sensor_obj = objadr + 3
                                                sensor_type = "temperature"
                                            elif b1 == 1:
                                                sensor_obj = objadr + 4
                                                sensor_type = "illuminance"
                                            elif b1 == 2:
                                                sensor_obj = objadr + 5
                                                sensor_type = "humidity"
                                            else:
                                                _LOGGER.warning(f"Unknown sensor index b1={b1} for UP-TLH")
                                                continue
                                            
                                            _LOGGER.info(f"UP-TLH Sensor: index={b1}, type={sensor_type}, obj={sensor_obj} (base {objadr} + {[3,4,5][b1]})")
                                                
                                            device_id = f"OBJ{(sensor_obj):05d}"
                                                
                                            if sensor_type:
                                                # Register device - this will also dispatch the new_device event
                                                await register_device_in_registry(
                                                    hass=self._hass,
                                                    entry=self._entry,
                                                    device_id=device_id,
                                                    name=f"{sensor_type.capitalize()} Sensor {sensor_obj}",
                                                    model=sensor_type,
                                                    sw_version="",
                                                    hw_version="",
                                                    device_type="sensor",
                                                    via_device=f"MI{paket.ipsrc:04X}",
                                                    api=self,
                                                    objadr=sensor_obj
                                                )       
                                                _LOGGER.debug(f"D0_RD_MODULSPEC_DATA_ACK UP_TLH -> Register Device   *********************************")
                                                # NOTE: Dispatcher is already called by register_device_in_registry, no need to call it again here
                                                
                                                # CRITICAL: Send D0_REQ to activate the sensor and trigger initial value broadcast
                                                _LOGGER.info(f"Sending D0_REQ to activate sensor {device_id} (OBJ={sensor_obj:04X})")
                                                await self._packet_sender.send_raw_command(
                                                    ipdst=sensor_obj,
                                                    ddata=bytes([D0_REQ, 0x00, 0x00]),
                                                    objsource=self._objadr,
                                                    mi=self._mi,
                                                    type8=SEND_AS_OBJ_GRP,  # Send to OBJ address
                                                )
                                                await asyncio.sleep(0.1)  # Small delay between sensor requests
                                            continue
                                    
                                    # 1.5. HS-Time: Modul-Info (ddata[1] = $FF) - Basisadresse lesen
                                    if model == "HS-Time" and b1 == 0xFF:
                                        _LOGGER.debug(f"D0_RD_MODULSPEC_DATA_ACK HS-Time -> FF (Modul-Info)")
                                        if len(paket.ddata) >= 5:
                                            # Laut Dokumentation: ddata[2] = Objektadresse High, ddata[3] = Objektadresse Low
                                            objadr_high = paket.ddata[2]
                                            objadr_low = paket.ddata[3]
                                            objadr = (objadr_high << 8) + objadr_low
                                            # ddata[4] = Broadcast-Index (0-7)
                                            broadcast_index = paket.ddata[4]
                                            _LOGGER.debug(f"D0_RD_MODULSPEC_DATA_ACK HS-Time 0xFF: objadr={objadr}, broadcast_index={broadcast_index}")
                                            # Speichere objadr im device Objekt
                                            if device:
                                                device.objadr = objadr
                                                # Persist objadr to config so it is available after HA restart
                                                try:
                                                    devices = dict(self._entry.options.get("devices", {}))
                                                    if device_id in devices:
                                                        devices[device_id]["objadr"] = objadr
                                                        new_options = dict(self._entry.options)
                                                        new_options["devices"] = devices
                                                        self._hass.config_entries.async_update_entry(self._entry, options=new_options)
                                                        _LOGGER.debug(f"Saved objadr={objadr} for {device_id} to config entry (HS-Time 0xFF)")
                                                except Exception as e:
                                                    _LOGGER.error(f"Failed to save objadr for {device_id}: {e}")
                                                
                                                # Broadcast-Intervall-Mapping (laut korrigierter Dokumentation)
                                                broadcast_intervals = {
                                                    0: "Nie",
                                                    1: "1 Minute",
                                                    2: "5 Minuten",
                                                    3: "15 Minuten",
                                                    4: "30 Minuten",
                                                    5: "60 Minuten",
                                                    6: "2 Stunden",
                                                    7: "4 Stunden",
                                                    8: "8 Stunden",
                                                    9: "12 Stunden",
                                                    10: "24 Stunden"
                                                }
                                                broadcast_interval_str = broadcast_intervals.get(broadcast_index, f"Unbekannt ({broadcast_index})")
                                                
                                                # Sende Broadcast-Intervall direkt an das MI-Device (wie bei UP-TLH)
                                                # WICHTIG: sensor_key ist "broadcast interval" (mit Leerzeichen), aber Dispatcher-Key verwendet slugify
                                                uid = device_id.upper()
                                                dispatcher_key_dict = f"net4home_update_{uid}"
                                                dispatcher_key_sensor = f"net4home_update_{uid}_{slugify('broadcast interval')}"
                                                async_dispatcher_send(self._hass, dispatcher_key_dict, {"broadcast interval": broadcast_interval_str})
                                                async_dispatcher_send(self._hass, dispatcher_key_sensor, broadcast_interval_str)
                                                _LOGGER.debug(f"HS-Time: Broadcast Interval for {device_id}: index={broadcast_index}, value='{broadcast_interval_str}', keys: {dispatcher_key_dict}, {dispatcher_key_sensor}")
                                                
                                                # Store Sunrise/Sunset object addresses for later D0_VALUE_REQ queries
                                                sunrise_objadr = objadr + 17
                                                sunset_objadr = objadr + 18
                                                
                                                # Send D0_VALUE_REQ for Sunrise and Sunset (values are stored directly on MI device)
                                                await self._packet_sender.send_raw_command(
                                                    ipdst=sunrise_objadr,
                                                    ddata=bytes([D0_VALUE_REQ, 0x00, 0x00]),
                                                    objsource=self._objadr,
                                                    mi=self._mi,
                                                )
                                                await asyncio.sleep(0.1)
                                                await self._packet_sender.send_raw_command(
                                                    ipdst=sunset_objadr,
                                                    ddata=bytes([D0_VALUE_REQ, 0x00, 0x00]),
                                                    objsource=self._objadr,
                                                    mi=self._mi,
                                                )
                                                _LOGGER.debug(f"HS-Time: Sent D0_VALUE_REQ for Sunrise/Sunset (objadr={objadr}, sunrise={sunrise_objadr}, sunset={sunset_objadr})")
                                            else:
                                                _LOGGER.warning(f"D0_RD_MODULSPEC_DATA_ACK HS-Time 0xFF: Device {device_id} not found, cannot set objadr")
                                        else:
                                            _LOGGER.warning(f"D0_RD_MODULSPEC_DATA_ACK packet too short for HS-Time 0xFF: {len(paket.ddata)} bytes")
                                        continue
                                    
                                    # 1.6. LCD3 (UP-LCD): b1..b2 = Adresse (Big Endian), $FFFF = Kapazitäts-Info
                                    # IMPORTANT: Check LCD BEFORE SensorConfig/PIR to avoid conflicts with b1 == 0
                                    elif model and 'LCD' in model.upper():
                                        _LOGGER.debug(f"D0_RD_MODULSPEC_DATA_ACK LCD3 for {device_id}: model={model}, ddata_len={len(paket.ddata)}, ddata[0:5]={[hex(b) for b in paket.ddata[:5]]}")
                                        if len(paket.ddata) >= 3:
                                            adr_insert = paket.ddata[1] * 256 + paket.ddata[2]  # Big Endian
                                            _LOGGER.debug(f"D0_RD_MODULSPEC_DATA_ACK LCD3 for {device_id}: adr_insert={adr_insert:04X}")
                                            if adr_insert == 0xFFFF:
                                                # Capacity info
                                                if len(paket.ddata) >= 11:
                                                    size_cfg = (paket.ddata[3] << 8) | paket.ddata[4]  # Big Endian
                                                    size_strn = (paket.ddata[5] << 8) | paket.ddata[6]  # Big Endian
                                                    size_str = (paket.ddata[7] << 8) | paket.ddata[8]  # Big Endian
                                                    size_node = (paket.ddata[9] << 8) | paket.ddata[10]  # Big Endian
                                                    _LOGGER.debug(f"D0_RD_MODULSPEC_DATA_ACK LCD3 capacity for {device_id}: "
                                                                f"SizeCfg={size_cfg}, SizeStrN={size_strn}, SizeStr={size_str}, SizeNODE={size_node}")
                                                else:
                                                    _LOGGER.warning(f"D0_RD_MODULSPEC_DATA_ACK packet too short for LCD3 Kapazität: {len(paket.ddata)} bytes")
                                            elif adr_insert == 0:
                                                # Zeile 0: Konfiguration (TCfg_LCD3)
                                                # Byte 0-1: adrUK (Basis-Objektadresse, Big Endian)
                                                # Paketstruktur: ddata[0] = Befehl, ddata[1-2] = Adresse (Big Endian), ddata[3-34] = 32 Bytes Daten
                                                # Mindestens 5 Bytes benötigt (Befehl + Adresse + erste 2 Bytes der Daten für adrUK)
                                                if len(paket.ddata) >= 5:
                                                    # ddata[3:5] = adrUK (Big Endian) - erste 2 Bytes der Konfiguration
                                                    adr_uk = (paket.ddata[3] << 8) | paket.ddata[4]  # Big Endian
                                                    device.objadr = adr_uk
                                                    _LOGGER.info(f"D0_RD_MODULSPEC_DATA_ACK LCD3 config (line 0) for {device_id}: adrUK={adr_uk:04X} (OBJ={adr_uk}), packet_len={len(paket.ddata)} bytes")
                                                    
                                                    # Send signal to add LCD buttons if not already present
                                                    async_dispatcher_send(self._hass, f"net4home_device_updated_{self._entry.entry_id}", device_id)
                                                    
                                                    # Save objadr to config entry for persistence
                                                    try:
                                                        devices = dict(self._entry.options.get("devices", {}))
                                                        if device_id in devices:
                                                            devices[device_id]["objadr"] = adr_uk
                                                            new_options = dict(self._entry.options)
                                                            new_options["devices"] = devices
                                                            self._hass.config_entries.async_update_entry(self._entry, options=new_options)
                                                            _LOGGER.debug(f"Saved objadr={adr_uk} for {device_id} to config entry")
                                                    except Exception as e:
                                                        _LOGGER.error(f"Failed to save objadr for {device_id}: {e}")
                                                else:
                                                    _LOGGER.warning(f"D0_RD_MODULSPEC_DATA_ACK packet too short for LCD3 config: {len(paket.ddata)} bytes (need at least 5 bytes for adrUK)")
                                            else:
                                                # Normal line data (other lines)
                                                _LOGGER.debug(f"D0_RD_MODULSPEC_DATA_ACK LCD3 line for {device_id}: adr={adr_insert:04X}")
                                        else:
                                            _LOGGER.warning(f"D0_RD_MODULSPEC_DATA_ACK packet too short for LCD3: {len(paket.ddata)} bytes")
                                        continue
                                    
                                    # WAV-Bell (PLATINE_HW_IS_BELL2): First line = TCFG, bytes 0-1 = AdrUK (Basis-Objektadresse)
                                    # Some firmware sends first config line with line_index=0x1E (30), not 0
                                    elif model == ".WAV-Bell" or device.module_type == PLATINE_HW_IS_BELL2:
                                        if len(paket.ddata) >= 5:
                                            line_index = (paket.ddata[1] << 8) | paket.ddata[2]  # Big Endian
                                            if line_index == 0 or line_index == 0x1E:
                                                # TCFG: AdrUK at ddata[2:4] (Big Endian), e.g. 0x1E 0x15 = 7701
                                                adr_uk = (paket.ddata[2] << 8) | paket.ddata[3]
                                                device.objadr = adr_uk
                                                _LOGGER.info(
                                                    f"D0_RD_MODULSPEC_DATA_ACK WAV-Bell config (line 0) for {device_id}: "
                                                    f"adrUK={adr_uk:04X} (OBJ={adr_uk}), packet_len={len(paket.ddata)} bytes"
                                                )
                                                async_dispatcher_send(self._hass, f"net4home_device_updated_{self._entry.entry_id}", device_id)
                                                try:
                                                    devices = dict(self._entry.options.get("devices", {}))
                                                    if device_id in devices:
                                                        devices[device_id]["objadr"] = adr_uk
                                                        new_options = dict(self._entry.options)
                                                        new_options["devices"] = devices
                                                        self._hass.config_entries.async_update_entry(self._entry, options=new_options)
                                                        _LOGGER.debug(f"Saved objadr={adr_uk} for {device_id} to config entry (WAV-Bell)")
                                                except Exception as e:
                                                    _LOGGER.error(f"Failed to save objadr for {device_id}: {e}")
                                            else:
                                                _LOGGER.debug(f"D0_RD_MODULSPEC_DATA_ACK WAV-Bell line for {device_id}: line_index={line_index}")
                                        else:
                                            _LOGGER.warning(
                                                f"D0_RD_MODULSPEC_DATA_ACK packet too short for WAV-Bell: {len(paket.ddata)} bytes"
                                            )
                                        continue

                                    # 5. IR_TX: b1 = $FF = Modul-Info, b1 < $80 = Tabelle, b1 >= $C0 = MaxPower
                                    elif model and 'IR' in model.upper() and 'TX' in model.upper():
                                        if b1 == 0xFF:
                                            # Modul-Info
                                            if len(paket.ddata) >= 6:
                                                tab_entry_count = paket.ddata[2]
                                                adr_obj_ir = paket.ddata[3] * 256 + paket.ddata[4]  # Little Endian
                                                tab2_entry_count = paket.ddata[5]
                                                _LOGGER.debug(f"D0_RD_MODULSPEC_DATA_ACK IR_TX module info for {device_id}: "
                                                            f"TabEntries={tab_entry_count}, ObjAdr={adr_obj_ir}, Tab2Entries={tab2_entry_count}")
                                            else:
                                                _LOGGER.warning(f"D0_RD_MODULSPEC_DATA_ACK packet too short for IR_TX Modul-Info: {len(paket.ddata)} bytes")
                                        elif b1 < 0x80:
                                            # Haupttabelle
                                            if len(paket.ddata) >= 26:
                                                tab_index = b1
                                                _LOGGER.debug(f"D0_RD_MODULSPEC_DATA_ACK IR_TX table for {device_id}: Index={tab_index}")
                                                # Table data can be stored for later use
                                            else:
                                                _LOGGER.warning(f"D0_RD_MODULSPEC_DATA_ACK packet too short for IR_TX Tabelle: {len(paket.ddata)} bytes")
                                        elif b1 >= 0xC0:
                                            # MaxPower-Tabelle
                                            if len(paket.ddata) >= 34:
                                                tab2_index = b1 - 0xC0
                                                _LOGGER.debug(f"D0_RD_MODULSPEC_DATA_ACK IR_TX MaxPower for {device_id}: Index={tab2_index}")
                                                # Table data can be stored for later use
                                            else:
                                                _LOGGER.warning(f"D0_RD_MODULSPEC_DATA_ACK packet too short for IR_TX MaxPower: {len(paket.ddata)} bytes")
                                        # IR_TX D0_RD_MODULSPEC_DATA_ACK processing complete
                                        continue

                                elif b0 == D0_VALUE_ACK:
                                    _LOGGER.info(f"D0_VALUE_ACK BLOCK REACHED! b0={b0}, D0_VALUE_ACK={D0_VALUE_ACK}, paket.objsrc={paket.objsrc}")
                                    device_id = f"OBJ{paket.objsrc:05d}"
                                    dispatch_device_id = device_id.upper()
                                    _LOGGER.debug(f"D0_VALUE_ACK for {device_id} – Type: {paket.ddata[1]}")

                                    # Check if packet has enough data (need at least 5 bytes for sensor values)
                                    if len(paket.ddata) < 5:
                                        _LOGGER.warning(f"D0_VALUE_ACK packet too short: {len(paket.ddata)} bytes, expected at least 5")
                                        continue

                                    if paket.ddata[1] == IN_HW_NR_IS_TEMP:
                                        i_analog_value = paket.ddata[3] * 256 + paket.ddata[4]
                                        if i_analog_value > 0x8000:
                                            i_analog_value -= 0x10000
                                        i_analog_value = (i_analog_value * 10) // 16
                                        value = round(i_analog_value / 10, 1)
                                        sensor_type = "temperature"
                                        dispatcher_key = f"net4home_update_{dispatch_device_id}_{sensor_type}"
                                        async_dispatcher_send(self._hass, dispatcher_key, value)
                                        _LOGGER.debug(f"_temperature D0_VALUE_ACK for {dispatcher_key} – Value: {value}")
                                    
                                    elif paket.ddata[1] == IN_HW_NR_IS_HUMIDITY:
                                        value = paket.ddata[3] * 256 + paket.ddata[4]
                                        sensor_type = "humidity"
                                        dispatcher_key = f"net4home_update_{dispatch_device_id}_{sensor_type}"
                                        async_dispatcher_send(self._hass, dispatcher_key, value)
                                        _LOGGER.debug(f"_humidity D0_VALUE_ACK for {dispatcher_key} – Value: {value}")
                                        
                                    elif paket.ddata[1] == IN_HW_NR_IS_LICHT_ANALOG:
                                        value = paket.ddata[3] * 256 + paket.ddata[4]
                                        sensor_type = "illuminance"
                                        dispatcher_key = f"net4home_update_{dispatch_device_id}_{sensor_type}"
                                        async_dispatcher_send(self._hass, dispatcher_key, value)
                                        _LOGGER.debug(f"_illuminance D0_VALUE_ACK for {dispatcher_key} – Value: {value}")
                                    
                                    # HS-Time: Sonnenaufgang (VAL_IS_MIN_TAG_WORD_SA = 50)
                                    elif paket.ddata[1] == VAL_IS_MIN_TAG_WORD_SA:
                                        # Laut Dokumentation: ddata[2] = Minuten Low, ddata[3] = Minuten High
                                        # Berechnung: Sonnenaufgang_Zeit = (ddata[3] * 256 + ddata[2]) Minuten seit Mitternacht
                                        # Finde das HS-Time MI-Device (Sunrise kommt von objadr + 17)
                                        device_id_from_ipsrc = f"MI{paket.ipsrc:04X}"
                                        mi_device = self.get_known_device(device_id_from_ipsrc)
                                        
                                        if mi_device and mi_device.model == "HS-Time":
                                            if len(paket.ddata) >= 4:
                                                # Laut korrigierter Dokumentation (hs-time.md):
                                                # ddata[2] = Minuten Low, ddata[3] = Minuten High
                                                # Berechnung: Sonnenaufgang_Zeit = (ddata[3] * 256 + ddata[2]) Minuten seit Mitternacht
                                                # Die Original-Implementierung interpretiert es falsch als direkt Stunden:Minuten
                                                minutes_low = paket.ddata[2]
                                                minutes_high = paket.ddata[3]
                                                minutes_since_midnight = minutes_high * 256 + minutes_low
                                                # Konvertiere Minuten seit Mitternacht zu Stunden:Minuten Format
                                                hours = minutes_since_midnight // 60
                                                minutes = minutes_since_midnight % 60
                                                # Wert als Zeit-String formatieren (z.B. "06:30")
                                                value = f"{hours:02d}:{minutes:02d}"
                                                
                                                # Sende direkt an das MI-Device (wie bei UP-TLH)
                                                uid = device_id_from_ipsrc.upper()
                                                async_dispatcher_send(self._hass, f"net4home_update_{uid}", {"sunrise": value})
                                                async_dispatcher_send(self._hass, f"net4home_update_{uid}_sunrise", value)
                                                _LOGGER.debug(f"HS-Time Sunrise for {device_id_from_ipsrc}: {value} ({minutes_since_midnight} minutes since midnight, raw: ddata[2]=0x{minutes_low:02X}={minutes_low}, ddata[3]=0x{minutes_high:02X}={minutes_high})")
                                            else:
                                                _LOGGER.warning(f"D0_VALUE_ACK packet too short for HS-Time Sunrise: {len(paket.ddata)} bytes")
                                        else:
                                            _LOGGER.warning(f"HS-Time Sunrise: MI device {device_id_from_ipsrc} not found or not HS-Time")
                                    
                                    # HS-Time: Sonnenuntergang (VAL_IS_MIN_TAG_WORD_SU = 51)
                                    elif paket.ddata[1] == VAL_IS_MIN_TAG_WORD_SU:
                                        # Laut Dokumentation: ddata[2] = Minuten Low, ddata[3] = Minuten High
                                        # Berechnung: Sonnenuntergang_Zeit = (ddata[3] * 256 + ddata[2]) Minuten seit Mitternacht
                                        # Finde das HS-Time MI-Device (Sunset kommt von objadr + 18)
                                        device_id_from_ipsrc = f"MI{paket.ipsrc:04X}"
                                        mi_device = self.get_known_device(device_id_from_ipsrc)
                                        
                                        if mi_device and mi_device.model == "HS-Time":
                                            if len(paket.ddata) >= 4:
                                                # Laut korrigierter Dokumentation (hs-time.md):
                                                # ddata[2] = Minuten Low, ddata[3] = Minuten High
                                                # Berechnung: Sonnenuntergang_Zeit = (ddata[3] * 256 + ddata[2]) Minuten seit Mitternacht
                                                # Die Original-Implementierung interpretiert es falsch als direkt Stunden:Minuten
                                                minutes_low = paket.ddata[2]
                                                minutes_high = paket.ddata[3]
                                                minutes_since_midnight = minutes_high * 256 + minutes_low
                                                # Konvertiere Minuten seit Mitternacht zu Stunden:Minuten Format
                                                hours = minutes_since_midnight // 60
                                                minutes = minutes_since_midnight % 60
                                                # Wert als Zeit-String formatieren (z.B. "18:30")
                                                value = f"{hours:02d}:{minutes:02d}"
                                                
                                                # Sende direkt an das MI-Device (wie bei UP-TLH)
                                                uid = device_id_from_ipsrc.upper()
                                                async_dispatcher_send(self._hass, f"net4home_update_{uid}", {"sunset": value})
                                                async_dispatcher_send(self._hass, f"net4home_update_{uid}_sunset", value)
                                                _LOGGER.debug(f"HS-Time Sunset for {device_id_from_ipsrc}: {value} ({minutes_since_midnight} minutes since midnight, raw: ddata[2]=0x{minutes_low:02X}={minutes_low}, ddata[3]=0x{minutes_high:02X}={minutes_high})")
                                            else:
                                                _LOGGER.warning(f"D0_VALUE_ACK packet too short for HS-Time Sunset: {len(paket.ddata)} bytes")
                                        else:
                                            _LOGGER.warning(f"HS-Time Sunset: MI device {device_id_from_ipsrc} not found or not HS-Time")
                                    
                                    elif paket.ddata[1] == IN_HW_NR_IS_RF_TAG_READER:
                                        # Check if packet has enough data (need at least 10 bytes: indices 0-9)
                                        if len(paket.ddata) < 10:
                                            _LOGGER.warning(f"RF-Key packet too short: {len(paket.ddata)} bytes, expected at least 10")
                                            continue
                                        
                                        # Extract 5-byte RF-Key code (40-bit)
                                        rf_key_bytes = paket.ddata[3:8]
                                        rf_key_hex = ''.join(f'{b:02X}' for b in rf_key_bytes)
                                        
                                        # Extract state from ddata[9]
                                        tag_state = paket.ddata[9] & 6
                                        if tag_state == 0:
                                            state = "short_hold"
                                        elif tag_state == 2:
                                            state = "long_hold"
                                        elif tag_state == 4:
                                            state = "removed_after_short"
                                        else:
                                            state = "unknown"
                                        
                                        # Map OBJ address to parent MI device for RF-Key messages
                                        # RF-Key sensor should be on the main MI device, not on OBJ child devices
                                        via_device_id = f"MI{paket.ipsrc:04X}"
                                        parent_device = self.devices.get(via_device_id)
                                        
                                        if parent_device and parent_device.device_type == "rf_reader":
                                            # Send update to the parent MI device, not the OBJ address
                                            dispatcher_key = f"net4home_update_{via_device_id.upper()}_rf_key"
                                            async_dispatcher_send(self._hass, dispatcher_key, {
                                                "rf_key": rf_key_hex,
                                                "state": state
                                            })
                                            _LOGGER.debug(f"RF-Key detected: {rf_key_hex} ({state}) from OBJ {device_id}, mapped to {via_device_id}")
                                            
                                            # Fire Home Assistant event for automation triggers
                                            self._hass.bus.async_fire(
                                                "net4home_rf_key_detected",
                                                {
                                                    "device_id": via_device_id.upper(),
                                                    "device_name": parent_device.name if parent_device else via_device_id,
                                                    "rf_key": rf_key_hex,
                                                    "state": state,
                                                    "rf_key_bytes": rf_key_bytes.hex(),
                                                }
                                            )
                                        else:
                                            # Fallback: use OBJ address if parent not found
                                            dispatcher_key = f"net4home_update_{device_id.upper()}_rf_key"
                                            async_dispatcher_send(self._hass, dispatcher_key, {
                                                "rf_key": rf_key_hex,
                                                "state": state
                                            })
                                            _LOGGER.debug(f"RF-Key detected: {rf_key_hex} ({state}) from {device_id} (parent not found)")
                                            
                                            # Fire Home Assistant event for automation triggers
                                            fallback_device = self.devices.get(device_id)
                                            self._hass.bus.async_fire(
                                                "net4home_rf_key_detected",
                                                {
                                                    "device_id": device_id.upper(),
                                                    "device_name": fallback_device.name if fallback_device else device_id,
                                                    "rf_key": rf_key_hex,
                                                    "state": state,
                                                    "rf_key_bytes": rf_key_bytes.hex(),
                                                }
                                            )

                                elif b0 == D0_STATUS_INFO:
                                    device_id = f"OBJ{paket.objsrc:05d}"
                                    if len(paket.ddata) < 4:
                                        _LOGGER.warning(f"STATUS_INFO packet too short: {len(paket.ddata)} bytes, expected at least 4")
                                        continue
                                    dispatch_key = f"net4home_update_{device_id.upper()}"
                                    device = self.get_known_device(device_id)
                                    if device and device.device_type == "light":
                                        is_on = paket.ddata[2] >> 7
                                        brightness_value = round((paket.ddata[2] & 0x7F) * 255 / 100)
                                        _LOGGER.debug(f"STATUS_INFO for {device_id}: light {'ON' if is_on else 'OFF'} {brightness_value}%")
                                        async_dispatcher_send(
                                            self._hass,
                                            dispatch_key,
                                            {"is_on": is_on, "brightness": brightness_value},
                                        )
                                    elif device and device.device_type == "switch":
                                        is_on = paket.ddata[2] == 1
                                        _LOGGER.debug(f"STATUS_INFO for {device_id}: switch {'ON' if is_on else 'OFF'}")
                                        async_dispatcher_send(self._hass, dispatch_key, is_on)
                                    elif paket.ddata[3] == OUT_HW_NR_IS_DIMMER:
                                        is_on = paket.ddata[2] >> 7
                                        brightness_value = round((paket.ddata[2] & 0x7F) * 255 / 100)
                                        _LOGGER.debug(f"STATUS_INFO for {device_id}: {'ON' if is_on else 'OFF'} {brightness_value}%")
                                        async_dispatcher_send(
                                            self._hass,
                                            dispatch_key,
                                            {"is_on": is_on, "brightness": brightness_value},
                                        )
                                    else:
                                        is_on = paket.ddata[2] == 1
                                        _LOGGER.debug(f"STATUS_INFO for {device_id}: {'ON' if is_on else 'OFF'}")
                                        async_dispatcher_send(self._hass, dispatch_key, is_on)

                                elif b0 in {D0_SET, D0_INC, D0_DEC, D0_TOGGLE}:
                                    device_id = f"OBJ{paket.objsrc:05d}"
                                    device = self.devices.get(device_id)

                                    if not device:
                                        continue

                                    # _LOGGER.debug(f"D0_xxx for {device_id} – Command: {paket.ddata[0]}")

                                    if device.device_type == "binary_sensor":
                                        await self.async_request_status(device.device_id)

                except (ConnectionResetError, OSError) as e:
                    _LOGGER.warning(f"[IP] Connection error: {e}")
                    if self._reconnect_enabled:
                        _LOGGER.debug(f"[IP] Reconnect enabled, attempting reconnect...")
                        await self.async_reconnect()
                    else:
                        _LOGGER.info(f"[IP] Reconnect disabled – leaving listener")
                        break
                except Exception as e:
                    _LOGGER.error(f"Error in listener: {e}", exc_info=True)

    async def async_turn_on_switch(self, device_id: str):
        """Send an ON signal to the specified switch device."""
        try:
            device = self.devices.get(device_id)
            if not device:
                _LOGGER.warning(f"No device with ID {device_id} found")
                return

            objadr = device.objadr 
            
            if not device:
                _LOGGER.warning(f"No device with ID {device_id} found")
                return
                
            model = device.model
            
            if model == "Schalter":
                await self._packet_sender.send_raw_command(
                    ipdst=objadr,
                    ddata=bytes([D0_SET, 0x64, 0x00]),  
                    objsource=self._objadr,
                    mi=self._mi,
                )
                _LOGGER.debug(f"Switch command ON sent to {device_id} (OBJ={objadr})")
            elif model == "Timer":
                await self._packet_sender.send_raw_command(
                    ipdst=objadr,
                    ddata=bytes([D0_TOGGLE , 0x00, 0x00]),  
                    objsource=self._objadr,
                    mi=self._mi,
                )
                _LOGGER.debug(f"Switch command TOGGLE sent to {device_id} (OBJ={objadr})")
                

        except Exception as e:
            _LOGGER.error(f"Error turning ON for {device_id}: {e}")

    async def async_turn_off_switch(self, device_id: str):
        """Send an OFF signal to the specified switch device."""
        try:
            if not device_id.startswith("OBJ"):
                _LOGGER.warning(f"Invalid device_id: {device_id}")
                return

            device = self.devices.get(device_id)
            objadr = device.objadr if device else None
            
            if objadr is None:
                _LOGGER.warning(f"No objadr for {device_id}")
                return

            await self._packet_sender.send_raw_command(
                ipdst=objadr,
                ddata=bytes([D0_SET, 0x00, 0x00]), 
                objsource=self._objadr,
                mi=self._mi,
            )

            _LOGGER.debug(f"Switch command OFF sent to {device_id} (OBJ={objadr})")

        except Exception as e:
            _LOGGER.error(f"Error turning OFF for {device_id}: {e}")

    async def async_send_bell_command(self, device_id: str, command: str) -> None:
        """
        Send WAV-Bell command (EIN/AUS/LAUTER/LEISER) to the module's object address (AdrUK).

        Commands are sent to the basis object address (adr_dld = AdrUK). Requires objadr
        to be set (e.g. via Read Device). Command values per WAV-Bell docs:
        - ON: D0_SET, 101 (EIN)
        - OFF: D0_SET, 102 (AUS)
        - INC_VOL: D0_INC, 0, 0 (LAUTER)
        - DEC_VOL: D0_DEC, 0, 0 (LEISER)
        """
        device = self.get_known_device(device_id)
        if not device:
            _LOGGER.warning(f"WAV-Bell: device {device_id} not found")
            return
        objadr = device.objadr
        if objadr is None:
            _LOGGER.warning(
                f"No objadr for WAV-Bell {device_id}. Use Read Device first to load object address (AdrUK)."
            )
            return
        if command == "ON":
            ddata = bytes([D0_SET, 101, 0])
        elif command == "OFF":
            ddata = bytes([D0_SET, 102, 0])
        elif command == "INC_VOL":
            ddata = bytes([D0_INC, 0, 0])
        elif command == "DEC_VOL":
            ddata = bytes([D0_DEC, 0, 0])
        else:
            _LOGGER.warning(f"WAV-Bell: unknown command {command}")
            return
        await self._packet_sender.send_raw_command(
            ipdst=objadr,
            ddata=ddata,
            objsource=self._objadr,
            mi=self._mi,
            type8=SEND_AS_OBJ_GRP,
        )
        _LOGGER.debug(f"WAV-Bell command {command} sent to {device_id} (OBJ={objadr})")

    async def async_send_bell_track(
        self,
        device_id: str,
        track: int,
        repeats: int = 1,
        interrupt: bool = True,
        dnr: bool = False,
    ) -> None:
        """
        Play a specific track on WAV-Bell module via D0_SET_N to the module's object address (AdrUK).

        - ddata[0] = 59 (D0_SET_N)
        - ddata[1] = track (0–31)
        - ddata[2] = (repeats - 1) & 0x0F, optionally + D2_OPT_INTERRUPT (0x80) and/or D2_OPT_DNR (0x40)

        Requires objadr to be set (e.g. via Read Device).
        """
        device = self.get_known_device(device_id)
        if not device:
            _LOGGER.warning(f"WAV-Bell: device {device_id} not found")
            return
        objadr = device.objadr
        if objadr is None:
            _LOGGER.warning(
                f"No objadr for WAV-Bell {device_id}. Use Read Device first to load object address (AdrUK)."
            )
            return
        if not 0 <= track <= 31:
            _LOGGER.warning(f"WAV-Bell: track must be 0–31, got {track}")
            return
        repeats_val = max(1, min(16, repeats))
        byte2 = (repeats_val - 1) & 0x0F
        if interrupt:
            byte2 |= D2_OPT_INTERRUPT
        if dnr:
            byte2 |= D2_OPT_DNR
        ddata = bytes([D0_SET_N, track, byte2])
        await self._packet_sender.send_raw_command(
            ipdst=objadr,
            ddata=ddata,
            objsource=self._objadr,
            mi=self._mi,
            type8=SEND_AS_OBJ_GRP,
        )
        _LOGGER.debug(
            f"WAV-Bell track {track} (repeats={repeats_val}, byte2=0x{byte2:02X}) sent to {device_id} (OBJ={objadr})"
        )

    async def async_send_lcd_command(self, device_id: str, options: int, text: str = "", freq: int = 100):
        """
        Send LCD command (D0_SET_N) to UP-LCD device.
        
        According to documentation (up-lcd.md), commands MUST be sent to the object address (adrUK).
        The object address is read from ModulSpec data (line 0, bytes 0-1 of TCfg_LCD3).
        
        Args:
            device_id: Device ID of the LCD module (e.g., "MI0099")
            options: Bit flags for LCD options (e.g., CI_LCD_OPT_BLINK, CI_LCD_OPT_BUZZER_ON)
            text: Text to display (optional, max 24 bytes)
            freq: Frequency in 100/Hz format (default: 100 = 1 Hz)
        """
        try:
            device = self.devices.get(device_id)
            if not device:
                _LOGGER.warning(f"No device with ID {device_id} found")
                return

            # UP-LCD commands MUST be sent to object address (adrUK), not MI address
            objadr = device.objadr
            if objadr is None:
                _LOGGER.warning(f"No objadr for {device_id}. Object address (adrUK) must be read from ModulSpec data first. "
                              f"Please read device configuration to load the object address.")
                return

            # Prepare text: max 24 bytes, null-terminated, padded with zeros
            text_bytes = text.encode('utf-8', errors='ignore')[:LCD_STR_LEN_1-1]  # Leave room for null terminator
            text_padded = text_bytes + b'\x00' * (LCD_STR_LEN_1 - len(text_bytes))

            # Build D0_SET_N command structure:
            # ddata[0] = D0_SET_N (59)
            # ddata[1] = 0xF0 (SetN-Kommando)
            # ddata[2] = options (Bit-Flags)
            # ddata[3] = freq (100 / Hz)
            # ddata[4] = xy (0 = keine Position)
            # ddata[5:29] = text (24 Bytes)
            ddata = bytearray([
                D0_SET_N,      # Command
                0xF0,          # SetN-Kommando
                options,       # Options (Bit-Flags)
                freq & 0xFF,  # Frequency (low byte)
                0,             # X/Y-Position (not used)
            ])
            ddata.extend(text_padded[:LCD_STR_LEN_1])  # Add 24 bytes of text

            # Send to object address (type8 = SEND_AS_OBJ_GRP = 0)
            await self._packet_sender.send_raw_command(
                ipdst=objadr,
                ddata=bytes(ddata),
                objsource=self._objadr,
                mi=self._mi,
                type8=SEND_AS_OBJ_GRP,  # Always use object address, never MI address
            )
            _LOGGER.debug(f"LCD command sent to {device_id} (OBJ={objadr:04X}): options=0x{options:02X}, text='{text[:20]}...'")

        except Exception as e:
            _LOGGER.error(f"Error sending LCD command for {device_id}: {e}")

    async def async_request_status(self, device_id: str):
        """Request status from a device."""
        try:
            device = self.devices.get(device_id)
            if not device:
                _LOGGER.warning(f"Device {device_id} not found for status request.")
                return

            objadr = device.objadr if device else None

            if objadr is None:
                _LOGGER.warning(f"Missing objadr {device_id}")
                return

            # For climate devices (MI devices): Send D0_REQ to base address to read targettemp
            # According to documentation: D0_REQ, 0, 0 → setpoint object address (objadr + 0)
            if device.device_type == 'climate':
                # Climate devices are MI devices, send D0_REQ to base address (objadr)
                await self._packet_sender.send_raw_command(
                    ipdst=objadr,
                    ddata=bytes([D0_REQ, 0x00, 0x00]), 
                    objsource=self._objadr,
                    mi=self._mi,
                )
                _LOGGER.debug(f"Status request (D0_REQ) for climate device {device_id} (OBJ={objadr}) sent")
            elif device_id.startswith("OBJ"):
                # For OBJ devices: Standard status query
                await self._packet_sender.send_raw_command(
                    ipdst=objadr,
                    ddata=bytes([D0_REQ, 0x00, 0x00]), 
                    objsource=self._objadr,
                    mi=self._mi,
                )
                _LOGGER.debug(f"Status request for {device_id} (OBJ={objadr}) sent")
            else:
                _LOGGER.warning(f"Invalid device_id format: {device_id} for status request (expected OBJ or MI for climate).")
        except Exception as e:
            _LOGGER.error(f"Error sending status request for {device_id}: {e}")

    async def async_request_sensor_data(self, device_id: str, channel: int = 0):
        """Request sensor data for a device (MI address)."""
        try:
            if not device_id.startswith("MI"):
                _LOGGER.warning(f"Invalid device_id: {device_id} for sensor data request (expected MI address).")
                return

            device = self.devices.get(device_id)
            if not device:
                _LOGGER.warning(f"Device {device_id} not found")
                return
            
            mi_addr = int(device_id[2:], 16)

            await self._packet_sender.send_raw_command(
                ipdst=mi_addr,
                ddata=bytes([D0_RD_SENSOR_DATA, channel, 0x00]), 
                objsource=self._objadr,
                mi=self._mi,
                type8=SEND_AS_IP,
            )

            _LOGGER.debug(f"Sensor data request for {device_id} channel {channel} sent")
        except Exception as e:
            _LOGGER.error(f"Error sending sensor data request for {device_id}: {e}")

    async def async_start_masterkey_learning(self, device_id: str):
        """Start Masterkey learning process for UP-RF device."""
        try:
            if not device_id.startswith("MI"):
                _LOGGER.warning(f"Invalid device_id: {device_id} for Masterkey learning (expected MI address).")
                return

            device = self.devices.get(device_id)
            if not device:
                _LOGGER.warning(f"Device {device_id} not found")
                return
            
            if device.device_type != "rf_reader":
                _LOGGER.warning(f"Device {device_id} is not an RF-Reader device")
                return

            mi_addr = int(device_id[2:], 16)

            # Send D0_WR_MODULSPEC_DATA with FA 00 to start Masterkey learning
            await self._packet_sender.send_raw_command(
                ipdst=mi_addr,
                ddata=bytes([D0_WR_MODULSPEC_DATA, 0xFA, 0x00]), 
                objsource=self._objadr,
                mi=self._mi,
                type8=SEND_AS_IP,
            )

            _LOGGER.info(f"Masterkey learning started for {device_id} (MI={mi_addr:04X})")
        except Exception as e:
            _LOGGER.error(f"Error starting Masterkey learning for {device_id}: {e}")

    async def async_read_device_config(self, device_id: str):
        """Read device configuration for MI device (queues device for detail retrieval)."""
        try:
            if not device_id.upper().startswith("MI"):
                _LOGGER.warning(f"Invalid device_id: {device_id} for config read (expected MI address).")
                return

            device = self.get_known_device(device_id)
            if not device:
                _LOGGER.warning(f"Device {device_id} not found")
                return
            # Use canonical device_id from device so queue and config use same key
            device_id = device.device_id

            # Set device status to pending before queuing
            # This ensures the device will be processed even if it was previously completed
            device.detail_status = "pending"
            device.discovered_at = datetime.now()
            await self._async_save_device_detail_status(device_id, "pending")
            _LOGGER.debug(f"Set device {device_id} detail_status to pending before queuing for details")

            # Queue device for detail retrieval
            # Check if queue is initialized and running
            if self._detail_queue is None:
                _LOGGER.warning(f"Detail queue not initialized, cannot queue {device_id}. Starting queue...")
                await self.async_start_detail_retrieval()

            if self._detail_queue is not None and self._detail_queue_running:
                await self._detail_queue.put(device_id)
                queue_size = self._detail_queue.qsize()
                _LOGGER.info(f"Device {device_id} ({device.model}) queued for detail retrieval (queue running: {self._detail_queue_running}, queue size after put: {queue_size})")
            else:
                _LOGGER.warning(f"Detail queue not running, cannot queue {device_id}. Queue running: {self._detail_queue_running}")
            
        except Exception as e:
            _LOGGER.error(f"Error reading device configuration for {device_id}: {e}")

    async def async_open_cover(self, device_id: str):
        """Send open signal to net4home device."""
        try:
            if not device_id.startswith("OBJ"):
                _LOGGER.warning(f"Invalid device_id: {device_id}")
                return

            device = self.devices.get(device_id)
            objadr = device.objadr if device else None
            
            if objadr is None:
                _LOGGER.warning(f"No objadr for {device_id}")
                return

            await self._packet_sender.send_raw_command(
                ipdst=objadr,
                ddata=bytes([D0_SET, 0x03, 0x00]), 
                objsource=self._objadr,
                mi=self._mi,
            )

            _LOGGER.debug(f"Cover command OPEN sent to {device_id} (OBJ={objadr})")

        except Exception as e:
            _LOGGER.error(f"Error opening cover for {device_id}: {e}")

    async def async_close_cover(self, device_id: str):
        """Send close signal to net4home device."""
        try:
            if not device_id.startswith("OBJ"):
                _LOGGER.warning(f"Invalid device_id: {device_id}")
                return

            device = self.devices.get(device_id)
            objadr = device.objadr if device else None
            
            if objadr is None:
                _LOGGER.warning(f"No objadr for {device_id}")
                return

            await self._packet_sender.send_raw_command(
                ipdst=objadr,
                ddata=bytes([D0_SET, 0x01, 0x00]), 
                objsource=self._objadr,
                mi=self._mi,
            )

            _LOGGER.debug(f"Cover command CLOSE sent to {device_id} (OBJ={objadr})")

        except Exception as e:
            _LOGGER.error(f"Error turning OFF for {device_id}: {e}")

    async def async_stop_cover(self, device_id: str):
        """Send stop signal to net4home device."""
        try:
            if not device_id.startswith("OBJ"):
                _LOGGER.warning(f"Invalid device_id: {device_id}")
                return

            device = self.devices.get(device_id)
            objadr = device.objadr if device else None
            
            if objadr is None:
                _LOGGER.warning(f"No objadr for {device_id}")
                return

            await self._packet_sender.send_raw_command(
                ipdst=objadr,
                ddata=bytes([D0_SET, 0x00, 0x00]), 
                objsource=self._objadr,
                mi=self._mi,
            )

            _LOGGER.debug(f"Cover command STOP sent to {device_id} (OBJ={objadr})")

        except Exception as e:
            _LOGGER.error(f"Error stopping cover for {device_id}: {e}")
        

    async def async_turn_on_light(self, device_id: str, brightness: int = 255):
        """Turn on light with specified brightness."""
        device = self.devices.get(device_id)

        if not device:
            _LOGGER.warning(f"No light device with ID {device_id} found")
            return
        objadr = device.objadr

        if objadr is None:
            _LOGGER.warning(f"No objadr for light {device_id}")
            return
        brightness100 = round(brightness * 100 / 255)
        await self._packet_sender.send_raw_command(
            ipdst=objadr,
            ddata=bytes([D0_SET, brightness100, 0x00]),
            objsource=self._objadr,
            mi=self._mi,
        )
        _LOGGER.debug(f"Turn light ON {device_id} with brightness {brightness100} (OBJ={objadr}) sent")

    async def async_set_alarm_state(self, device_id: str, mode: int):
        """Set alarm state for HS-Safety module.
        
        Args:
            device_id: Device ID (MI address for HS-Safety, e.g., "MI0301")
            mode: Alarm mode (0=Unscharf, 1=Extern Scharf, 2=Intern 2 Scharf, 3=Intern 1 Scharf)
        """
        try:
            device = self.devices.get(device_id)
            if not device:
                _LOGGER.warning(f"Device {device_id} not found for alarm control")
                return

            # HS-Safety uses the base OBJ address (EE_LC_ADR) stored during registration
            # This is the objadr from paket.objsrc when D0_ACK_TYP was received
            objadr = device.objadr
            if objadr is None:
                _LOGGER.warning(f"No base object address (EE_LC_ADR) for alarm {device_id} (device.model={device.model})")
                return

            # Validate mode
            if mode not in (0, 1, 2, 3):
                _LOGGER.warning(f"Invalid alarm mode: {mode} (expected: 0-3)")
                return

            # Send command to the base OBJ address (EE_LC_ADR) using OBJ addressing
            await self._packet_sender.send_raw_command(
                ipdst=objadr,  # Send to base OBJ address (EE_LC_ADR)
                ddata=bytes([D0_SET, mode, 0x00]), 
                objsource=self._objadr,  # OBJ address of the bus connector
                mi=self._mi,
                # type8 defaults to SEND_AS_OBJ_GRP (0) for OBJ addressing
            )

            mode_names = {0: "Disarmed", 1: "Armed Away", 2: "Armed Night", 3: "Armed Home"}
            _LOGGER.debug(f"Alarm command {mode_names.get(mode, 'Unknown')} sent to {device_id} (base object address/EE_LC_ADR={objadr})")

        except Exception as e:
            _LOGGER.error(f"Error setting alarm state for {device_id}: {e}", exc_info=True)

    async def async_turn_off_light(self, device_id: str):
        """Turn off light device."""
        device = self.devices.get(device_id)
        if not device:
            _LOGGER.warning(f"No light device with ID {device_id} found")
            return
        objadr = device.objadr
        if objadr is None:
            _LOGGER.warning(f"No objadr for light {device_id}")
            return

        # Example command: Turn off (adjust according to device)
        await self._packet_sender.send_raw_command(
            ipdst=objadr,
            ddata=bytes([D0_SET, 0x00, 0x00]),  # Beispiel OFF-Befehl
            objsource=self._objadr,
            mi=self._mi,
        )
        _LOGGER.debug(f"Turn light OFF {device_id} (OBJ={objadr}) sent")

    async def _enum_timeout_handler(self):
        """Handle ENUM_ALL timeout - start next round or complete enumeration."""
        if self._enum_state == 0:
            return
        
        if self._enum_state < 3:
            # Start next round
            self._enum_state += 1
            _LOGGER.debug(f"[ENUM_ALL] Timeout after round {self._enum_state - 1}, starting round {self._enum_state}")
            await self._send_enum_all_round()
        else:
            # Enumeration complete
            _LOGGER.debug(f"[ENUM_ALL] All 3 rounds completed, enumeration finished")
            self._enum_state = 0
            _LOGGER.debug("[ENUM_ALL] Detail retrieval can now continue")
        
        self._enum_timeout_task = None

    async def _send_enum_all_round(self):
        """Send a single ENUM_ALL round and start timeout timer."""
        try:
            ipdst = MI_ENUM_ALL
            ddata = bytes([D0_ENUM_ALL])
            objsource = 0
            
            _LOGGER.debug(f"[ENUM_ALL] Sending round {self._enum_state}")
            await self._packet_sender.send_raw_command(
                ipdst=ipdst,
                ddata=ddata,
                objsource=objsource,
                mi=self._mi,
                type8=SEND_AS_IP,
            )
            
            # Start timeout timer
            self._enum_timeout_task = asyncio.create_task(
                self._wait_for_timeout()
            )
        except Exception as e:
            _LOGGER.error(f"[ENUM_ALL] Error sending ENUM_ALL round: {e}", exc_info=True)
            self._enum_state = 0
            self._enum_timeout_task = None

    async def _wait_for_timeout(self):
        """Wait for timeout period and then call timeout handler."""
        try:
            await asyncio.sleep(self._enum_timeout_seconds)
            await self._enum_timeout_handler()
        except asyncio.CancelledError:
            # Task was cancelled (timer reset), this is expected
            pass

    async def send_enum_all(self):
        """
        Send a device discovery to the bus.
        
        For small systems (≤250 modules): 3 rounds with 500ms timeout.
        ENUM_ALL is sent to MI address 0xFFFF (MIFFFF).
        - ipdst: MI_ENUM_ALL (0xFFFF = 65535) - MI address for ENUM_ALL
        - mi: MI address of sender (configurator)
        - objsource: 0 (no OBJ address, as it is a module command)
        - ddata: Only [D0_ENUM_ALL] (one byte, value 0x02)
        
        All modules on the bus respond with D0_ACK_TYP.
        """
        # Check if enumeration is already in progress
        if self._enum_state > 0:
            _LOGGER.warning("[ENUM_ALL] Enumeration already in progress, ignoring request")
            return
        
        try:
            # Initialize enumeration state
            self._enum_state = 1
            
            # Start first round
            await self._send_enum_all_round()

        except Exception as e:
            _LOGGER.error(f"[ENUM_ALL] Error starting ENUM_ALL: {e}", exc_info=True)
            self._enum_state = 0
            if self._enum_timeout_task:
                self._enum_timeout_task.cancel()
                self._enum_timeout_task = None

    def get_known_device(self, device_id: str) -> Optional[Net4HomeDevice]:
        """Get a known device by device_id (case-insensitive lookup)."""
        device = self.devices.get(device_id)
        if device:
            return device
        if isinstance(device_id, str):
            device = self.devices.get(device_id.upper())
            if device:
                return device
            device = self.devices.get(device_id.lower())
            if device:
                return device
            # Match by normalized key (e.g. MI0003 vs mi0003)
            uid = device_id.upper()
            for key, dev in self.devices.items():
                if key.upper() == uid:
                    return dev
        if not device:
            _LOGGER.warning(f"Unknown device: {device_id}")
        return device

    def _find_up_tlh_by_objadr(self, objadr: int) -> Optional[Net4HomeDevice]:
        """Find UP-TLH/UP-T climate device by setpoint object address (objadr + 0)."""
        for device in self.devices.values():
            if (device.device_type == "climate" and device.model in ("UP-TLH", "UP-T") and
                    device.objadr is not None and device.objadr == objadr):
                return device
        return None

    async def async_set_climate_mode(self, device_id: str, hvac_mode: str, target_temp: float = None):
        """Set climate mode using D0_SET_N: bit0 = Heat ON, bit1 = Cool ON.
        
        According to documentation: D0_SET_N, Status, 0 → setpoint object address
        Status: 0 = both off, 1 = heating, 2 = cooling, 3 = both
        """
        device = self.devices.get(device_id)
        if not device:
            _LOGGER.error(f"Device {device_id} not found for setting climate mode")
            return
        
        objadr = device.objadr
        if objadr is None:
            _LOGGER.error(f"Device {device_id} has no objadr set, cannot set climate mode")
            return
        
        mode_byte = 0

        if hvac_mode == "heat" or hvac_mode == 1:
            mode_byte = 0x01  # Bit 0 = heating controller active
        elif hvac_mode == "cool" or hvac_mode == 2:
            mode_byte = 0x02  # Bit 1 = cooling controller active
        elif hvac_mode == "heat_cool" or hvac_mode == "both" or hvac_mode == 3:
            mode_byte = 0x03  # Bit 0 and Bit 1 = both active
        elif hvac_mode == "off" or hvac_mode == 0:
            mode_byte = 0x00  # Both off
        else:
            _LOGGER.warning(f"Unknown HVAC mode: {hvac_mode}, using 'off'")
            mode_byte = 0x00

        # According to documentation: D0_SET_N, Status, 0 → setpoint object address
        ddata = bytes([D0_SET_N, mode_byte, 0x00])

        await self._packet_sender.send_raw_command(
            ipdst=objadr,
            ddata=ddata,
            objsource=self._objadr,
            mi=self._mi,
        )
        _LOGGER.debug(f"Set climate mode {hvac_mode} (D0_SET_N, status=0x{mode_byte:02X}) for {device_id} (OBJ={objadr})")


    async def async_set_temperature(self, device_id: str, temperature: float):
        """Send target temperature to net4home bus."""
        device = self.devices.get(device_id)
        if not device:
            _LOGGER.error(f"Device {device_id} not found for setting temperature")
            return
        
        objadr = device.objadr
        if objadr is None:
            _LOGGER.error(f"Device {device_id} has no objadr set, cannot set temperature")
            return
        
        temp_val = int(round(temperature * 10))  # e.g. 22.5°C ➜ 225
        hi = (temp_val >> 8) & 0xFF
        lo = temp_val & 0xFF

        await self._packet_sender.send_raw_command(
            ipdst=objadr,
            ddata=bytes([D0_SET, hi, lo]),
            objsource=self._objadr,
            mi=self._mi,
        )
        _LOGGER.debug(
            f"Set target temperature {temperature:.1f}°C "
            f"(raw={temp_val}, hi=0x{hi:02X}, lo=0x{lo:02X}) for {device_id} (OBJ={objadr})"
        )
        
        # Immediately update the climate entity with the new target temperature
        # This provides instant feedback without waiting for the bus response
        if device.device_type == 'climate':
            device.targettemp = temperature
            update_data = {"targettemp": temperature}
            async_dispatcher_send(self._hass, f"net4home_update_{device_id.upper()}", update_data)
            _LOGGER.debug(f"Sent immediate update for targettemp={temperature:.1f}°C to {device_id}")

    # ========== Detail Retrieval Queue Management ==========
    
    async def async_start_detail_retrieval(self):
        """Start the continuous detail queue manager."""
        if self._detail_queue_running:
            _LOGGER.debug("Detail queue already running")
            return
        
        if self._detail_queue is None:
            self._detail_queue = asyncio.Queue()
        
        self._detail_queue_running = True
        self._detail_queue_task = asyncio.create_task(self._async_process_detail_queue())
        _LOGGER.info("Detail retrieval queue manager started")
        
        # On start: Load all pending devices into queue
        await self._async_load_pending_devices_to_queue()

    async def async_activate_all_sensors(self):
        """Send D0_REQ to all registered sensor devices to activate them and trigger value broadcasts."""
        sensor_count = 0
        for device_id, device in self.devices.items():
            if device.device_type == "sensor" and device_id.startswith("OBJ"):
                # Extract OBJ address from device_id (format: OBJ00003, OBJ26404, etc.)
                try:
                    obj_addr = int(device_id[3:])  # Remove "OBJ" prefix
                    _LOGGER.info(f"Activating sensor {device_id} (OBJ=0x{obj_addr:04X})")
                    await self._packet_sender.send_raw_command(
                        ipdst=obj_addr,
                        ddata=bytes([D0_REQ, 0x00, 0x00]),
                        objsource=self._objadr,
                        mi=self._mi,
                        type8=SEND_AS_OBJ_GRP,  # Send to OBJ address
                    )
                    sensor_count += 1
                    await asyncio.sleep(0.2)  # Small delay between requests to avoid flooding
                except (ValueError, IndexError) as e:
                    _LOGGER.error(f"Failed to parse OBJ address from {device_id}: {e}")
        
        _LOGGER.info(f"Sent activation requests to {sensor_count} sensors")

    async def async_refresh_preset_values_up_tlh(self):
        """Request 0xF0 (presetday/presetnight) for UP-TLH/UP-T climate devices that have no preset values yet.
        Used at startup for devices loaded from config with detail_status=completed (0xF0 is never re-requested otherwise)."""
        for device_id, device in self.devices.items():
            if (device.device_type != "climate" or device.model not in ("UP-TLH", "UP-T") or
                    (getattr(device, "presetday", None) is not None and getattr(device, "presetnight", None) is not None)):
                continue
            if not device_id.startswith("MI"):
                continue
            try:
                mi_addr = int(device_id[2:], 16)
                _LOGGER.info(f"Refreshing preset values (0xF0) for {device_id}")
                await self._packet_sender.send_raw_command(
                    ipdst=mi_addr,
                    ddata=bytes([D0_ENABLE_CONFIGURATION, D1_ENABLE_CONFIGURATION_OK_BYTE, 0x00]),
                    objsource=self._objadr,
                    mi=self._mi,
                    type8=SEND_AS_IP,
                )
                await asyncio.sleep(0.5)
                await self._packet_sender.send_raw_command(
                    ipdst=mi_addr,
                    ddata=bytes([D0_RD_MODULSPEC_DATA, 0xF0, 0x00]),
                    objsource=self._objadr,
                    mi=self._mi,
                    type8=SEND_AS_IP,
                )
                await asyncio.sleep(0.5)
            except (ValueError, Exception) as e:
                _LOGGER.warning(f"Failed to refresh preset values for {device_id}: {e}")

    async def async_stop_detail_retrieval(self):
        """Stop the detail queue manager."""
        self._detail_queue_running = False
        if self._detail_queue_task:
            self._detail_queue_task.cancel()
            try:
                await self._detail_queue_task
            except asyncio.CancelledError:
                pass
        _LOGGER.info("Detail retrieval queue manager stopped")

    async def async_queue_device_for_details(self, device_id: str):
        """Add a device to the detail queue (called at D0_ACK_TYP)."""
        device = self.devices.get(device_id)
        if not device:
            _LOGGER.warning(f"Device {device_id} not found for detail queue")
            return
        
        # Check if details have already been successfully retrieved
        if device.detail_status == "completed":
            _LOGGER.debug(f"Device {device_id} already has completed detail retrieval, skipping queue")
            return
        
        # Setze Status auf pending (nur wenn noch nicht completed)
        device.detail_status = "pending"
        device.discovered_at = datetime.now()
        
        # Speichere Status in Config Entry
        await self._async_save_device_detail_status(device_id, "pending")
        
        # Add to queue (if queue is running)
        if self._detail_queue is not None:
            await self._detail_queue.put(device_id)
            _LOGGER.info(f"Device {device_id} ({device.model}) queued for detail retrieval")
        else:
            _LOGGER.warning(f"Detail queue not initialized, cannot queue {device_id}")

    async def _async_process_detail_queue(self):
        """Main loop for detail queue processing."""
        initial_delay_applied = False
        _LOGGER.debug("Detail queue worker loop started")
        
        while self._detail_queue_running:
            try:
                # Wait if ENUM_ALL is active
                if self._enum_state > 0:
                    _LOGGER.debug(f"ENUM_ALL in progress (state={self._enum_state}), pausing detail retrieval")
                    await asyncio.sleep(0.5)  # Check every 500ms
                    continue
                
                # Initial delay beim ersten Start (nur wenn ENUM_ALL nicht aktiv war)
                if not initial_delay_applied:
                    _LOGGER.debug(f"Applying initial delay of {self._detail_initial_delay} seconds")
                    await asyncio.sleep(self._detail_initial_delay)
                    initial_delay_applied = True
                    _LOGGER.debug("Initial delay completed, starting detail retrieval")
                
                # Wait for device in queue (with timeout for graceful shutdown)
                try:
                    _LOGGER.debug(f"Waiting for device from queue (queue size: {self._detail_queue.qsize() if self._detail_queue else 'N/A'})")
                    device_id = await asyncio.wait_for(
                        self._detail_queue.get(), 
                        timeout=1.0
                    )
                    _LOGGER.info(f"Processing device {device_id} from detail queue")
                except asyncio.TimeoutError:
                    continue
                
                # Process device (with timeout so one stuck device does not block the queue)
                _LOGGER.debug(f"Calling _async_fetch_device_details for {device_id} (timeout={self._detail_fetch_timeout}s)")
                try:
                    await asyncio.wait_for(
                        self._async_fetch_device_details(device_id),
                        timeout=self._detail_fetch_timeout,
                    )
                except asyncio.TimeoutError:
                    device = self.devices.get(device_id)
                    if device:
                        device.detail_status = "pending"
                        await self._async_save_device_detail_status(device_id, "pending")
                        if self._detail_queue is not None and self._detail_queue_running:
                            await self._detail_queue.put(device_id)
                        _LOGGER.warning(
                            f"Detail retrieval for {device_id} ({getattr(device, 'model', '?')}) timed out after "
                            f"{self._detail_fetch_timeout}s, re-queued as pending"
                        )
                    else:
                        _LOGGER.warning(f"Detail retrieval for {device_id} timed out after {self._detail_fetch_timeout}s, device not found")
                    # Continue with next device in queue
                
                # Rate limiting: Wait between queries (increased to avoid bus overload)
                await asyncio.sleep(self._detail_rate_limit)
                
            except asyncio.CancelledError:
                _LOGGER.debug("Detail queue processing cancelled")
                break
            except Exception as e:
                _LOGGER.error(f"Error in detail queue processing: {e}", exc_info=True)
                await asyncio.sleep(1.0)  # Pause on error (reduced for more traffic)

    async def _async_fetch_device_details(self, device_id: str):
        """Perform detail query for a device."""
        device = self.devices.get(device_id)
        if not device:
            _LOGGER.warning(f"Device {device_id} not found for detail retrieval")
            return
        
        # Check if details have already been successfully retrieved
        if device.detail_status == "completed":
            # Exception: UP-TLH/UP-T with missing presetday/presetnight - request only 0xF0 then skip full fetch
            if (device.model in ("UP-TLH", "UP-T") and
                    (getattr(device, "presetday", None) is None or getattr(device, "presetnight", None) is None) and
                    device_id.startswith("MI")):
                try:
                    mi_addr = int(device_id[2:], 16)
                    _LOGGER.info(f"Device {device_id} completed but presetday/presetnight missing, requesting 0xF0 only")
                    await self._packet_sender.send_raw_command(
                        ipdst=mi_addr,
                        ddata=bytes([D0_ENABLE_CONFIGURATION, D1_ENABLE_CONFIGURATION_OK_BYTE, 0x00]),
                        objsource=self._objadr,
                        mi=self._mi,
                        type8=SEND_AS_IP,
                    )
                    await asyncio.sleep(0.5)
                    await self._packet_sender.send_raw_command(
                        ipdst=mi_addr,
                        ddata=bytes([D0_RD_MODULSPEC_DATA, 0xF0, 0x00]),
                        objsource=self._objadr,
                        mi=self._mi,
                        type8=SEND_AS_IP,
                    )
                    await asyncio.sleep(0.5)
                except (ValueError, Exception) as e:
                    _LOGGER.warning(f"Failed to request 0xF0 for {device_id}: {e}")
            else:
                _LOGGER.debug(f"Device {device_id} already has completed detail retrieval, skipping")
            return
        
        device.detail_status = "in_progress"
        device.last_detail_request = datetime.now()
        await self._async_save_device_detail_status(device_id, "in_progress")
        
        try:
            _LOGGER.debug(f"Fetching details for device {device_id} ({device.model}, type: {device.device_type})")
            
            # Distinguish between MI devices (modules) and OBJ devices (child devices)
            # IMPORTANT: A device with via_device is ALWAYS an OBJ device (child device),
            # even if device_id starts with "MI". Only devices WITHOUT via_device
            # and with device_id.startswith("MI") are real MI devices (modules).
            if device.via_device:
                # Device has via_device -> it is an OBJ device (child device)
                is_mi_device = False
                is_obj_device = True
            else:
                # Device has no via_device -> check device_id
                is_mi_device = device_id.startswith("MI")
                is_obj_device = device_id.startswith("OBJ")
            
            if is_mi_device:
                # MI devices (modules): Perform hardware type-specific detail queries
                # Check if module type information is available
                if device.module_type is None or (device.ns is None and device.na is None and device.nm is None):
                    _LOGGER.warning(
                        f"Module type information not yet available for {device_id}, "
                        f"skipping detail queries. module_type={device.module_type}, "
                        f"ns={device.ns}, na={device.na}, nm={device.nm}"
                    )
                    # Mark as pending so it will be retried later
                    device.detail_status = "pending"
                    await self._async_save_device_detail_status(device_id, "pending")
                    return
                
                # Hole MI-Adresse
                mi_addr = int(device_id[2:], 16)
                
                # Aktiviere Konfigurationsmodus vor den Detailabfragen (3 Bytes wie Konfigurator: 2A D3 00)
                _LOGGER.debug(f"Enabling configuration mode for {device_id} (MI={mi_addr:04X})")
                await self._packet_sender.send_raw_command(
                    ipdst=mi_addr,
                    ddata=bytes([D0_ENABLE_CONFIGURATION, D1_ENABLE_CONFIGURATION_OK_BYTE, 0x00]),
                    objsource=self._objadr,
                    mi=self._mi,
                    type8=SEND_AS_IP,  
                )
                
                _LOGGER.debug(f"Configuration mode enabled for {device_id}")
                await asyncio.sleep(0.5)
           
           
                # Basierend auf Modultyp-Eigenschaften Abfragen senden xxx
                # 1. Aktoren abfragen (wenn na > 0)
                
                if device.na and device.na > 0:
                    # Send D0_RD_ACTOR_DATA for each configured channel (0 to na-1)
                    for channel in range(device.na):
                        await self._packet_sender.send_raw_command(
                            ipdst=mi_addr,
                            ddata=bytes([D0_RD_ACTOR_DATA, channel]),
                            objsource=self._objadr,
                            mi=self._mi,
                            type8=SEND_AS_IP,  
                        )
                        _LOGGER.debug(f"Sent D0_RD_ACTOR_DATA for {device_id} (channel={channel}, na={device.na})")
                        # Short pause between requests so responses can be processed
                        await asyncio.sleep(0.1)
                    

              
                # 2. Sensoren abfragen (wenn ns > 0)
                if device.ns and device.ns > 0:
                    # Send D0_RD_SENSOR_DATA for each configured channel (0 to ns-1)
                    for channel in range(device.ns):
                        await self._packet_sender.send_raw_command(
                            ipdst=mi_addr,
                            ddata=bytes([D0_RD_SENSOR_DATA, channel, 0x00]),
                            objsource=self._objadr,
                            mi=self._mi,
                            type8=SEND_AS_IP,  
                        )
                        _LOGGER.debug(f"Sent D0_RD_SENSOR_DATA for {device_id} (channel={channel}, ns={device.ns})")
                        # Short pause between requests so responses can be processed
                        await asyncio.sleep(0.1)
                    
                    # Wait after all sensor queries so last responses can be processed
                    await asyncio.sleep(0.2)
                
                # Warte zwischen Aktor- und Sensor-Abfragen
                if device.na and device.na > 0 and device.ns and device.ns > 0:
                    await asyncio.sleep(0.3)
                
                # 3. ModulSpec-Daten abfragen (wenn nm > 0)
                if device.nm and device.nm > 0:
                    # Special case: UP-TLH and UP-T need ModulSpec data for all 3 sensors (index 0, 1, 2)
                    # as well as special indices 0xF0 (day/night preset) and 0xF1 (heat/cool object addresses)
                    if device.model in ('UP-TLH', 'UP-T'):
                        # For UP-TLH/UP-T: Query for all 3 sensors (index 0, 1, 2)
                        
                        await self._packet_sender.send_raw_command(
                            ipdst=mi_addr,
                            ddata=bytes([D0_RD_MODULSPEC_DATA, 0xFF, 0x00]),
                            objsource=self._objadr,
                            mi=self._mi,
                            type8=SEND_AS_IP,
                        )
                        await asyncio.sleep(0.5)

                        # Additional special indices for UP-TLH/UP-T
                        # Day/night preset (0xF0)
                        await self._packet_sender.send_raw_command(
                            ipdst=mi_addr,
                            ddata=bytes([D0_RD_MODULSPEC_DATA, 0xF0, 0x00]),
                            objsource=self._objadr,
                            mi=self._mi,
                            type8=SEND_AS_IP,
                        )
                        await asyncio.sleep(0.5)
                        
                        # Heat/Cool Objektadressen (0xF1)
                        await self._packet_sender.send_raw_command(
                            ipdst=mi_addr,
                            ddata=bytes([D0_RD_MODULSPEC_DATA, 0xF1, 0x00]),
                            objsource=self._objadr,
                            mi=self._mi,
                            type8=SEND_AS_IP,
                        )
                        await asyncio.sleep(0.5)
                        

                        for modulspec_index in range(3):
                            await self._packet_sender.send_raw_command(
                                ipdst=mi_addr,
                                ddata=bytes([D0_RD_MODULSPEC_DATA, modulspec_index, 0x00]),
                                objsource=self._objadr,
                                mi=self._mi,
                                type8=SEND_AS_IP,  
                            )
                            # Rate Limiting zwischen ModulSpec-Abfragen
                            if modulspec_index < 2:
                                await asyncio.sleep(0.5)

                        # Nach 0xF1: D0_REQ an die Basisadresse senden, um targettemp zu lesen
                        # Laut Dokumentation: D0_REQ, 0, 0 → Sollwert-Objektadresse (objadr + 0)
                        if device.objadr is not None:
                            await self._packet_sender.send_raw_command(
                                ipdst=device.objadr,
                                ddata=bytes([D0_REQ, 0x00, 0x00]),
                                objsource=self._objadr,
                                mi=self._mi,
                            )
                            _LOGGER.debug(f"Sent D0_REQ for targettemp to {device_id} (OBJ={device.objadr})")
                        else:
                            _LOGGER.warning(f"Cannot send D0_REQ for {device_id}: objadr not yet set (0xF1 packet may not have arrived)")
                        
                        _LOGGER.debug(f"Sent D0_RD_MODULSPEC_DATA for {device_id} (UP-TLH/UP-T, 3 sensors + 0xF0, 0xF1)")
                    elif device.model == "HS-Time":
                        # For HS-Time: Query for module info (0xFF) to get base address
                        await self._packet_sender.send_raw_command(
                            ipdst=mi_addr,
                            ddata=bytes([D0_RD_MODULSPEC_DATA, 0xFF, 0x00]),
                            objsource=self._objadr,
                            mi=self._mi,
                            type8=SEND_AS_IP,
                        )
                        _LOGGER.debug(f"Sent D0_RD_MODULSPEC_DATA for {device_id} (HS-Time, 0xFF for Modul-Info)")
                        await asyncio.sleep(0.2)
                    elif device.model == "UP-LCD" or device.module_type == PLATINE_HW_IS_LCD3:
                        # For UP-LCD: Request line 0 (configuration) to get adrUK (object address)
                        # Line 0 contains TCfg_LCD3 with adrUK in bytes 0-1 (Big Endian)
                        # Request format: D0_RD_MODULSPEC_DATA, High-Byte, Low-Byte
                        # For line 0: High-Byte = 0, Low-Byte = 0
                        await self._packet_sender.send_raw_command(
                            ipdst=mi_addr,
                            ddata=bytes([D0_RD_MODULSPEC_DATA, 0x00, 0x00]),  # Line 0 (Big Endian: 0x0000)
                            objsource=self._objadr,
                            mi=self._mi,
                            type8=SEND_AS_IP,
                        )
                        _LOGGER.debug(f"Sent D0_RD_MODULSPEC_DATA for {device_id} (UP-LCD, line 0) to get object address (adrUK)")
                        await asyncio.sleep(0.2)
                    else:
                        # For other modules: Start with index 0 (3 bytes: command, index, 0x00)
                        await self._packet_sender.send_raw_command(
                            ipdst=mi_addr,
                            ddata=bytes([D0_RD_MODULSPEC_DATA, 0x00, 0x00]),  # Index 0
                            objsource=self._objadr,
                            mi=self._mi,
                            type8=SEND_AS_IP,  
                        )
                        _LOGGER.debug(f"Sent D0_RD_MODULSPEC_DATA for {device_id} (nm={device.nm})")
                        # Warte kurz, damit das Modul antworten kann
                        await asyncio.sleep(0.3)
                
                # Warte zwischen Sensor- und ModulSpec-Abfragen
                if device.ns and device.ns > 0 and device.nm and device.nm > 0:
                    await asyncio.sleep(0.3)
                
                # Wait additionally so all responses can be processed
                # before we mark the device as "completed"
                await asyncio.sleep(0.1)
                
                _LOGGER.debug(f"Hardware type-specific detail queries for {device_id} completed")
            elif is_obj_device:
                # OBJ devices (child devices) need status query
                # Perform detail queries based on device type
                if device.device_type in ("light", "switch", "cover"):
                    # For actors: Query status (D0_REQ leads to D0_ACTOR_ACK)
                    await self.async_request_status(device_id)
                elif device.device_type == "climate":
                    # For climate: Query status
                    await self.async_request_status(device_id)
                elif device.device_type == "binary_sensor":
                    # For binary sensors: Query status
                    await self.async_request_status(device_id)
                elif device.device_type == "sensor":
                    # For sensors: Query status
                    await self.async_request_status(device_id)
                else:
                    # For unknown types: Query status
                    await self.async_request_status(device_id)
            else:
                # Unbekanntes Format - markiere als completed
                _LOGGER.warning(f"Unknown device ID format: {device_id}")
            
            # Mark as completed (for MI devices already set, for OBJ devices after status query)
            device.detail_status = "completed"
            device.detail_retry_count = 0
            await self._async_save_device_detail_status(device_id, "completed")
            _LOGGER.debug(f"Detail retrieval completed for {device_id}")
            
        except Exception as e:
            device.detail_retry_count += 1
            if device.detail_retry_count < 3:
                device.detail_status = "pending"
                await self._async_save_device_detail_status(device_id, "pending")
                # Back to queue with delay
                retry_delay = 3.0 * device.detail_retry_count  # Exponential backoff (reduced for more traffic)
                _LOGGER.warning(
                    f"Detail retrieval failed for {device_id}, retrying ({device.detail_retry_count}/3) "
                    f"after {retry_delay}s: {e}"
                )
                await asyncio.sleep(retry_delay)
                if self._detail_queue is not None:
                    await self._detail_queue.put(device_id)
            else:
                device.detail_status = "failed"
                await self._async_save_device_detail_status(device_id, "failed")
                _LOGGER.error(f"Detail retrieval failed for {device_id} after 3 retries: {e}")

    async def _async_load_pending_devices_to_queue(self):
        """Load all pending devices into the queue on start."""
        pending_count = 0
        for device_id, device in self.devices.items():
            if device.detail_status in ("pending", "in_progress"):
                if self._detail_queue is not None:
                    await self._detail_queue.put(device_id)
                    pending_count += 1
                    _LOGGER.debug(f"Restored pending device {device_id} to detail queue")
        
        if pending_count > 0:
            _LOGGER.info(f"Restored {pending_count} pending devices to detail queue")

    async def _async_save_device_detail_status(self, device_id: str, status: str):
        """Save detail_status in Config Entry Options."""
        if not self._entry:
            return
        
        try:
            devices = dict(self._entry.options.get("devices", {}))
            if device_id in devices:
                devices[device_id]["detail_status"] = status
                devices[device_id]["detail_retry_count"] = self.devices[device_id].detail_retry_count
                if self.devices[device_id].last_detail_request:
                    devices[device_id]["last_detail_request"] = self.devices[device_id].last_detail_request.isoformat()
                
                # Update Config Entry
                new_options = dict(self._entry.options)
                new_options["devices"] = devices
                self._hass.config_entries.async_update_entry(self._entry, options=new_options)
                _LOGGER.debug(f"Saved detail_status={status} for {device_id}")
        except Exception as e:
            _LOGGER.error(f"Failed to save detail_status for {device_id}: {e}")

