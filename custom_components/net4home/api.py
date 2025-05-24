"""Support for net4home integration."""
import asyncio
import struct
import logging
import binascii

from typing import Optional
from homeassistant.helpers.dispatcher import async_dispatcher_send
from .helpers import register_device_in_registry
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    N4H_IP_PORT,
    DEFAULT_MI,
    DEFAULT_OBJADR,
    N4HIP_PT_PAKET,
)
from .n4htools import (
    log_parsed_packet,
    interpret_n4h_sFkt,
    TN4Hpaket,
    n4h_parse,
    platine_typ_to_name_a,
)
from .helpers import register_device_in_registry

from .const import (
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
)

_LOGGER = logging.getLogger(__name__)

from typing import Optional

class Net4HomeDevice:
    def __init__(
        self,
        device_id: str,
        name: str,
        model: str,
        device_type: str,
        via_device: Optional[str] = None,  
    ):
        self.device_id = device_id
        self.name = name
        self.model = model
        self.device_type = device_type
        self.via_device = via_device


# Receive data from Bus connector
class N4HPacketReceiver:
    def __init__(self):
        self._buffer = bytearray()

    def feed_data(self, data: bytes):
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
            else:
                _LOGGER.debug(f"Ignored packet type: {ptype}")

            del self._buffer[:total_len + 8]
        return packets
        

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
        self.devices = {}
        
    async def async_connect(self):
        _LOGGER.info(f"Connect with net4home Bus connector at {self._host}:{self._port}")
        self._reader, self._writer = await asyncio.open_connection(self._host, self._port)
        _LOGGER.debug("TCP-Connection established")

        try:
            packet_bytes = binascii.unhexlify(self._password)
        except binascii.Error as e:
            _LOGGER.error(f"Ungültiger Hex-String für Passwort: {e}")
            raise

        self._writer.write(packet_bytes)
        await self._writer.drain()
        _LOGGER.debug("Credentials to Bus connector sent")

    async def async_disconnect(self):
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            _LOGGER.debug("Connection to net4home Bus connector closed")

    async def async_listen(self):
        _LOGGER.info("Start listening for bus messages")
        try:
            while True:
                data = await self._reader.read(4096)
                if not data:
                    _LOGGER.info("Connection closed to net4home Bus connector")
                    break

                packets = self._packet_receiver.feed_data(data)
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
                        
                        # We have a device answered to a enum request
                        if b0 == D0_ACK_TYP: 
                            device_id = f"MI{paket.ipsrc:05d}"
                            model = platine_typ_to_name_a(paket.ddata[1])
                            sw_version = ""
                            name = device_id

                            # Register the device and start with a nonblocking connection 
                            asyncio.create_task(
                                register_device_in_registry(
                                    self._hass,
                                    self._entry_id,
                                    device_id=device_id,
                                    name=name,
                                    model=model,
                                    sw_version=sw_version,
                                )
                            )
                        elif b0 == D0_RD_ACTOR_DATA:   
                            device_id = ""
                        # We have a device answered to a configuration request
                        elif b0 == D0_RD_ACTOR_DATA_ACK:  
                            # Let´s register the correct type we see in D2
                            b2 = paket.ddata[2]
                            
                            # Hey, it´s an AR (switch entity)
                            if b2 == OUT_HW_NR_IS_ONOFF:
                                device_id = f"OBJ{(paket.ddata[8]*256+paket.ddata[9]):04d}"
                                model = "Schalter"
                                name = device_id
                                via_device = "MI0113"
                                
                                new_ar = Net4HomeDeviceAR(
                                    device_id=device_id,
                                    name=name,
                                    model=model,
                                    device_type="switch",  
                                    via_device=via_device,
                                )

                                new_ar._state = is_on
                                self.devices[device_id] = new_ar
                                
                                asyncio.create_task(
                                    register_device_in_registry(
                                        self._hass,
                                        self._entry_id,
                                        device_id=device_id,
                                        name=name,
                                        model=model,
                                        sw_version="",
                                    )
                                )

                                from homeassistant.helpers.dispatcher import async_dispatcher_send
                                async_dispatcher_send(self._hass, f"net4home_new_device_{self._entry_id}", new_ar)

                            # ddata[2]  -> Type ONOFF, TIMER....
                            # ddata[3]  -> ddata[3]*256+ddata[4]; (Zeit1)
                            # ddata[4]  -> siehe 3
                            # ddata[5]  -> PowerUp
                            # ddata[6]  -> scheinbar ungenutzt bei AR                          
                            # ddata[7]  -> Statusänderungen
                            # ddata[8]*256+ ddata[9] -> Adresse
                            # ddata[10]:= hi(t2);(Zeit2)
                            # ddata[11]:= lo(t2);
                            # ddata[12] -> OUT_OPTION_2_MOTOR_ANLAUF/OUT_OPTION_2_INV_OUT 

                            # 1F 00 04 00 01 00 FF 01 05 DD 00 01 00 15

        except Exception as e:
            _LOGGER.error(f"Fehler im Listener: {e}")


