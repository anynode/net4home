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
    D0_RD_SENSOR_DATA_ACK,
    D0_RD_SENSOR_DATA,
    D0_RD_MODULSPEC_DATA,
    D0_RD_MODULSPEC_DATA_ACK,
    OUT_HW_NR_IS_ONOFF,
    OUT_HW_NR_IS_TIMER,
    OUT_HW_NR_IS_JAL,
    OUT_HW_NR_IS_DIMMER,
    IN_HW_NR_IS_TEMP,
    IN_HW_NR_IS_HUMIDITY,
    IN_HW_NR_IS_LICHT_ANALOG,
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
            # _LOGGER.debug(log_line)
            
            # === Senden
            self._writer.write  (final_bytes)
            await self._writer.drain()

        except Exception as e:
            _LOGGER.error(f"Error sending data (raw): {e}")
            
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
                        if device.device_type == "light":
                            await self.async_request_status(device.device_id)
                    return
            except Exception as e:
                _LOGGER.error(f"Reconnect failed (Try {attempt}): {e}")

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
                        _LOGGER.warning("Connection to net4home Bus connector closed")
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
                            device_id = f"MI{paket.ipsrc:04X}"
                            objadr = None 
                            model = platine_typ_to_name_a(paket.ddata[1])
                            sw_version = ""
                            name = device_id
                            device_type="module"
                            
                            if model == "UP-TLH":
                                device_type="climate"
                                objadr=paket.objsrc
                                
                            _LOGGER.debug(f"ACK_TYP received for device: {device_id} ({device_type}) ({model}) ({objadr})")

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
                                )
                            except Exception as e:
                                _LOGGER.error(f"Error during registration of device (module) {device_id}: {e}")
                                
                        elif b0 == D0_ACTOR_ACK:
                            device_id = f"OBJ{paket.objsrc:05d}"
                            
                            device = self.get_known_device(device_id)
                            if not device:
                                continue

                            _LOGGER.error(f"Device {device.device_type}: {device.model}")

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
                                _LOGGER.debug(f"STATUS_INFO_ACK für {device_id}: {'CLOSED' if is_closed else 'OPEN'}")
                                async_dispatcher_send(self._hass, f"net4home_update_{device_id}", is_closed)

                            elif device.device_type == 'sensor':
                                if device.model == "presetday":
                                    temp = paket.ddata[2] /10
                                    _LOGGER.debug(f"STATUS_INFO_ACK für {device_id}: Preset day {temp}")
                                elif device.model == "presetnight":    
                                    temp = paket.ddata[2] /10
                                    _LOGGER.debug(f"STATUS_INFO_ACK für {device_id}: Preset night {temp}")
                                elif device.model == "targettemp":    
                                    temp = paket.ddata[2] /10
                                    _LOGGER.debug(f"STATUS_INFO_ACK für {device_id}: Target Temperature {temp}")
                                elif device.model == "temperature":    
                                    temp = paket.ddata[2] /10
                                    _LOGGER.debug(f"STATUS_INFO_ACK für {device_id}: Temperature {temp}")
                                else:
                                    continue
                                async_dispatcher_send(self._hass, f"net4home_update_{device_id}", temp)


                            elif device.device_type == 'climate':
                                _LOGGER.debug(f"STATUS_INFO_ACK für {device_id}: ")
                                is_on = paket.ddata[1] == 1
                                temp = paket.ddata[2] /10
                                async_dispatcher_send(self._hass, f"net4home_update_{device_id}", {
                                    "current_temp": temp,
                                    "target_temp": temp,
                                    "is_on": is_on
                                })
                            elif device.device_type == 'light':
                                is_on = paket.ddata[2] >> 7
                                brightness_value = round((paket.ddata[2] & 0x7F) * 255 / 100)
                                _LOGGER.debug(f"STATUS_INFO_ACK für {device_id}: {'ON' if is_on else 'OFF'} {round((paket.ddata[2] & 0x7F))}%")
                                async_dispatcher_send(self._hass,f"net4home_update_{device_id}",{"is_on": is_on, "brightness": brightness_value},)

                            elif device.device_type == 'binary_sensor':
                                is_closed = paket.ddata[2] != 1 
                                _LOGGER.debug(f"STATUS_INFO_ACK für {device_id}: {'CLOSED' if is_closed else 'OPEN'}")
                                async_dispatcher_send(self._hass, f"net4home_update_{device_id}", is_closed)
                                    
                        elif b0 == D0_RD_ACTOR_DATA_ACK:
                            _LOGGER.debug(f"D0_RD_ACTOR_DATA_ACK identified: {paket.ddata[2]}")
                            
                            b1  = paket.ddata[1] + 1 # channel
                            b2  = paket.ddata[2]     # actor type
                            b8  = paket.ddata[8]     # OBJ hi
                            b9  = paket.ddata[9]     # OBJ lo
                            
                            # 0E 1F 00 01 03 84 02 01 01 3E 1D 00 00 00 19          -> Typ 1-10
                            
                            # 10 1F 00 04 00 78 02 23 00 7E 91 00 09 01 1A 00 00    -> HS-AD3e
                            # 10 1F 01 04 00 78 02 23 00 7E 96 00 09 01 1A 00 00
                            # 10 1F 02 01 00 00 02 0A 01 7E 9B 00 00 00 1A 00 00

                            device_id = f"OBJ{(b8*256+b9):05d}"
                            objadr = (b8 << 8) + b9
                            via_device = f"MI{paket.ipsrc:04X}"
                            is_dimmer = False
                            is_jal = False

                            device_obj = self.devices.get(via_device)
                            
                            
                            if device_obj and device_obj.model in ('HS-AD1-1x10V', 'HS-AD3e', 'HS-AD3'):
                                is_dimmer = True
                                
                            if device_obj and device_obj.model in ('HS-AJ3', 'HS-AJ1', 'HS-AJ4-500', 'HS-AJ3-6'):
                                is_jal = True

                            # We have a classic switch with ON/OFF feature
                            if b2 == OUT_HW_NR_IS_ONOFF and not is_dimmer:
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
                            if b2 == OUT_HW_NR_IS_TIMER and not is_dimmer:
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
                            if b2 == OUT_HW_NR_IS_JAL or is_jal:

                                _LOGGER.debug(f"OUT_HW_NR_IS_JAL Paket : {' '.join(f'{b:02X}' for b in paket.ddata)}")

                                # Module details
                                
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

                            if b2 == OUT_HW_NR_IS_ONOFF and is_dimmer:

                                _LOGGER.debug(f"OUT_HW_NR_IS_DIM Paket : {' '.join(f'{b:02X}' for b in paket.ddata)}")

                                # Module details
                                
                                _LOGGER.debug(f"OUT_HW_NR_IS_DIMMER identified: {device_id}")

                                try:
                                    await register_device_in_registry(
                                        hass=self._hass,
                                        entry=self._entry,
                                        device_id=device_id,
                                        name = f"CH{b1}_{device_id[3:]}",
                                        model="Dimmer",
                                        sw_version="",
                                        hw_version="",
                                        device_type="light",
                                        via_device=via_device,
                                        api=self,
                                        objadr=objadr,
                                    )
                                except Exception as e:
                                    _LOGGER.error(f"Error during registration of DIMMER device (channel) {device_id}: {e}")
                                    
                            # HS-AJ3
                            # 0F 03 2B 00 03 11 04 00 02 02 04 01 00 50 00 74
                            
                            # HS-AR6 
                            # 0E 1F 00 type:04 EV:00 time1:3C Po:02 FF 01 hi:2C lo:25 invert:00 time2:01 Pu:00 15
                            # len:0E 1F ch:01 type:04 EV:00 time1:3C Po:02 FF 00 hi:2C lo:26 invert:00 time2:01 Pu:00 15
                            # len:0E 1F ch:02 type:01 EV:FF time1:FF Po:02 FF 01 hi:2C lo:27 invert:00 time2:01 Pu:00 15
                            # len:0E 1F ch:03 type:01 EV:FF time1:FF Po:02 FF 00 hi:2C lo:28 invert:00 time2:01 Pu:00 15
                            # len:0E 1F ch:04 type:04 EV:00 time1:3C Po:02 FF 00 hi:2C lo:29 invert:00 time2:01 Pu:00 15
                            # len:0E 1F ch:05 type:01 EV:40 time1:04 Po:FF 00 0C hi:00 lo:2C invert:2A time2:00 Pu:01 00
                          

                        elif b0 == D0_RD_SENSOR_DATA_ACK:
                            _LOGGER.debug(f"D0_RD_SENSOR_DATA_ACK identified: Typ: {paket.ddata[2]} - {' '.join(f'{b:02X}' for b in paket.ddata)}")

            
                            b1  = paket.ddata[1] + 1 # channel
                            b2  = paket.ddata[2]     # actor type (1=ON_CLOSE, 5=ON_SHORT_CLOSE__ON_LONG_CLOSE)

                            offSet1   = 0 +2 + 1
                            offSet2   = offSet1 + 5
                            offSet3   = 0 +2 + 1
                            offSet4   = 0 +2 + 1
                            offSetAdr = offSet2 + 5
                            _LOGGER.debug(f"D0_RD_SENSOR_DATA_ACK identified: off: {offSetAdr} - Typ: {paket.ddata[2]} - len: {len(paket.ddata)}")

                            if len(paket.ddata) <= offSetAdr:
                                continue
                            
