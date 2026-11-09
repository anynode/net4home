"""Incoming bus packets."""
import asyncio
import logging
import time

from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import slugify

from .const import (
    D0_ACK_TYP,
    D0_ACTOR_ACK,
    D0_DEC,
    D0_ENABLE_CONFIGURATION,
    D0_ENUM_ALL,
    D0_INC,
    D0_RD_ACTOR_DATA_ACK,
    D0_RD_GRP_DATA_ACK,
    D0_RD_MODULSPEC_DATA_ACK,
    D0_RD_SENSOR_DATA_ACK,
    D0_REQ,
    D0_SENSOR_ACK,
    D0_SET,
    D0_SET_N,
    D0_STATUS_INFO,
    D0_TOGGLE,
    D0_VALUE_ACK,
    D0_WR_MODULSPEC_DATA,
    D10_CONFIG_ENABLE_BIT,
    D10_FCONFIG_ENABLE_BIT,
    IN_HW_NR_IS_CLOCK,
    IN_HW_NR_IS_HUMIDITY,
    IN_HW_NR_IS_LICHT_ANALOG,
    IN_HW_NR_IS_RF_TAG_READER,
    IN_HW_NR_IS_TEMP,
    OUT_HW_NR_IS_DIMMER,
    OUT_HW_NR_IS_JAL,
    OUT_HW_NR_IS_ONOFF,
    OUT_HW_NR_IS_SLOW_PWM,
    OUT_HW_NR_IS_TIMER,
    PLATINE_HW_IS_BELL2,
    SEND_AS_IP,
    VAL_IS_MIN_TAG_WORD_SA,
    VAL_IS_MIN_TAG_WORD_SU,
)
from .si_layout import (
    SI_MODEL_CHANNELS,
    ensure_si_runtime,
    si_entry_from_line,
    si_info_from_ddata,
    si_power_from_ack,
)
from .alarm_layout import (
    alarm_base_from_modulspec,
    alarm_flags_from_sensor_ack,
    alarm_sabotage,
    alarm_state_from_status,
    alarm_tables_from_info,
    ensure_alarm_runtime,
    trigger_from_entry,
)
from .tlh_layout import (
    climate_regulators,
    tlh_measured_sensor,
    tlh_uses_fixed_sensor_map,
)
from .cover_motion import cover_position_from_status
from .ext_ld_layout import (
    ext_ld_base_from_modulspec,
    ext_ld_status,
)
from .n4htools import (
    get_function_and_address_count,
    n4h_parse,
    platine_typ_to_name_a,
)
from .binary_inputs import is_binary_sensor_channel
from .dimmer_layout import (
    is_dimmer_module,
    timer_channel_device_type,
)
from .lcd_layout import lcd_base_from_modulspec
from .hs_time import (
    parse_hs_time_clock,
    sun_object_offsets,
    sun_time_from_ack,
)
from .rf_keys import (
    parse_rf_key_record,
    parse_rf_key_table_line,
    parse_rf_master_index,
)
from .protocol import pwm_status_to_ha
from .helpers import register_device_in_registry

_LOGGER = logging.getLogger(__name__)

