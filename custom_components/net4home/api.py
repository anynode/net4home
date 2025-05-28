"""Support for net4home integration."""
import asyncio
import struct
import logging
import binascii
import time

from typing import Optional

from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.device_registry import DeviceInfo

from .helpers import register_device_in_registry
from .models import Net4HomeDevice  
from .n4htools import compress_section, decode_d2b, n4h_parse, platine_typ_to_name_a  

from .const import (
    N4H_IP_PORT,
    DEFAULT_MI,
    DEFAULT_OBJADR,
    N4HIP_PT_PAKET,
    N4HIP_PT_PASSWORT_REQ,
    N4HIP_PT_OOB_DATA_RAW,
    D0_SET_IP,
    D0_ENUM_ALL,
    D0_ACK_TYP,
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
    OUT_HW_NR_IS_ONOFF,
    OUT_HW_NR_IS_TIMER,
    OUT_HW_NR_IS_JAL,
)

_LOGGER = logging.getLogger(__name__)

# Receive data from Bus connector
class N4HPacketReceiver:
    def __init__(self):
        self._buffer = bytearray()

    def receive_raw_command(self, data: bytes):
        self._buffer.extend(data)
        packets = []

        while True:
            if len(self._buffer) < 2:
                break  # Not enough data to determine length

            length_bytes = self._buffer[:1]
            total_len = length_bytes[0] - 4

            if len(self._buffer) < total_len:
                break  # Full packet not yet received

            # First 8 bytes after length are uncompressed header
            header = self._buffer[2:6]
            ptype = struct.unpack('<h', self._buffer[6:8])[0]

            if ptype == N4HIP_PT_PAKET:
                payload = self._buffer[8:total_len]
                packets.append((ptype, payload))
            elif ptype == N4HIP_PT_OOB_DATA_RAW:
                _LOGGER.debug(f"Raw OOB data packets received.")
            elif ptype == N4HIP_PT_PASSWORT_REQ:
                _LOGGER.debug(f"Password packet received.")
            else:
                _LOGGER.debug(f"Ignored packet type: {ptype}")

            del self._buffer[:total_len + 8]
        return packets

# Send data to Bus connector
class N4HPacketSender:
    def __init__(self, writer: asyncio.StreamWriter):
        self._writer = writer

    async def send_raw_command(self, ipdst: int, ddata: bytes, objsource: int = 0, mi: int = 65281):

        try:
            # === Paketaufbau im Hexstring
            sendbus = "A10F0000"         # fester Prefix (Paketkennung)
            sendbus += "4E000000"        # reservierte Payload-Länge
            sendbus += "00"              # ?
            sendbus += "00"              # type8 = 0 for OBJ

            # === Adressen codieren
            sendbus += decode_d2b(mi)           # ipsrc
            sendbus += decode_d2b(ipdst)        # ipdst
            sendbus += decode_d2b(objsource)    # objsrc

            # === DDATA vorbereiten: erstes Byte = Länge, dann der eigentliche Payload
            full_ddata = bytes([len(ddata)]) + ddata

            # === Auf 64 Byte auffüllen (128 Hexzeichen)
            ddata_hex = full_ddata.hex().upper().ljust(128, "0")
            sendbus += ddata_hex

            # === Abschluss mit csRX, csCalc, length, posb
            sendbus += "00000000"

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
            #_LOGGER.debug(log_line)
            
            # === Senden
            self._writer.write  (final_bytes)
            await self._writer.drain()

        except Exception as e:
            _LOGGER.error(f"Fehler beim Senden (raw): {e}")
            