#  adrSelf := ddata[EE_OFFSET_ADR]*256+ ddata[EE_OFFSET_ADR+1];
#  EE_OFFSET_PIN_IS                = 0 +2;
#  EE_OFFSET_FKT1                  = EE_OFFSET_PIN_IS + 1;
#  EE_OFFSET_FKT2                  = EE_OFFSET_FKT1   + EE_IN_TAB_ADRFKT_LEN;
#  EE_OFFSET_ADR                   = EE_OFFSET_FKT2   + EE_IN_TAB_ADRFKT_LEN;
#  EE_OFFSET_MEM_STATE             = EE_OFFSET_ADR    + 2;
#  EE_OFFSET_TIMER                 = EE_OFFSET_MEM_STATE + 1;
#  EE_NCNO_INV                     = EE_OFFSET_TIMER     + 2;
#  EE_OFFSET_FKT3                  = EE_NCNO_INV         + 1;
#  EE_OFFSET_FKT4                  = EE_OFFSET_FKT3      + 5;

                            device_id = f"OBJ{(offSetAdr*256+offSetAdr+1):05d}"
                            objadr = (offSetAdr << 8) + offSetAdr+1
                            via_device = f"MI{paket.ipsrc:04X}"
                            device_obj = self.devices.get(via_device)