class PacketDispatch:
    """Incoming bus packets."""

    async def async_listen(self):
        """Listen for incoming packets from the bus connector."""
        _LOGGER.debug("[IP] Start listening for bus packets")
        
        packet_count = 0
        no_data_count = 0
        while True:
                try:
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
                        # Process the received data
                        packets = self._packet_receiver.receive_raw_command(data)
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
                                        async_dispatcher_send(self._hass, f"net4home_update_{dispatch_id}", {"targettemp": sollwert_temp})
                                        async_dispatcher_send(self._hass, f"net4home_update_{dispatch_id}_targettemp", sollwert_temp)

                                if b0 == D0_SET and len(paket.ddata) >= 2:
                                    self._dispatch_cover_motion(paket.ipdest, paket.ddata[1])

                                if b0 == D0_WR_MODULSPEC_DATA and len(paket.ddata) >= 6 and paket.ddata[1] == 0xF0:
                                    device_id_mi = f"MI{paket.ipdest:04X}"
                                    device = self.get_known_device(device_id_mi)
                                    if device and device.model in ("UP-TLH", "UP-T"):
                                        presetday = (paket.ddata[2] * 256 + paket.ddata[3]) / 10.0
                                        presetnight = (paket.ddata[4] * 256 + paket.ddata[5]) / 10.0
                                        device.presetday = presetday
                                        device.presetnight = presetnight
                                        dispatch_id = device.device_id.upper()
                                        async_dispatcher_send(self._hass, f"net4home_update_{dispatch_id}", {"presetday": presetday, "presetnight": presetnight})
                                        async_dispatcher_send(self._hass, f"net4home_update_{dispatch_id}_presetday", presetday)
                                        async_dispatcher_send(self._hass, f"net4home_update_{dispatch_id}_presetnight", presetnight)
                                
                                if b0 == D0_SET_N and len(paket.ddata) >= 2:
                                    device = self._find_up_tlh_by_objadr(paket.ipdest)
                                    if device:
                                        heat_active, cool_active, hvac_mode = climate_regulators(paket.ddata[1])
                                        device.heat_active = heat_active
                                        device.cool_active = cool_active
                                        dispatch_id = device.device_id.upper()
                                        update_data = {"hvac_mode": hvac_mode, "heat_active": heat_active, "cool_active": cool_active}
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
                                    existing = self.devices.get(device_id)
                                    name = existing.name if existing and existing.name else device_id
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
                                    
                                    # UP-TLH is a module with entities
                                    if model == "UP-TLH":
                                        device_type="climate"
                                        # IMPORTANT: objadr will be set later from the 0xF1 packet (D0_RD_MODULSPEC_DATA_ACK)
                                        # Initially set to None so sensors are not created with wrong objadr
                                        objadr=None
                                    
                                    # UP-RF is an RF-Key reader module
                                    elif model in ("UP-RF", "UP-RF-S4AR1"):
                                        device_type="rf_reader"
                                        objadr=paket.objsrc
                                    
                                    # HS-Safety is an alarm control panel module.
                                    # The command address is EE_LC_ADR from modulspec line 0,
                                    # not the object that answered D0_ACK_TYP.
                                    elif model == "HS-Safety":
                                        device_type="alarm_control_panel"
                                        objadr=paket.objsrc if paket.objsrc else None
                                    
                                    # HS-Time is a time control module with sunrise/sunset sensors
                                    elif model == "HS-Time":
                                        device_type="sensor"  # Treated as sensor module
                                        # objadr will be set later from the 0xFF packet (D0_RD_MODULSPEC_DATA_ACK)
                                        objadr=None

                                    # EXT-LD (Motorriegel): commands go to the base object EE_ADR_LOCAL_ADR,
                                    # which is read from modulspec line 0.
                                    elif model == "EXT-LD":
                                        device_type="lock"
                                        objadr=None
                                        

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
                                        
                                        # Module type information is already stored during registration
                                        # Just verify it was set correctly and log
                                        device = self.devices.get(device_id)
                                        if device:
                                            device.ack_typ_at = time.monotonic()
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
                                            
                                        
                                        # Request sensor data for UP-RF devices to discover sensor object addresses
                                        # (These requests are fast and can be done immediately)
                                        if device_type == "rf_reader":
                                            # Request sensor data for channels 0 and 1 (command 1 and command 2)
                                            await self.async_request_sensor_data(device_id, channel=0)
                                            await self.async_request_sensor_data(device_id, channel=1)
                                        
                                        # Add device to detail queue (for further detail queries)
                                        await self.async_queue_device_for_details(device_id)
                                        
                                        # Persist module metadata to options so module data is never missing after restart
                                        await self._async_save_module_metadata(
                                            device_id, sw_version, module_type, ns, na, nm, ng
                                        )
                                            
                                    except Exception as e:
                                        _LOGGER.error(f"Error during registration of device (module) {device_id}: {e}")

                                elif b0 == D0_ACTOR_ACK:
                                    # For UP-TLH/UP-T: D0_ACTOR_ACK comes from OBJ addresses (objadr, objadr+1, objadr+2)
                                    # But sensors are created on the MI device, so we need to find the MI device
                                    device_id = f"MI{paket.ipsrc:04X}"
                                    device = self.devices.get(device_id)

                                    if not device:
                                        # Fallback: Versuche OBJ-Device
                                        device_id = f"OBJ{paket.objsrc:05d}"
                                        device = self.devices.get(device_id)
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
                                            continue

                                    # For multi-channel actor modules (e.g. HS-AD1-1x10V): D0_ACTOR_ACK refers to the channel (OBJ), not the module (MI).
                                    # Commands go to the actor (OBJ); UP-TLH/UP-T (climate) keep using MI and are unchanged.
                                    if device.device_type == 'module':
                                        obj_device_id = f"OBJ{paket.objsrc:05d}"
                                        obj_device = self.devices.get(obj_device_id)
                                        if obj_device:
                                            device_id = obj_device_id
                                            device = obj_device
                                        else:
                                            # Channel was never stored (e.g. OBJ15801 on MI0158). Read the module again.
                                            await self.async_request_missing_actor_channels(device.device_id)
                                            continue

                                    if device.device_type == 'rf_reader':
                                        continue  # UP-RF: no actor entities, RF-Key updates via D0_VALUE_ACK

                                    if device.device_type == 'lock':
                                        status = ext_ld_status(paket.ddata)
                                        if status is not None:
                                            device.ext_ld_status = status
                                            async_dispatcher_send(
                                                self._hass,
                                                f"net4home_update_{device.device_id.upper()}_lock",
                                                status,
                                            )
                                            _LOGGER.info(
                                                "EXT-LD %s status reply obj=%s flags=0x%02X raw=%s",
                                                device.device_id,
                                                paket.objsrc,
                                                status["flags"],
                                                paket.ddata.hex(),
                                            )
                                        continue

                                    if device.model == "HS-Time":
                                        if len(paket.ddata) < 3:
                                            _LOGGER.warning(
                                                "D0_ACTOR_ACK too short for HS-Time %s: %s bytes",
                                                device.device_id,
                                                len(paket.ddata),
                                            )
                                            continue
                                        mask = paket.ddata[2]
                                        device.hs_profile_mask = mask
                                        async_dispatcher_send(
                                            self._hass,
                                            f"net4home_update_{device.device_id.upper()}_hs_profile",
                                            mask,
                                        )
                                        _LOGGER.debug(
                                            "HS-Time %s profile mask 0x%02X",
                                            device.device_id,
                                            mask,
                                        )
                                        continue

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
                                                
                                                # The regulator flags belong to the current setpoint.
                                                # Day and night replies carry a temperature only.
                                                if sensor_key == "targettemp":
                                                    device.targettemp = temp
                                                    heat_active, cool_active, hvac_mode = climate_regulators(paket.ddata[3])
                                                    device.heat_active = heat_active
                                                    device.cool_active = cool_active
                                                    _LOGGER.info(
                                                        "UP-TLH %s setpoint %s °C, heat=%s, cool=%s",
                                                        device.device_id,
                                                        temp,
                                                        heat_active,
                                                        cool_active,
                                                    )
                                                elif sensor_key == "presetday":
                                                    device.presetday = temp
                                                elif sensor_key == "presetnight":
                                                    device.presetnight = temp
                                                # Send updates to the MI device (where sensors were created); use uppercase for dispatcher key
                                                dispatch_id = device_id.upper()
                                                update_data = {sensor_key: temp}
                                                if sensor_key == "targettemp":
                                                    update_data["hvac_mode"] = hvac_mode
                                                    update_data["heat_active"] = heat_active
                                                    update_data["cool_active"] = cool_active
                                                async_dispatcher_send(self._hass, f"net4home_update_{dispatch_id}", update_data)
                                                async_dispatcher_send(self._hass, f"net4home_update_{dispatch_id}_{sensor_key}", temp)
                                            else:
                                                _LOGGER.warning(f"D0_ACTOR_ACK packet too short for climate: {len(paket.ddata)} bytes, expected at least 4")
                                    else:
                                        # Check if packet has enough data (need at least 3 bytes)
                                        if len(paket.ddata) < 3:
                                            _LOGGER.warning(f"D0_ACTOR_ACK packet too short: {len(paket.ddata)} bytes, expected at least 3")
                                            continue
                                        
                                        if device.device_type == 'switch':
                                            is_on = paket.ddata[2] == 1
                                            _LOGGER.debug(f"D0_ACTOR_ACK for {device_id}: {'ON' if is_on else 'OFF'}")
                                            async_dispatcher_send(self._hass, f"net4home_update_{device_id}", is_on)
                                            
                                        elif device.device_type == 'timer':
                                            is_on = paket.ddata[2] == 1
                                            _LOGGER.debug(f"D0_ACTOR_ACK for {device_id}: {'ON' if is_on else 'OFF'}")
                                            async_dispatcher_send(self._hass, f"net4home_update_{device_id}", is_on)
                                            
                                        elif device.device_type == 'cover':
                                            position = cover_position_from_status(paket.ddata[2])
                                            _LOGGER.debug(
                                                "D0_ACTOR_ACK for %s: status 0x%02X, position %s",
                                                device_id,
                                                paket.ddata[2],
                                                position,
                                            )
                                            async_dispatcher_send(self._hass, f"net4home_update_{device_id}", {"position": position})

                                        elif device.device_type == 'light':
                                            if device.model == "PWM":
                                                is_on, brightness_value = pwm_status_to_ha(
                                                    paket.ddata[1], paket.ddata[2]
                                                )
                                                percent = round(brightness_value * 100 / 255)
                                            else:
                                                is_on = paket.ddata[2] >> 7
                                                brightness_value = round((paket.ddata[2] & 0x7F) * 255 / 100)
                                                percent = paket.ddata[2] & 0x7F
                                            _LOGGER.debug(
                                                "STATUS_INFO_ACK for %s: %s %s%%",
                                                device_id,
                                                "ON" if is_on else "OFF",
                                                percent,
                                            )
                                            async_dispatcher_send(self._hass,f"net4home_update_{device_id}",{"is_on": is_on, "brightness": brightness_value},)

                                        elif device.device_type == 'binary_sensor':
                                            is_closed = paket.ddata[2] != 1 
                                            _LOGGER.debug(f"STATUS_INFO_ACK for {device_id}: {'CLOSED' if is_closed else 'OPEN'}")
                                            async_dispatcher_send(self._hass, f"net4home_update_{device_id}", is_closed)
                                            
                                        else:
                                            # Only log warning for unhandled device types
                                            _LOGGER.warning(f"Unhandled device type in D0_ACTOR_ACK: {device.device_type} ({device.model}) for {device_id}")

                                elif b0 == D0_RD_GRP_DATA_ACK:
                                    index = paket.ddata[1] if len(paket.ddata) > 1 else None
                                    module = self.devices.get(f"MI{paket.ipsrc:04X}")
                                    lines = getattr(module, "group_lines", None) if module else None
                                    if isinstance(lines, dict) and index is not None:
                                        lines[index] = bytes(paket.ddata)
                                    if index is not None:
                                        self._release_line_read(paket.ipsrc, b0, index)

                                elif b0 == D0_RD_ACTOR_DATA_ACK:
                                    _line_index = paket.ddata[1] if len(paket.ddata) > 1 else None
                                    try:
                                        if len(paket.ddata) < 10:
                                            _LOGGER.warning(
                                                "D0_RD_ACTOR_DATA_ACK too short from MI%04X: %s bytes",
                                                paket.ipsrc,
                                                len(paket.ddata),
                                            )
                                            continue

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
                                        if device_obj and is_dimmer_module(device_obj.model):
                                            is_dimmer = True
                                        
                                        if device_obj and device_obj.model in ('HS-AJ3', 'UP-AJ1', 'HS-AJ4-500', 'HS-AJ3-6'):
                                            is_jal = True
                                    
                                        # Also check if the via_device already has dimmer devices (then it is a dimmer module)
                                        if via_device in self.devices:
                                            via_device_obj = self.devices[via_device]
                                            # Check if there are already dimmer channels
                                            for existing_device in self.devices.values():
                                                if existing_device.via_device == via_device and existing_device.device_type == "light":
                                                    is_dimmer = True
                                                    break
                                    
                                        # Timer entries have priority and are detected regardless of module type
                                        # IMPORTANT: Timer check must occur BEFORE dimmer check
                                        # Timer is also detected on dimmer modules if b2 == OUT_HW_NR_IS_TIMER
                                        if b2 == OUT_HW_NR_IS_TIMER:
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
                                            # A timer on a dimmer keeps a 0–100% output. Toggle recalls
                                            # the last level; SET carries a percent, so it is a light.
                                            timer_type = timer_channel_device_type(
                                                device_obj.model if device_obj else None
                                            )

                                            try:
                                                await register_device_in_registry(
                                                    hass=self._hass,
                                                    entry=self._entry,
                                                    device_id=device_id,
                                                    name = f"CH{b1}_{device_id[3:]}",
                                                    model="Timer",
                                                    sw_version="",
                                                    hw_version="",
                                                    device_type=timer_type,
                                                    via_device=via_device,
                                                    api=self,
                                                    objadr=objadr,
                                                    send_state_changes = bool(b7),
                                                    timer_time1=t1,
                                                )
                                                if device_id in self.devices:
                                                    self.devices[device_id].timer_time1 = t1
                                                    await self._async_save_device_timer_time1(device_id, t1)
                                                settings = {
                                                    "powerup_status": b5,
                                                    "send_state_changes": bool(b7),
                                                }
                                                if timer_type == "light":
                                                    settings["min_hell"] = b6
                                                await self._async_save_actor_settings(device_id, **settings)
                                            except Exception as e:
                                                _LOGGER.error(f"Error during registration of TIMER device (channel) {device_id}: {e}")
                                    
                                        # Wenn OUT_HW_NR_IS_ONOFF und is_dimmer, dann als Dimmer behandeln
                                        elif b2 == OUT_HW_NR_IS_ONOFF and is_dimmer:
                                        
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
                                                await self._async_save_actor_settings(
                                                    device_id,
                                                    powerup_status=b5,
                                                    min_hell=b6,
                                                    send_state_changes=bool(b7),
                                                )
                                            except Exception as e:
                                                _LOGGER.error(f"Error during registration of DIMMER device (channel) {device_id}: {e}", exc_info=True)

                                        # We have a classic switch with ON/OFF feature
                                        # IMPORTANT: Only for real ON/OFF actors, NOT for dimmers (they have OUT_HW_NR_IS_DIMMER)
                                        elif b2 == OUT_HW_NR_IS_ONOFF and not is_dimmer:

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
                                                await self._async_save_actor_settings(
                                                    device_id,
                                                    powerup_status=b5,
                                                    send_state_changes=bool(b7),
                                                )
                                            except Exception as e:
                                                _LOGGER.error(f"Error during registration of ONOFF device (channel) {device_id}: {e}", exc_info=True)

                                        # We have a dimmer
                                        elif b2 == OUT_HW_NR_IS_DIMMER:

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
                                                await self._async_save_actor_settings(
                                                    device_id,
                                                    powerup_status=b5,
                                                    min_hell=b6,
                                                    send_state_changes=bool(b7),
                                                )
                                            except Exception as e:
                                                _LOGGER.error(f"Error during registration of DIMMER device (channel) {device_id}: {e}", exc_info=True)

                                        elif b2 == OUT_HW_NR_IS_SLOW_PWM:
                                            b5 = paket.ddata[5]
                                            b6 = paket.ddata[6]
                                            b7 = paket.ddata[7]
                                            try:
                                                await register_device_in_registry(
                                                    hass=self._hass,
                                                    entry=self._entry,
                                                    device_id=device_id,
                                                    name=f"CH{b1}_{device_id[3:]}",
                                                    model="PWM",
                                                    sw_version="",
                                                    hw_version="",
                                                    device_type="light",
                                                    via_device=via_device,
                                                    api=self,
                                                    objadr=objadr,
                                                    send_state_changes=bool(b7),
                                                )
                                                await self._async_save_actor_settings(
                                                    device_id,
                                                    powerup_status=b5,
                                                    min_hell=b6,
                                                    send_state_changes=bool(b7),
                                                )
                                            except Exception as e:
                                                _LOGGER.error(
                                                    "Error during registration of PWM device (channel) %s: %s",
                                                    device_id,
                                                    e,
                                                    exc_info=True,
                                                )

                                        # We have a cover 
                                        elif b2 == OUT_HW_NR_IS_JAL or is_jal:


                                            # Module details
                                            b3  = paket.ddata[3]     # time1 hi
                                            b4  = paket.ddata[4]     # time1 lo
                                            b7  = paket.ddata[7]     # Status update
                                            t1  = b3*256+b4 # time1 (Run time for covers)
                                        

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
                                                    timer_time1=t1,
                                                )
                                                # Store run time (Timer1) in device (also for already existing devices)
                                                if device_id in self.devices:
                                                    self.devices[device_id].timer_time1 = t1
                                                    self.devices[device_id].send_state_changes = bool(b7)
                                                    await self._async_save_device_timer_time1(device_id, t1)
                                                    async_dispatcher_send(self._hass, f"net4home_diagnostic_update_{device_id}")
                                                else:
                                                    _LOGGER.warning(
                                                        "[JAL] device_id=%s not in api.devices (keys: %s), cannot store run time",
                                                        device_id, list(self.devices.keys())[:20],
                                                    )
                                            except Exception as e:
                                                _LOGGER.error(f"Error during registration of COVER device (channel) {device_id}: {e}")

                                        elif b2 not in (0,):
                                            _LOGGER.warning(
                                                "Unhandled actor type %s from %s channel %s, object %s",
                                                b2,
                                                via_device,
                                                b1,
                                                objadr,
                                            )
                                        child = self.devices.get(device_id)
                                        if (
                                            child is not None
                                            and child.via_device == via_device
                                            and _line_index is not None
                                        ):
                                            child.actor_channel = _line_index

                                    finally:
                                        if _line_index is not None:
                                            self._release_line_read(paket.ipsrc, b0, _line_index)
                                elif b0 == D0_RD_SENSOR_DATA_ACK:
                                    _line_index = paket.ddata[1] if len(paket.ddata) > 1 else None
                                    try:

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
                                            if len(paket.ddata) == 3:
                                                _LOGGER.info(
                                                    "Sensor table MI%04X channel %s is empty",
                                                    paket.ipsrc,
                                                    paket.ddata[1],
                                                )
                                            else:
                                                _LOGGER.warning(
                                                    "D0_RD_SENSOR_DATA_ACK from MI%04X is %s bytes, need %s, raw %s",
                                                    paket.ipsrc,
                                                    len(paket.ddata),
                                                    min_required,
                                                    paket.ddata.hex(),
                                                )
                                            continue
                                    
                                        pin_typ = paket.ddata[EE_OFFSET_PIN_IS]

                                        channel = paket.ddata[1] + 1
                                        function_count, _ = get_function_and_address_count(pin_typ)

                                        objadr = paket.ddata[EE_OFFSET_ADR]*256+paket.ddata[EE_OFFSET_ADR+1]
                                        _LOGGER.info(
                                            "Sensor table MI%04X channel %s len=%s pin=%s object=%s raw %s",
                                            paket.ipsrc,
                                            paket.ddata[1],
                                            len(paket.ddata),
                                            pin_typ,
                                            objadr,
                                            paket.ddata[:32].hex(),
                                        )
                                    
                                        # EE_NCNO_INV is optional - only available in longer packets (19+ bytes)
                                        # For shorter packets (like UP-RF with 15 bytes), default to False
                                        if len(paket.ddata) >= EE_NCNO_INV + 1:
                                            detected_inverted = bool(paket.ddata[EE_NCNO_INV])
                                        else:
                                            detected_inverted = False
                                    

                                        if objadr == 0:
                                            _LOGGER.warning(
                                                f"D0_RD_SENSOR_DATA_ACK channel {channel} from "
                                                f"MI{paket.ipsrc:04X} has no object address"
                                            )
                                            continue

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


                                        if device_obj and is_binary_sensor_channel(device_obj.model, pin_typ):
                                            try:
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
                                            except Exception as e:
                                                _LOGGER.error(f"Error during SENSOR registration for {device_id}: {e}", exc_info=True)
                                        elif device_obj and device_obj.model not in ("UP-RF", "UP-RF-S4AR1"):
                                            _LOGGER.info(
                                                "Sensor channel %s of %s (%s) pin %s object %s was not mapped",
                                                channel,
                                                via_device,
                                                device_obj.model,
                                                pin_typ,
                                                objadr,
                                            )
                                    
                                        # For UP-RF devices, we don't register OBJ addresses as separate devices
                                        # The RF-Key sensor will be created directly on the MI device
                                        if device_obj and device_obj.model in ('UP-RF', 'UP-RF-S4AR1'):
                                            # Store OBJ address mapping for RF-Key message routing
                                            # We'll map OBJ addresses to the parent MI device in D0_VALUE_ACK handler
                                            pass

                                    finally:
                                        if _line_index is not None:
                                            self._release_line_read(paket.ipsrc, b0, _line_index)
                                elif b0 == D0_SENSOR_ACK:
                                    # Power of a UP-SI / HS-SI6 channel object (W, pin 18).
                                    si_owner = self._si_channel_owner(paket.objsrc)
                                    if si_owner is not None:
                                        owner, channel = si_owner
                                        ensure_si_runtime(owner)
                                        power = si_power_from_ack(paket.ddata)
                                        if power is not None:
                                            owner.si_power[channel] = power
                                            async_dispatcher_send(
                                                self._hass,
                                                f"net4home_si_{owner.device_id.upper()}",
                                                "power",
                                            )
                                        continue

                                    # A contact of an HS-Safety trigger list. The normal
                                    # binary sensor path below still runs for it.
                                    contact_owner = self._alarm_contact_owner(paket.objsrc)
                                    if contact_owner is not None and len(paket.ddata) >= 3:
                                        ensure_alarm_runtime(contact_owner)
                                        contact_owner.alarm_contacts[paket.objsrc] = paket.ddata[2] == 1
                                        async_dispatcher_send(
                                            self._hass,
                                            f"net4home_alarm_{contact_owner.device_id.upper()}",
                                            "contacts",
                                        )
                                    alarm = self._alarm_from_sensor_ack(paket)
                                    status = (
                                        alarm_flags_from_sensor_ack(paket.ddata)
                                        if alarm is not None
                                        else None
                                    )
                                    if alarm is not None and status is not None:
                                        flags, syncing = status
                                        state = alarm_state_from_status(flags, syncing)
                                        sabotage = alarm_sabotage(flags)
                                        previous = getattr(alarm, "alarm_state", None)
                                        previous_sabotage = getattr(alarm, "alarm_sabotage", None)
                                        alarm.alarm_state = state
                                        alarm.alarm_sabotage = sabotage
                                        if previous != state or previous_sabotage != sabotage:
                                            _LOGGER.info(
                                                "HS-Safety %s status %s sabotage %s (flags=0x%02X syncing=%s)",
                                                alarm.device_id,
                                                state,
                                                sabotage,
                                                flags,
                                                syncing,
                                            )
                                        if previous is not None and previous != state:
                                            self._schedule_alarm_log(alarm)
                                        async_dispatcher_send(
                                            self._hass,
                                            f"net4home_update_{alarm.device_id.upper()}",
                                            {"alarm_state": state, "sabotage": sabotage},
                                        )
                                        continue
                                    if len(paket.ddata) < 3:
                                        _LOGGER.warning(
                                            "D0_SENSOR_ACK packet too short: %s bytes from MI%04X object %s data %s",
                                            len(paket.ddata),
                                            paket.ipsrc,
                                            paket.objsrc,
                                            paket.ddata.hex(),
                                        )
                                        continue
                                    device_id = f"OBJ{paket.objsrc:05d}"
                                    device = self.devices.get(device_id)
                                    if device is None:
                                        device = next(
                                            (
                                                candidate
                                                for candidate in self.devices.values()
                                                if candidate.device_type == "binary_sensor"
                                                and candidate.objadr == paket.objsrc
                                            ),
                                            None,
                                        )

                                    if not device:
                                        continue

                                    is_closed = paket.ddata[2] == 1
                                    async_dispatcher_send(
                                        self._hass,
                                        f"net4home_update_{device.device_id.upper()}",
                                        is_closed,
                                    )

                                elif b0 == D0_RD_MODULSPEC_DATA_ACK:
                                    b1  = paket.ddata[1] 
                                    obj_heat = None
                                    obj_cool = None
                                    presetday = None
                                    presetnight = None
                                    
                                    # Initialize b2 and b3 in case they are used later
                                    b2 = None
                                    b3 = None

                                    if self._rf_key_read_active():
                                        _LOGGER.info(
                                            "modulspec ACK while reading keys from MI%04X len=%s raw %s",
                                            paket.ipsrc,
                                            len(paket.ddata),
                                            paket.ddata.hex(),
                                        )

                                    device_id = f"MI{paket.ipsrc:04X}"
                                    device = self.devices.get(device_id)
                                    if not device:
                                        _LOGGER.warning(f"D0_RD_MODULSPEC_DATA_ACK: Device {device_id} not found")
                                        continue
                                    
                                    model = device.model or ""
                                    objadr = device.objadr if device else None

                                    if device.device_type == "rf_reader" and getattr(
                                        device, "rf_key_list_until", 0
                                    ) > time.monotonic():
                                        master_index = parse_rf_master_index(paket.ddata)
                                        table_slots = parse_rf_key_table_line(paket.ddata)
                                        if master_index is not None:
                                            device.rf_master_index = master_index
                                            self._apply_rf_master(device)
                                            _LOGGER.info(
                                                "UP-RF %s master slot %s raw %s",
                                                device_id,
                                                master_index + 1,
                                                paket.ddata.hex(),
                                            )
                                            continue
                                        if table_slots:
                                            slots = self._ensure_rf_keys(device)
                                            for index, code in table_slots:
                                                slots[index]["code"] = code
                                            self._apply_rf_master(device)
                                            _LOGGER.info(
                                                "UP-RF %s key table line %s raw %s",
                                                device_id,
                                                paket.ddata[1],
                                                paket.ddata.hex(),
                                            )
                                            continue
                                        record = parse_rf_key_record(paket.ddata)
                                        if record is None:
                                            _LOGGER.info(
                                                "UP-RF %s key list reply did not match a slot, len=%s raw %s",
                                                device_id,
                                                len(paket.ddata),
                                                paket.ddata.hex(),
                                            )
                                        if record is not None:
                                            index, code, master = record
                                            slots = self._ensure_rf_keys(device)
                                            slots[index] = {
                                                "code": code,
                                                "master": master and bool(code),
                                            }
                                            device.rf_key_list_until = time.monotonic() + 1.5
                                            self._publish_rf_slot(device, index)
                                            _LOGGER.info(
                                                "UP-RF %s Schlüssel %s %s%s raw %s",
                                                device_id,
                                                index + 1,
                                                code or "leer",
                                                " Master" if slots[index]["master"] else "",
                                                paket.ddata.hex(),
                                            )
                                            continue
                                    
                                    # Module-specific evaluation based on device.model
                                    # See docs/modulspec.md for details

                                    if model in SI_MODEL_CHANNELS:
                                        ensure_si_runtime(device)
                                        self._release_line_read(paket.ipsrc, b0, b1)
                                        if b1 == 0xFF:
                                            info = si_info_from_ddata(model, paket.ddata)
                                            if info is None:
                                                _LOGGER.warning(
                                                    "%s %s module info reply not understood: %s",
                                                    model,
                                                    device_id,
                                                    paket.ddata.hex(),
                                                )
                                            else:
                                                device.si_info = info
                                                _LOGGER.info(
                                                    "%s %s base %s channels %s lines %s",
                                                    model,
                                                    device_id,
                                                    info.base,
                                                    info.channels,
                                                    info.lines,
                                                )
                                                async_dispatcher_send(
                                                    self._hass,
                                                    f"net4home_si_{device_id.upper()}",
                                                    "info",
                                                )
                                                await self.async_request_si_power(device_id)
                                        else:
                                            device.si_entries[b1] = si_entry_from_line(paket.ddata)
                                            async_dispatcher_send(
                                                self._hass,
                                                f"net4home_si_{device_id.upper()}",
                                                "entries",
                                            )
                                        continue

                                    if model == "HS-Safety" and b1 == 0xFF:
                                        ensure_alarm_runtime(device)
                                        self._release_line_read(paket.ipsrc, b0, b1)
                                        counts = alarm_tables_from_info(paket.ddata)
                                        if counts is None:
                                            _LOGGER.warning(
                                                "HS-Safety %s module info reply too short: %s",
                                                device_id,
                                                paket.ddata.hex(),
                                            )
                                        else:
                                            device.alarm_tab_counts = counts
                                            _LOGGER.info(
                                                "HS-Safety %s tables: Tab0 %s, triggers %s, log %s events",
                                                device_id,
                                                counts.tab0,
                                                counts.tab1,
                                                counts.events,
                                            )
                                        continue

                                    counts = getattr(device, "alarm_tab_counts", None)
                                    if (
                                        model == "HS-Safety"
                                        and counts
                                        and counts.log_lines
                                        and counts.log_start <= b1 < counts.log_start + counts.log_lines
                                    ):
                                        ensure_alarm_runtime(device)
                                        device.alarm_log_lines[b1] = bytes(paket.ddata[2:18])
                                        self._release_line_read(paket.ipsrc, b0, b1)
                                        if b1 != 0:
                                            continue

                                    if (
                                        model == "HS-Safety"
                                        and b1 != 0
                                        and counts
                                        and counts.tab0 <= b1 < counts.tab0 + counts.tab1
                                    ):
                                        ensure_alarm_runtime(device)
                                        self._release_line_read(paket.ipsrc, b0, b1)
                                        slot = b1 - device.alarm_tab_counts[0]
                                        trigger = trigger_from_entry(bytes(paket.ddata[2:18]))
                                        if trigger is None:
                                            device.alarm_triggers.pop(slot, None)
                                        else:
                                            trigger["index"] = slot
                                            device.alarm_triggers[slot] = trigger
                                        async_dispatcher_send(
                                            self._hass,
                                            f"net4home_alarm_{device_id.upper()}",
                                            "triggers",
                                        )
                                        continue

                                    if model == "HS-Safety" and b1 == 0:
                                        base = alarm_base_from_modulspec(paket.ddata)
                                        if base is None:
                                            _LOGGER.warning(
                                                "HS-Safety %s modulspec line 0 has no base address, raw %s",
                                                device_id,
                                                paket.ddata.hex(),
                                            )
                                        else:
                                            device.objadr = base
                                            await self._async_save_objadr(device_id, base)
                                            _LOGGER.info("HS-Safety %s base address %s", device_id, base)
                                        continue

                                    if model == "EXT-LD" and b1 == 0:
                                        base = ext_ld_base_from_modulspec(paket.ddata)
                                        if base is None:
                                            _LOGGER.warning(
                                                "EXT-LD %s modulspec line 0 has no base address, raw %s",
                                                device_id,
                                                paket.ddata.hex(),
                                            )
                                        else:
                                            device.objadr = base
                                            await self._async_save_objadr(device_id, base)
                                            _LOGGER.info("EXT-LD %s base address %s", device_id, base)
                                        continue
                                    
                                    # 1. UP-TLH / UP-T: Spezielle Indizes und Sensoren
                                    if model in ('UP-TLH', 'UP-T'):
                                        # Special indices (0xF0, 0xF1) only for UP-TLH/UP-T
                                        if b1 == 0xF0:  # Tag/Nachtwert (UP-TLH/UP-T)
                                            if len(paket.ddata) >= 6:
                                                # Laut Dokumentation: Tagwert = (ddata[2] * 256 + ddata[3]) / 10.0
                                                # ddata[2] = Tagwert High, ddata[3] = Tagwert Low
                                                # Nachtwert = (ddata[4] * 256 + ddata[5]) / 10.0
                                                # ddata[4] = Nachtwert High, ddata[5] = Nachtwert Low
                                                presetday = (paket.ddata[2] * 256 + paket.ddata[3]) / 10.0
                                                presetnight = (paket.ddata[4] * 256 + paket.ddata[5]) / 10.0
                                                _LOGGER.debug(f"D0_RD_MODULSPEC_DATA_ACK 0xF0 for {device_id}: presetday={presetday}°C, presetnight={presetnight}°C")
                                                # Send updates to climate device and individual sensors
                                                async_dispatcher_send(self._hass, f"net4home_update_{device_id}", {"presetday": presetday, "presetnight": presetnight})
                                                async_dispatcher_send(self._hass, f"net4home_update_{device_id}_presetday", presetday)
                                                async_dispatcher_send(self._hass, f"net4home_update_{device_id}_presetnight", presetnight)
                                            else:
                                                _LOGGER.warning(f"D0_RD_MODULSPEC_DATA_ACK packet too short for 0xF0: {len(paket.ddata)} bytes")
                                            continue
                                        
                                        if b1 == 0xF1:  # Heat/Cool Objektadressen (UP-TLH/UP-T)
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

                                                if objadr <= 0:
                                                    device.objadr = None
                                                    device.tlh_f1_reply = 0
                                                    _LOGGER.warning(
                                                        "D0_RD_MODULSPEC_DATA_ACK 0xF1 for %s: base address is 0, raw %s",
                                                        device_id,
                                                        paket.ddata.hex(),
                                                    )
                                                    try:
                                                        devices = dict(self._entry.options.get("devices", {}))
                                                        if device_id in devices and "objadr" in devices[device_id]:
                                                            devices[device_id].pop("objadr", None)
                                                            new_options = dict(self._entry.options)
                                                            new_options["devices"] = devices
                                                            self._hass.config_entries.async_update_entry(
                                                                self._entry, options=new_options
                                                            )
                                                    except Exception as e:
                                                        _LOGGER.error(f"Failed to clear objadr for {device_id}: {e}")
                                                    await self._async_flush_pending_tlh_sensors(device)
                                                    continue

                                                device.objadr = objadr
                                                device.tlh_f1_reply = objadr
                                                try:
                                                    devices = dict(self._entry.options.get("devices", {}))
                                                    if device_id in devices:
                                                        devices[device_id]["objadr"] = objadr
                                                        new_options = dict(self._entry.options)
                                                        new_options["devices"] = devices
                                                        self._hass.config_entries.async_update_entry(self._entry, options=new_options)
                                                except Exception as e:
                                                    _LOGGER.error(f"Failed to save objadr for {device_id}: {e}")

                                                await self._async_flush_pending_tlh_sensors(device)

                                                # D0_REQ an die Basisadresse, um den Sollwert zu lesen
                                                await self._packet_sender.send_raw_command(
                                                    ipdst=objadr,
                                                    ddata=bytes([D0_REQ, 0x00, 0x00]),
                                                    objsource=self._objadr,
                                                    mi=self._mi,
                                                )
                                            else:
                                                _LOGGER.warning(f"D0_RD_MODULSPEC_DATA_ACK packet too short for 0xF1: {len(paket.ddata)} bytes")
                                            continue
                                        
                                        # UP-TLH / UP-T: channels 0, 1, 2 are temperature, illuminance, humidity.
        # From user software 1.17 the objects are adrBase+3/+4/+5.
        # Older firmware stores a separate address in each channel record.
        # Guessing an offset creates sensors at the wrong object.
                                        if b1 < 0x80:
                                            packet_address = None
                                            if len(paket.ddata) >= 4:
                                                packet_address = (paket.ddata[2] << 8) | paket.ddata[3]
                                            measured = tlh_measured_sensor(
                                                device.objadr,
                                                b1,
                                                getattr(device, "sw_version", None),
                                                packet_address,
                                            )
                                            if measured is None:
                                                if b1 in (0, 1, 2):
                                                    pending = getattr(device, "pending_tlh_channels", None)
                                                    if pending is None:
                                                        pending = []
                                                        device.pending_tlh_channels = pending
                                                    if not any(item[0] == b1 for item in pending):
                                                        pending.append((b1, packet_address))
                                                _LOGGER.debug(
                                                    "D0_RD_MODULSPEC_DATA_ACK UP-TLH/UP-T %s channel %s waits for base address (sw=%s)",
                                                    device_id,
                                                    b1,
                                                    getattr(device, "sw_version", None),
                                                )
                                                continue
                                            await self._async_register_tlh_measured_sensor(
                                                device, measured[0], measured[1]
                                            )
                                            if not tlh_uses_fixed_sensor_map(
                                                getattr(device, "sw_version", None)
                                            ):
                                                self._remember_legacy_tlh_sensor(
                                                    device, b1, measured[0]
                                                )
                                                await self._async_request_measured_value(measured[0])
                                            continue
                                    
                                    # HS-Time schedule rows are modulspec lines 0..47.
                                    if model == "HS-Time" and b1 < 48:
                                        lines = getattr(device, "hs_schedule_lines", None)
                                        if not isinstance(lines, dict):
                                            lines = {}
                                            device.hs_schedule_lines = lines
                                        lines[b1] = bytes(paket.ddata[2:15])
                                        self._release_line_read(paket.ipsrc, b0, b1)
                                        continue

                                    # 1.5. HS-Time: Modul-Info (ddata[1] = $FF) - Basisadresse lesen
                                    if model == "HS-Time" and b1 == 0xFF:
                                        if len(paket.ddata) >= 5:
                                            # Laut Dokumentation: ddata[2] = Objektadresse High, ddata[3] = Objektadresse Low
                                            objadr_high = paket.ddata[2]
                                            objadr_low = paket.ddata[3]
                                            objadr = (objadr_high << 8) + objadr_low
                                            # ddata[4] = Broadcast-Index (0-7)
                                            broadcast_index = paket.ddata[4]
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
                                                device.hs_broadcast_interval = broadcast_interval_str
                                                
                                                # Sende Broadcast-Intervall direkt an das MI-Device (wie bei UP-TLH)
                                                # WICHTIG: sensor_key ist "broadcast interval" (mit Leerzeichen), aber Dispatcher-Key verwendet slugify
                                                uid = device_id.upper()
                                                dispatcher_key_dict = f"net4home_update_{uid}"
                                                dispatcher_key_sensor = f"net4home_update_{uid}_{slugify('broadcast interval')}"
                                                async_dispatcher_send(self._hass, dispatcher_key_dict, {"broadcast interval": broadcast_interval_str})
                                                async_dispatcher_send(self._hass, dispatcher_key_sensor, broadcast_interval_str)
                                                
                                                if len(paket.ddata) >= 10 and paket.ddata[9] in (16, 48):
                                                    device.hs_tab_count = paket.ddata[9]
                                                sunrise_offset, sunset_offset = sun_object_offsets(
                                                    getattr(device, "sw_version", None),
                                                    getattr(device, "hs_tab_count", None),
                                                )
                                                device.hs_sunrise_obj = objadr + sunrise_offset
                                                device.hs_sunset_obj = objadr + sunset_offset
                                                await self._async_query_hs_time(device)
                                            else:
                                                _LOGGER.warning(f"D0_RD_MODULSPEC_DATA_ACK HS-Time 0xFF: Device {device_id} not found, cannot set objadr")
                                        else:
                                            _LOGGER.warning(f"D0_RD_MODULSPEC_DATA_ACK packet too short for HS-Time 0xFF: {len(paket.ddata)} bytes")
                                        continue
                            
                                    # 1.6. LCD3 (UP-LCD): b1..b2 = Adresse (Big Endian), $FFFF = Kapazitäts-Info
                                    # IMPORTANT: Check LCD BEFORE SensorConfig/PIR to avoid conflicts with b1 == 0
                                    elif model and 'LCD' in model.upper():
                                        device.lcd_modulspec_raw = paket.ddata.hex()
                                        line = None
                                        if len(paket.ddata) >= 3:
                                            line = (paket.ddata[1] << 8) | paket.ddata[2]
                                        base = lcd_base_from_modulspec(paket.ddata)
                                        if base is not None:
                                            device.objadr = base
                                            await self._async_save_objadr(device_id, base)
                                            _LOGGER.info(
                                                "UP-LCD %s object address %s, raw %s",
                                                device_id,
                                                base,
                                                paket.ddata[:8].hex(),
                                            )
                                            async_dispatcher_send(
                                                self._hass,
                                                f"net4home_device_updated_{self._entry.entry_id}",
                                                device_id,
                                            )
                                        elif line == 0:
                                            _LOGGER.warning(
                                                "UP-LCD %s line 0 has no object address, raw %s",
                                                device_id,
                                                paket.ddata.hex(),
                                            )
                                        if line == 0:
                                            self._release_line_read(
                                                paket.ipsrc, D0_RD_MODULSPEC_DATA_ACK, 0
                                            )
                                        continue

                                    elif model == ".WAV-Bell" or device.module_type == PLATINE_HW_IS_BELL2:
                                        await self._async_handle_bell_modulspec(device, paket.ddata)
                                        continue

                                    # 5. IR_TX: b1 = $FF = Modul-Info, b1 < $80 = Tabelle, b1 >= $C0 = MaxPower
                                    elif model and 'IR' in model.upper() and 'TX' in model.upper():
                                        if b1 == 0xFF:
                                            # Modul-Info
                                            if len(paket.ddata) >= 6:
                                                tab_entry_count = paket.ddata[2]
                                                adr_obj_ir = paket.ddata[3] * 256 + paket.ddata[4]  # Little Endian
                                                tab2_entry_count = paket.ddata[5]
                                            else:
                                                _LOGGER.warning(f"D0_RD_MODULSPEC_DATA_ACK packet too short for IR_TX Modul-Info: {len(paket.ddata)} bytes")
                                        elif b1 < 0x80:
                                            # Haupttabelle
                                            if len(paket.ddata) >= 26:
                                                tab_index = b1
                                                # Table data can be stored for later use
                                            else:
                                                _LOGGER.warning(f"D0_RD_MODULSPEC_DATA_ACK packet too short for IR_TX Tabelle: {len(paket.ddata)} bytes")
                                        elif b1 >= 0xC0:
                                            # MaxPower-Tabelle
                                            if len(paket.ddata) >= 34:
                                                tab2_index = b1 - 0xC0
                                                # Table data can be stored for later use
                                            else:
                                                _LOGGER.warning(f"D0_RD_MODULSPEC_DATA_ACK packet too short for IR_TX MaxPower: {len(paket.ddata)} bytes")
                                        continue

                                    _LOGGER.info(
                                        "Modulspec reply from %s (%s) line %s len=%s raw %s",
                                        device_id,
                                        model,
                                        b1,
                                        len(paket.ddata),
                                        paket.ddata[:24].hex(),
                                    )

                                elif b0 == D0_VALUE_ACK:
                                        device_id = f"OBJ{paket.objsrc:05d}"
                                        # _LOGGER.debug(f"D0_VALUE_ACK for {device_id} – Type: {paket.ddata[1]}")

                                        # Check if packet has enough data (need at least 5 bytes for sensor values)
                                        if len(paket.ddata) < 5:
                                            _LOGGER.warning(f"D0_VALUE_ACK packet too short: {len(paket.ddata)} bytes, expected at least 5")
                                            continue

                                        if paket.ddata[1] == IN_HW_NR_IS_CLOCK:
                                            clock = parse_hs_time_clock(paket.ddata)
                                            mi_device = self.get_known_device(f"MI{paket.ipsrc:04X}")
                                            if mi_device is None or mi_device.model != "HS-Time":
                                                mi_device = next(
                                                    (
                                                        item
                                                        for item in self.devices.values()
                                                        if item.model == "HS-Time"
                                                        and item.objadr == paket.objsrc
                                                    ),
                                                    None,
                                                )
                                            if clock is None or mi_device is None:
                                                _LOGGER.warning(
                                                    "HS-Time clock reply from MI%04X did not match, len=%s raw %s",
                                                    paket.ipsrc,
                                                    len(paket.ddata),
                                                    paket.ddata.hex(),
                                                )
                                                continue
                                            mi_device.hs_clock = clock
                                            async_dispatcher_send(
                                                self._hass,
                                                f"net4home_update_{mi_device.device_id.upper()}_hs_clock",
                                                clock,
                                            )
                                            if not getattr(mi_device, "hs_clock_logged", False):
                                                mi_device.hs_clock_logged = True
                                                _LOGGER.info(
                                                    "HS-Time %s clock %s synced=%s reception=%s",
                                                    mi_device.device_id,
                                                    clock["time"],
                                                    clock["synced"],
                                                    clock["reception"],
                                                )
                                            continue

                                        if paket.ddata[1] == IN_HW_NR_IS_TEMP:
                                            i_analog_value = paket.ddata[3] * 256 + paket.ddata[4]
                                            if i_analog_value > 0x8000:
                                                i_analog_value -= 0x10000
                                            i_analog_value = (i_analog_value * 10) // 16
                                            value = round(i_analog_value / 10, 1)
                                            sensor_type = "temperature"
                                            self._remember_measured_value(device_id, sensor_type, value)
                                            dispatcher_key = f"net4home_update_{device_id}_{sensor_type}"
                                            async_dispatcher_send(self._hass, dispatcher_key, value)
                                    
                                        elif paket.ddata[1] == IN_HW_NR_IS_HUMIDITY:
                                            value = paket.ddata[3] * 256 + paket.ddata[4]
                                            sensor_type = "humidity"
                                            self._remember_measured_value(device_id, sensor_type, value)
                                            dispatcher_key = f"net4home_update_{device_id}_{sensor_type}"
                                            async_dispatcher_send(self._hass, dispatcher_key, value)
                                        
                                        elif paket.ddata[1] == IN_HW_NR_IS_LICHT_ANALOG:
                                            value = paket.ddata[3] * 256 + paket.ddata[4]
                                            sensor_type = "illuminance"
                                            self._remember_measured_value(device_id, sensor_type, value)
                                            dispatcher_key = f"net4home_update_{device_id}_{sensor_type}"
                                            async_dispatcher_send(self._hass, dispatcher_key, value)
                                            #_LOGGER.debug(f"_illuminance D0_VALUE_ACK for {dispatcher_key} – Value: {value}")
                                    
                                        # HS-Time: Sonnenaufgang (VAL_IS_MIN_TAG_WORD_SA = 50)
                                        elif paket.ddata[1] in (
                                            VAL_IS_MIN_TAG_WORD_SA,
                                            VAL_IS_MIN_TAG_WORD_SU,
                                        ):
                                            sun_kind = (
                                                "sunrise"
                                                if paket.ddata[1] == VAL_IS_MIN_TAG_WORD_SA
                                                else "sunset"
                                            )
                                            device_id_from_ipsrc = f"MI{paket.ipsrc:04X}"
                                            mi_device = self.get_known_device(device_id_from_ipsrc)
                                            if mi_device is None or mi_device.model != "HS-Time":
                                                mi_device = next(
                                                    (
                                                        item
                                                        for item in self.devices.values()
                                                        if item.model == "HS-Time"
                                                        and paket.objsrc
                                                        in (
                                                            getattr(item, "hs_sunrise_obj", None),
                                                            getattr(item, "hs_sunset_obj", None),
                                                        )
                                                    ),
                                                    None,
                                                )
                                            if mi_device and mi_device.model == "HS-Time":
                                                value = sun_time_from_ack(paket.ddata)
                                                target = mi_device.device_id.upper()
                                                if value is None:
                                                    _LOGGER.warning(
                                                        "HS-Time %s %s reply too short: %s",
                                                        target,
                                                        sun_kind,
                                                        paket.ddata.hex(),
                                                    )
                                                else:
                                                    setattr(mi_device, f"hs_{sun_kind}", value)
                                                    async_dispatcher_send(
                                                        self._hass,
                                                        f"net4home_update_{target}_{sun_kind}",
                                                        value,
                                                    )
                                                    _LOGGER.info(
                                                        "HS-Time %s %s %s raw %s",
                                                        target,
                                                        sun_kind,
                                                        value,
                                                        paket.ddata.hex(),
                                                    )
                                            else:
                                                _LOGGER.warning(
                                                    "HS-Time %s reply from MI%04X did not match",
                                                    sun_kind,
                                                    paket.ipsrc,
                                                )
                                    
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
                                                dispatcher_key = f"net4home_update_{via_device_id}_rf_key"
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
                                                self._schedule_rf_key_list(via_device_id, (1.5,), replace=False)
                                            else:
                                                dispatcher_key = f"net4home_update_{device_id}_rf_key"
                                                async_dispatcher_send(self._hass, dispatcher_key, {
                                                    "rf_key": rf_key_hex,
                                                    "state": state
                                                })
                                                _LOGGER.debug(
                                                    f"RF-Key detected: {rf_key_hex} ({state}) from {device_id} (parent not found)"
                                                )
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
                                    
                                        # Check if packet has enough data
                                        if len(paket.ddata) < 4:
                                            _LOGGER.warning(f"STATUS_INFO packet too short: {len(paket.ddata)} bytes, expected at least 4")
                                            continue
                                    
                                        is_on = paket.ddata[2] == 1
                                    
                                        if paket.ddata[3] == OUT_HW_NR_IS_DIMMER:
                                            is_on = paket.ddata[2] >> 7
                                            brightness_value = round((paket.ddata[2] & 0x7F) * 255 / 100)
                                            _LOGGER.debug(f"STATUS_INFO for {device_id}: {'ON' if is_on else 'OFF'} {brightness_value}%")
                                            async_dispatcher_send(
                                                self._hass,
                                                f"net4home_update_{device_id}",
                                                {
                                                    "is_on": is_on,
                                                    "brightness": brightness_value
                                                }
                                            )
                                        elif paket.ddata[3] == OUT_HW_NR_IS_SLOW_PWM:
                                            is_on, brightness_value = pwm_status_to_ha(
                                                paket.ddata[1], paket.ddata[2]
                                            )
                                            _LOGGER.debug(
                                                "STATUS_INFO for %s: %s %s%%",
                                                device_id,
                                                "ON" if is_on else "OFF",
                                                round(brightness_value * 100 / 255),
                                            )
                                            async_dispatcher_send(
                                                self._hass,
                                                f"net4home_update_{device_id}",
                                                {
                                                    "is_on": is_on,
                                                    "brightness": brightness_value,
                                                },
                                            )
                                        else:
                                            # _LOGGER.debug(f"STATUS_INFO for {device_id}: {'ON' if is_on else 'OFF'}")
                                            async_dispatcher_send(self._hass, f"net4home_update_{device_id}", is_on)

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