class Net4HomeApi:
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
    ):
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
        self._entry = entry
       

    async def async_connect(self):

        self._reader, self._writer = await asyncio.open_connection(self._host, self._port)
        _LOGGER.info(f"Connect with net4home Bus connector at {self._host}:{self._port}")

        packet_bytes = binascii.unhexlify(
            "420000000008ac0f0000cd564c77400c000021203732363343423543464343333646323630364344423338443945363135394535401b0000080700000087000000c000000aac"
        )

        self._writer.write(packet_bytes)
        await self._writer.drain()
        _LOGGER.debug("Credentials to Bus connector sent. Waiting for approval...")

        self._packet_sender = N4HPacketSender(self._writer)


    async def async_reconnect(self, max_attempts: int = 5, base_delay: float = 5.0) -> None:
        for attempt in range(1, max_attempts + 1):
            delay = base_delay * attempt
            _LOGGER.warning(f"Try to reconnect - attempt {attempt}/{max_attempts} in {delay:.1f}s...")

            await asyncio.sleep(delay)

            try:
                await self.async_connect()
                if self._writer and not self._writer.is_closing():
                    _LOGGER.info("Reconnect successful")

                    for device in self.devices.values():
                        if device.device_type == "switch":
                            await self.async_request_status(device.device_id)
                    return
            except Exception as e:
                _LOGGER.error(f"Reconnect fehlgeschlagen (Versuch {attempt}): {e}")

        _LOGGER.error("Maximale Reconnect-Versuche erreicht. Keine Verbindung zum Bus möglich.")


    async def async_disconnect(self):
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            _LOGGER.debug("Connection to net4home Bus connector closed")

    async def async_listen(self):
        _LOGGER.debug("Start listening for bus packets")
        try:
            while True:
                try:
                    data = await self._reader.read(4096)
                    if not data:
                        _LOGGER.warning("Verbindung zum net4home Busconnector wurde geschlossen")
                        await self.async_reconnect()
                        continue
                except (ConnectionResetError, OSError) as e:
                    _LOGGER.error(f"Network error: {e}")
                    await self.async_reconnect()
                    continue
                packets = self._packet_receiver.receive_raw_command(data)
                for ptype, payload in packets:
                    try:
                        ret, paket = n4h_parse(payload)
                    except Exception as e:
                        _LOGGER.error(f"Parsing error: {e}")
                        continue

                    if paket is None:
                        _LOGGER.warning(f"Unable to parse a legit bus packet - {ret} - {payload.hex()}")
                        continue

                    if paket.ddatalen != 0:
                        
                        # Identify the action what we have to do
                        b0 = paket.ddata[0]
                        
                        # Discovered a module, maybe we know it
                        if b0 == D0_ACK_TYP: 
                            device_id = f"MI{paket.ipsrc:04x}"
                            model = platine_typ_to_name_a(paket.ddata[1])
                            sw_version = ""
                            name = device_id

                            _LOGGER.debug(f"ACK_TYP received for device: {device_id} ({model})")

                            try:
                                await register_device_in_registry(
                                    hass=self._hass,
                                    entry=self._entry,
                                    device_id=device_id,
                                    name=name,
                                    model=model,
                                    sw_version=sw_version,
                                    hw_version="",
                                    device_type="module", 
                                    via_device="",
                                    api=self,
                                )
                            except Exception as e:
                                _LOGGER.error(f"Error during registration of device (module) {device_id}: {e}")
                        elif b0 == D0_ACTOR_ACK:
                            device_id = f"OBJ{paket.objsrc:05d}"

                            device = self.devices.get(device_id)
                            if device.device_type == 'switch':
                                is_on = paket.ddata[2] == 1
                                _LOGGER.debug(f"STATUS_INFO_ACK für {device_id}: {'ON' if is_on else 'OFF'}")
                                async_dispatcher_send(self._hass, f"net4home_update_{device_id}", is_on)
                            elif device.device_type == 'timer':
                                is_on = paket.ddata[2] == 1
                                _LOGGER.debug(f"STATUS_INFO_ACK für {device_id}: {'ON' if is_on else 'OFF'}")
                                async_dispatcher_send(self._hass, f"net4home_update_{device_id}", is_on)
                            elif device.device_type == 'cover':
                                is_closed = paket.ddata[2] != 1 
                                _LOGGER.debug(f"STATUS_INFO_ACK für {device_id}: {'CLOSED' if is_on else 'OPEN'}")
                                async_dispatcher_send(self._hass, f"net4home_update_{device_id}", is_closed)

                        elif b0 == D0_RD_ACTOR_DATA_ACK:
                            _LOGGER.debug(f"D0_RD_ACTOR_DATA_ACK identified: {paket.ddata[2]}")
                            
                            b1  = paket.ddata[1] + 1 # channel
                            b2  = paket.ddata[2]     # actor type
                            b8  = paket.ddata[8]     # OBJ hi
                            b9  = paket.ddata[9]     # OBJ lo

                            device_id = f"OBJ{(b8*256+b9):05d}"
                            objadr = (b8 << 8) + b9
                            via_device = f"MI{paket.ipsrc:04x}"

                            # We have a classic switch with ON/OFF feature
                            if b2 == OUT_HW_NR_IS_ONOFF:
                                _LOGGER.debug(f"OUT_HW_NR_IS_ONOFF identified: {device_id}")

                                # Module details
                                b3  = paket.ddata[2]     # time1 hi
                                b4  = paket.ddata[3]     # time1 lo
                                b5  = paket.ddata[4]     # Power Up (0=OFF, 1=ON, 2=ASBEFORE, 3=NoChange, 4=ON100% ) 
                                b6  = paket.ddata[5]     # min
                                b7  = paket.ddata[6]     # Status update
                                b10 = paket.ddata[9]     # time2 hi
                                b11 = paket.ddata[10]    # time2 lo
                                b12 = paket.ddata[11]    # inverted

                                try:
                                    await register_device_in_registry(
                                        hass=self._hass,
                                        entry=self._entry,
                                        device_id=device_id,
                                        name = f"CH{b1}_{device_id[3:]}",
                                        model="Schalter",
                                        sw_version="",
                                        hw_version="",
                                        device_type="switch",
                                        via_device=via_device,
                                        api=self,
                                        objadr=objadr,
                                    )
                                except Exception as e:
                                    _LOGGER.error(f"Error during registration of ONOFF device (channel) {device_id}: {e}")

                            # We have a classic switch with ON/OFF and the timer feature
                            if b2 == OUT_HW_NR_IS_TIMER:
                                _LOGGER.debug(f"OUT_HW_NR_IS_TIMER identified: {device_id}")

                                # Module details
                                b3  = paket.ddata[2]     # time1 hi
                                b4  = paket.ddata[3]     # time1 lo
                                b5  = paket.ddata[4]     # Power Up (0=OFF, 1=ON, 2=ASBEFORE, 3=NoChange, 4=ON100% ) 
                                b6  = paket.ddata[5]     # min
                                b7  = paket.ddata[6]     # Status update
                                b10 = paket.ddata[9]     # time2 hi
                                b11 = paket.ddata[10]    # time2 lo
                                b12 = paket.ddata[11]    # inverted


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
                                    )
                                except Exception as e:
                                    _LOGGER.error(f"Error during registration of TIMER device (channel) {device_id}: {e}")

                            # We have a cover 
                            if b2 == OUT_HW_NR_IS_JAL:

                                _LOGGER.debug(f"OUT_HW_NR_IS_JAL Paket : {' '.join(f'{b:02X}' for b in paket.ddata)}")

                                # Module details
                                b3  = paket.ddata[2]     # time1 hi
                                b4  = paket.ddata[3]     # time1 lo
                                b5  = paket.ddata[4]     # Power Up (0=OFF, 1=ON, 2=ASBEFORE, 3=NoChange, 4=ON100% ) 
                                b6  = paket.ddata[5]     # min
                                b7  = paket.ddata[6]     # Status update
                                b10 = paket.ddata[9]    # OUT_OPTION_DELAYED_ON & OUT_OPTION_UP_DOWN_SWAP
                                b11 = paket.ddata[10]    # Anlaufverzögerung
                                
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
                                    )
                                except Exception as e:
                                    _LOGGER.error(f"Error during registration of COVER device (channel) {device_id}: {e}")

                            # HS-AJ3
                            # 0F 03 2B 00 03 11 04 00 02 02 04 01 00 50 00 74
                            
                            # HS-AR6 
                            # 0E 1F 00 type:04 EV:00 time1:3C Po:02 FF 01 hi:2C lo:25 invert:00 time2:01 Pu:00 15
                            # len:0E 1F ch:01 type:04 EV:00 time1:3C Po:02 FF 00 hi:2C lo:26 invert:00 time2:01 Pu:00 15
                            # len:0E 1F ch:02 type:01 EV:FF time1:FF Po:02 FF 01 hi:2C lo:27 invert:00 time2:01 Pu:00 15
                            # len:0E 1F ch:03 type:01 EV:FF time1:FF Po:02 FF 00 hi:2C lo:28 invert:00 time2:01 Pu:00 15
                            # len:0E 1F ch:04 type:04 EV:00 time1:3C Po:02 FF 00 hi:2C lo:29 invert:00 time2:01 Pu:00 15
                            # len:0E 1F ch:05 type:01 EV:40 time1:04 Po:FF 00 0C hi:00 lo:2C invert:2A time2:00 Pu:01 00
                          

                            
                        # Status Info D0_STATUS_INFO
                        elif b0 == D0_STATUS_INFO:
                            device_id = f"OBJ{paket.objsrc:05d}"
                            is_on = paket.ddata[2] == 1

                            _LOGGER.debug(f"STATUS_INFO für {device_id}: {'ON' if is_on else 'OFF'}")
                            async_dispatcher_send(self._hass, f"net4home_update_{device_id}", is_on)

                                                        
        except Exception as e:
            _LOGGER.error(f"Fehler im Listener: {e}")

    async def async_turn_on_switch(self, device_id: str):
        """Sendet ein EIN-Signal an das angegebene Switch-Device."""
        try:
            device = self.devices.get(device_id)
            if not device:
                _LOGGER.warning(f"Kein Gerät mit ID {device_id} gefunden")
                return

            objadr = device.objadr 
            
            if not device:
                _LOGGER.warning(f"Kein Gerät mit ID {device_id} gefunden")
                return
                
            model = device.model
            
            if model == "Schalter":
                await self._packet_sender.send_raw_command(
                    ipdst=objadr,
                    ddata=bytes([D0_SET, 0x64, 0x00]),  
                    objsource=self._objadr,
                    mi=self._mi,
                )
                _LOGGER.debug(f"Schaltbefehl EIN an {device_id} (OBJ={objadr}) gesendet")
            elif model == "Timer":
                await self._packet_sender.send_raw_command(
                    ipdst=objadr,
                    ddata=bytes([D0_TOGGLE , 0x00, 0x00]),  
                    objsource=self._objadr,
                    mi=self._mi,
                )
                _LOGGER.debug(f"Schaltbefehl TOGGLE an {device_id} (OBJ={objadr}) gesendet")
                

        except Exception as e:
            _LOGGER.error(f"Fehler beim Schalten EIN für {device_id}: {e}")

    async def async_turn_off_switch(self, device_id: str):
        """Sendet ein AUS-Signal an das angegebene Switch-Device."""
        try:
            if not device_id.startswith("OBJ"):
                _LOGGER.warning(f"Ungültige device_id: {device_id}")
                return

            device = self.devices.get(device_id)
            objadr = device.objadr if device else None
            
            if objadr is None:
                _LOGGER.warning(f"Keine objadr für {device_id}")
                return

            await self._packet_sender.send_raw_command(
                ipdst=objadr,
                ddata=bytes([D0_SET, 0x00, 0x00]), 
                objsource=self._objadr,
                mi=self._mi,
            )

            _LOGGER.debug(f"Schaltbefehl AUS an {device_id} (OBJ={objadr}) gesendet")

        except Exception as e:
            _LOGGER.error(f"Fehler beim Schalten AUS für {device_id}: {e}")

    async def async_request_status(self, device_id: str):
        try:
            if not device_id.startswith("OBJ"):
                _LOGGER.warning(f"Invalid device_id: {device_id} for status request.")
                return

            device = self.devices.get(device_id)
            objadr = device.objadr if device else None

            if objadr is None:
                _LOGGER.warning(f"Missing objadr {device_id}")
                return

            if device.device_type == "module":
                _LOGGER.warning(f"No request necessary for {device_id}")
                return

            await self._packet_sender.send_raw_command(
                ipdst=objadr,
                ddata=bytes([D0_REQ, 0x00, 0x00]), 
                objsource=self._objadr,
                mi=self._mi,
            )

            _LOGGER.debug(f"Status request for {device_id} (OBJ={objadr}) sent")
        except Exception as e:
            _LOGGER.error(f"Error sending status request for {device_id}: {e}")


    async def async_open_cover(self, device_id: str):
        # Send open signal to net4home device
        try:
            if not device_id.startswith("OBJ"):
                _LOGGER.warning(f"Ungültige device_id: {device_id}")
                return

            device = self.devices.get(device_id)
            objadr = device.objadr if device else None
            
            if objadr is None:
                _LOGGER.warning(f"Keine objadr für {device_id}")
                return

            await self._packet_sender.send_raw_command(
                ipdst=objadr,
                ddata=bytes([D0_SET, 0x03, 0x00]), 
                objsource=self._objadr,
                mi=self._mi,
            )

            _LOGGER.debug(f"Schaltbefehl AUF an {device_id} (OBJ={objadr}) gesendet")

        except Exception as e:
            _LOGGER.error(f"Fehler beim Schalten AUS für {device_id}: {e}")

    async def async_close_cover(self, device_id: str):
        # Send close signal to net4home device
        try:
            if not device_id.startswith("OBJ"):
                _LOGGER.warning(f"Ungültige device_id: {device_id}")
                return

            device = self.devices.get(device_id)
            objadr = device.objadr if device else None
            
            if objadr is None:
                _LOGGER.warning(f"Keine objadr für {device_id}")
                return

            await self._packet_sender.send_raw_command(
                ipdst=objadr,
                ddata=bytes([D0_SET, 0x01, 0x00]), 
                objsource=self._objadr,
                mi=self._mi,
            )

            _LOGGER.debug(f"Schaltbefehl AB an {device_id} (OBJ={objadr}) gesendet")

        except Exception as e:
            _LOGGER.error(f"Fehler beim Schalten AUS für {device_id}: {e}")

    async def async_stop_cover(self, device_id: str):
        # Send stop signal to net4home device
        try:
            if not device_id.startswith("OBJ"):
                _LOGGER.warning(f"Ungültige device_id: {device_id}")
                return

            device = self.devices.get(device_id)
            objadr = device.objadr if device else None
            
            if objadr is None:
                _LOGGER.warning(f"Keine objadr für {device_id}")
                return

            await self._packet_sender.send_raw_command(
                ipdst=objadr,
                ddata=bytes([D0_SET, 0x00, 0x00]), 
                objsource=self._objadr,
                mi=self._mi,
            )

            _LOGGER.debug(f"Schaltbefehl STOP an {device_id} (OBJ={objadr}) gesendet")

        except Exception as e:
            _LOGGER.error(f"Fehler beim Schalten AUS für {device_id}: {e}")
        



    async def send_enum_all(self):
        """Send a device discovery to the bus."""
        try:
            # ENUM_ALL ist ein Broadcast an MI 0xFFFF (65535), ohne spezifische OBJ-Adresse

            await self._packet_sender.send_raw_command(
                ipdst=0xFFFF,  # Broadcast
                ddata=bytes([D0_ENUM_ALL, 0x00, 0x00]),
                objsource=self._objadr,
                mi=self._mi,
            )

            _LOGGER.debug("ENUM_ALL gesendet")

        except Exception as e:
            _LOGGER.error(f"Fehler beim Senden von ENUM_ALL: {e}")