# 10 00 01 2C 27 35 40 07 00 00 03 0E 11 01
#2025-05-29 08:49:10.428 DEBUG (MainThread) [custom_components.net4home.n4htools] MI 0025   00000 >  65281 22 - 10 00 01 29 72 35 00 00 40 05 FF 00 06 x:09 C5 01 00 03 00 40 0F FF D0_RD_SENSOR_DATA_ACK
#2025-05-29 08:49:10.508 DEBUG (MainThread) [custom_components.net4home.n4htools] MI 0025   00000 >  65281 22 - 10 01 01 27 77 35 00 00 40 05 FF 00 06 09 C6 01 00 03 00 40 0F FF D0_RD_SENSOR_DATA_ACK
#2025-05-29 08:49:10.593 DEBUG (MainThread) [custom_components.net4home.n4htools] MI 0025   00000 >  65281 22 - 10 02 01 29 7C 35 00 00 40 05 FF 00 06 09 C7 01 00 03 00 40 0F FF D0_RD_SENSOR_DATA_ACK
#2025-05-29 08:49:10.688 DEBUG (MainThread) [custom_components.net4home.n4htools] MI 0025   00000 >  65281 22 - 10 03 01 28 3E 35 00 00 40 05 FF 00 06 09 C8 01 00 03 00 40 0F FF D0_RD_SENSOR_DATA_ACK

                            _LOGGER.debug(f"D0_RD_SENSOR_DATA_ACK identified: model: {device_obj.model} - {via_device} - {objadr}")

                            if device_obj and device_obj.model in ('UP-S4'):
                                is_sensor = True

                            if b2 == is_sensor:
                                _LOGGER.debug(f"OUT_HW_NR_IS_ONOFF identified: {device_id}")

                                try:
                                    await register_device_in_registry(
                                        hass=self._hass,
                                        entry=self._entry,
                                        device_id=device_id,
                                        name = f"CH{b1}_{device_id[3:]}",
                                        model="sensor",
                                        sw_version="",
                                        hw_version="",
                                        device_type="binary_sensor",
                                        via_device=via_device,
                                        api=self,
                                        objadr=objadr,
                                    )
                                except Exception as e:
                                    _LOGGER.error(f"Error during registration of SENSOR device (channel) {device_id}: {e}")


                            
                        elif b0 == D0_RD_MODULSPEC_DATA_ACK:
                            _LOGGER.debug(f"D0_RD_MODULSPEC_DATA_ACK identified: Typ: {paket.ddata[1]} - {' '.join(f'{b:02X}' for b in paket.ddata)}")

                            b1  = paket.ddata[1] 
                            obj_heat = None
                            obj_cool = None
                            presetday = None
                            presetnight = None

                            device_id = f"MI{paket.ipsrc:04X}"
                            device = self.devices.get(device_id)
                            objadr = device.objadr if device else None
                            
                            if objadr is None:
                                _LOGGER.warning(f"Objadr für Gerät {device_id} nicht gefunden, Abbruch der Verarbeitung")
                                continue                             
                                
                            if b1 == 0xF0: # Tag/Nachtwert
                                presetday   = (paket.ddata[2] * 256+paket.ddata[3]) / 10
                                presetnight = (paket.ddata[2] * 256+paket.ddata[3]) / 10
                                sensor_obj = objadr
                                sensor_type = "temperature"


                            if b1 == 0xF1:
                                b2  = paket.ddata[2]
                                b3  = paket.ddata[3]
                                b6  = paket.ddata[6]
                                b7  = paket.ddata[7]
                                b8  = paket.ddata[8]
                                b9  = paket.ddata[9]
                                device_id = f"OBJ{(b2*256+b3):05d}"
                                objadr = (b2 << 8) + b3

                                sensor_obj = objadr
                                sensor_type = "temperature"
                                obj_heat = (b6 << 8) + b7 
                                obj_cool = (b8 << 8) + b9
                                _LOGGER.debug(f"D0_RD_MODULSPEC_DATA_ACK identified: objadr: {objadr} - obj_heat: {obj_heat} - obj_cool: {obj_cool}")
                                
                                # Target temperature
                                await register_device_in_registry(
                                    hass=self._hass,
                                    entry=self._entry,
                                    device_id=f"OBJ{(sensor_obj):05d}",
                                    name=f"{sensor_type.capitalize()} Sensor {sensor_obj}",
                                    model="targettemp",
                                    sw_version="",
                                    hw_version="",
                                    device_type="sensor",
                                    via_device=f"MI{paket.ipsrc:04X}",
                                    api=self,
                                    objadr=sensor_obj
                                )       

                                # Preset day
                                await register_device_in_registry(
                                    hass=self._hass,
                                    entry=self._entry,
                                    device_id=f"OBJ{(sensor_obj+1):05d}",
                                    name=f"{sensor_type.capitalize()} Sensor {sensor_obj+1}",
                                    model="presetday",
                                    sw_version="",
                                    hw_version="",
                                    device_type="sensor",
                                    via_device=f"MI{paket.ipsrc:04X}",
                                    api=self,
                                    objadr=sensor_obj
                                )       

                                # Preset night
                                await register_device_in_registry(
                                    hass=self._hass,
                                    entry=self._entry,
                                    device_id=f"OBJ{(sensor_obj+2):05d}",
                                    name=f"{sensor_type.capitalize()} Sensor {sensor_obj+2}",
                                    model="presetnight",
                                    sw_version="",
                                    hw_version="",
                                    device_type="sensor",
                                    via_device=f"MI{paket.ipsrc:04X}",
                                    api=self,
                                    objadr=sensor_obj
                                )   
                                    
                            if b1 < 0x80: # 3 Sensoren für ein UP-TLH (UP-T prüfen)
                            
                                if b1 == 0: 
                                    sensor_obj = objadr+3
                                    sensor_type = "temperature"
                                if b1 == 1: 
                                    sensor_obj = objadr+4
                                    sensor_type = "humidity"
                                if b1 == 2: 
                                    sensor_obj = objadr+5
                                    sensor_type = "illuminance"
                                    
                                if sensor_type:
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
                                    
                        elif b0 == D0_VALUE_ACK:
                            device_id = f"MI{paket.ipsrc:04X}"

                            #if device_id not in self.devices:
                            #    _LOGGER.debug(f"unbekannt D0_VALUE_ACK für {device_id} – Typ: {paket.ddata[1]}")
                            #    return

                            _LOGGER.debug(f"D0_VALUE_ACK für {device_id} – Typ: {paket.ddata[1]}")

                            sensor_updates = {}

                            if paket.ddata[1] == IN_HW_NR_IS_TEMP:
                                i_analog_value = paket.ddata[3] * 256 + paket.ddata[4]
                                if i_analog_value > 0x8000:
                                    i_analog_value -= 0x10000
                                i_analog_value = (i_analog_value * 10) // 16
                                value = round(i_analog_value / 10, 1)
                                sensor_updates["temperature"] = value

                            elif paket.ddata[1] == IN_HW_NR_IS_HUMIDITY:
                                value = paket.ddata[3] * 256 + paket.ddata[4]
                                sensor_updates["humidity"] = value

                            elif paket.ddata[1] == IN_HW_NR_IS_LICHT_ANALOG:
                                value = paket.ddata[3] * 256 + paket.ddata[4]
                                sensor_updates["illuminance"] = value

                            if sensor_updates:
                                _LOGGER.debug(f"Sending sensor data for {device_id}: {sensor_updates}")
                                async_dispatcher_send(
                                    self._hass,
                                    f"net4home_update_{device_id}",
                                    sensor_updates
                                )
                                                                            
                        
                        elif b0 == D0_STATUS_INFO:
                            device_id = f"OBJ{paket.objsrc:05d}"
                            is_on = paket.ddata[2] == 1
                            
                            if paket.ddata[3] == OUT_HW_NR_IS_DIMMER:
                                is_on = paket.ddata[2] >> 7
                                brightness_value = round((paket.ddata[2] & 0x7F) * 255 / 100)
                                _LOGGER.debug(f"STATUS_INFO für {device_id}: {'ON' if is_on else 'OFF'} {brightness_value}%")
                                async_dispatcher_send(
                                    self._hass,
                                    f"net4home_update_{device_id}",
                                    {
                                        "is_on": is_on,
                                        "brightness": brightness_value
                                    }
                                )
                            else:
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
        

    async def async_turn_on_light(self, device_id: str, brightness: int = 255):
        device = self.devices.get(device_id)
        if not device:
            _LOGGER.warning(f"Kein Light-Gerät mit ID {device_id} gefunden")
            return
        objadr = device.objadr
        if objadr is None:
            _LOGGER.warning(f"Keine objadr für Light {device_id}")
            return
        brightness100 = round(brightness * 100 / 255)
        await self._packet_sender.send_raw_command(
            ipdst=objadr,
            ddata=bytes([D0_SET, brightness100, 0x00]),
            objsource=self._objadr,
            mi=self._mi,
        )
        _LOGGER.debug(f"Schalte Light EIN {device_id} mit Helligkeit {brightness100} (OBJ={objadr}) gesendet")

    async def async_turn_off_light(self, device_id: str):
        device = self.devices.get(device_id)
        if not device:
            _LOGGER.warning(f"Kein Light-Gerät mit ID {device_id} gefunden")
            return
        objadr = device.objadr
        if objadr is None:
            _LOGGER.warning(f"Keine objadr für Light {device_id}")
            return

        # Beispielbefehl: Ausschalten (je nach Gerät anpassen)
        await self._packet_sender.send_raw_command(
            ipdst=objadr,
            ddata=bytes([D0_SET, 0x00, 0x00]),  # Beispiel OFF-Befehl
            objsource=self._objadr,
            mi=self._mi,
        )
        _LOGGER.debug(f"Schalte Light AUS {device_id} (OBJ={objadr}) gesendet")



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

    def get_known_device(self, device_id: str) -> Optional[Net4HomeDevice]:
        device = self.devices.get(device_id)
        if not device:
            _LOGGER.warning(f"Unbekanntes Gerät: {device_id}")
        return device

    async def async_set_climate_mode(self, device_id: str, hvac_mode: str):
        objadr = self.devices[device_id].objadr
        command = 0x01 if hvac_mode == "heat" else 0x00
        await self._packet_sender.send_raw_command(
            ipdst=objadr,
            ddata=bytes([D0_SET, command, 0x00]),
            objsource=self._objadr,
            mi=self._mi,
        )
        _LOGGER.debug(f"Set climate mode to {hvac_mode} for {device_id} (OBJ={objadr})")


    async def async_set_temperature(self, device_id: str, temperature: float):
        objadr = self.devices[device_id].objadr
        temp_val = round(temperature)
        await self._packet_sender.send_raw_command(
            ipdst=objadr,
            ddata=bytes([D0_SET, temp_val, 0x00]),
            objsource=self._objadr,
            mi=self._mi,
        )
        _LOGGER.debug(f"Set target temperature {temp_val}°C for {device_id} (OBJ={objadr})")


