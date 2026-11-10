"""UP-T and UP-TLH commands."""
import asyncio
import logging
from typing import Optional

from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
)

from .const import (
    D0_ENABLE_CONFIGURATION,
    D0_RD_MODULSPEC_DATA,
    D0_REQ,
    D0_SET,
    D0_SET_N,
    D0_VALUE_REQ,
    D0_WR_MODULSPEC_DATA,
    D1_ENABLE_CONFIGURATION_OK_BYTE,
    DOMAIN,
    SEND_AS_IP,
    SEND_AS_OBJ_GRP,
)
from .tlh_layout import (
    pack_day_night_record,
    tlh_measured_sensor,
    tlh_uses_fixed_sensor_map,
)
from .helpers import register_device_in_registry

_LOGGER = logging.getLogger(__name__)

_MEASURED_SENSOR_NAMES = ("temperature sensor", "humidity sensor", "illuminance sensor")


def _is_measured_sensor(device) -> bool:
    """True for a UP-TLH temperature, illuminance or humidity object."""
    name = (getattr(device, "name", None) or "").lower()
    return any(name.startswith(prefix) for prefix in _MEASURED_SENSOR_NAMES)

class ClimateCommands:
    """UP-T and UP-TLH commands."""

    async def _async_register_tlh_measured_sensor(self, parent, sensor_obj: int, sensor_type: str) -> None:
        """Register one UP-TLH or UP-T measured-value sensor under its parent module."""
        sensor_id = f"OBJ{sensor_obj:05d}"
        _LOGGER.debug(
            "UP-TLH/UP-T %s channel %s -> %s",
            parent.device_id,
            sensor_type,
            sensor_id,
        )
        await register_device_in_registry(
            hass=self._hass,
            entry=self._entry,
            device_id=sensor_id,
            name=f"{sensor_type.capitalize()} Sensor {sensor_obj}",
            model="Sensor",
            sw_version="",
            hw_version="",
            device_type="sensor",
            via_device=parent.device_id,
            api=self,
            objadr=sensor_obj,
        )

    async def _async_flush_pending_tlh_sensors(self, device) -> None:
        """Register sensor channels that arrived before the base address was known."""
        pending = getattr(device, "pending_tlh_channels", None) or []
        if not pending:
            return
        device.pending_tlh_channels = []
        for channel, packet_address in pending:
            measured = tlh_measured_sensor(
                device.objadr,
                channel,
                getattr(device, "sw_version", None),
                packet_address,
            )
            if measured is None:
                _LOGGER.warning(
                    "UP-TLH/UP-T %s channel %s still has no object address (objadr=%s, sw=%s)",
                    device.device_id,
                    channel,
                    device.objadr,
                    getattr(device, "sw_version", None),
                )
                continue
            await self._async_register_tlh_measured_sensor(device, measured[0], measured[1])

    def _remember_measured_value(self, device_id: str, sensor_type: str, value) -> None:
        """Keep the latest measured value on the device so a late entity still shows it."""
        device = self.devices.get(device_id)
        if device is not None:
            setattr(device, sensor_type, value)

    def _tlh_base_from_children(self, parent) -> int | None:
        """Recover adrBase from sensor children when 0xF1 was not stored.

        Only firmware from 1.17 has a fixed offset. Older channel records
        carry their own address, so they cannot be turned back into a base.
        """
        if not tlh_uses_fixed_sensor_map(parent.sw_version):
            return None
        offsets = (("temperature", 3), ("illuminance", 4), ("humidity", 5))
        parent_id = parent.device_id.upper()
        bases = []
        for child in self.devices.values():
            if (child.via_device or "").upper() != parent_id:
                continue
            if not child.device_id.startswith("OBJ"):
                continue
            try:
                address = int(child.device_id[3:])
            except ValueError:
                continue
            name = (child.name or "").lower()
            for kind, offset in offsets:
                if kind in name:
                    bases.append(address - offset)
                    break
        if len(set(bases)) != 1:
            return None
        base = bases[0]
        return base if base > 0 else None

    async def async_ensure_tlh_measured_sensors(self) -> None:
        """Register the three measured-value sensors of UP-TLH and UP-T from 1.17 on.

        From that version the objects are adrBase+3, +4 and +5, so a dropped
        object such as OBJ25004 can be restored without reading the channel
        record again. Older firmware is handled by async_refresh_legacy_tlh_sensors.
        """
        parents = [
            device
            for device_id, device in self.devices.items()
            if device.device_type == "climate"
            and device.model in ("UP-TLH", "UP-T")
            and device_id.startswith("MI")
        ]
        for parent in parents:
            if not tlh_uses_fixed_sensor_map(parent.sw_version):
                continue
            adr_base = parent.objadr if parent.objadr and parent.objadr > 0 else None
            if adr_base is None:
                adr_base = self._tlh_base_from_children(parent)
            if not adr_base:
                continue
            for channel in (0, 1, 2):
                measured = tlh_measured_sensor(
                    adr_base, channel, parent.sw_version, None
                )
                if measured is None:
                    continue
                sensor_obj, _sensor_type = measured
                sensor_id = f"OBJ{sensor_obj:05d}"
                if sensor_id in self.devices:
                    continue
                await self._async_register_tlh_measured_sensor(
                    parent, sensor_obj, _sensor_type
                )

    def _legacy_tlh_valid_addresses(self, device) -> Optional[set]:
        """The three sensor objects, once enough channel records have arrived.

        A missing reply is filled in only when the setpoint base and the two
        replies sit on base, base+1 and base+2 and the missing one is already
        registered. MI0259 does not use that layout, so a partial reply there
        does not delete anything.
        """
        known = getattr(device, "tlh_sensor_objects", {})
        if not isinstance(known, dict):
            return None
        learned = {
            addr for addr in known.values() if isinstance(addr, int) and addr > 0
        }
        if all(index in known for index in (0, 1, 2)) and len(learned) == 3:
            return learned
        base = device.objadr if getattr(device, "objadr", None) else None
        if not base or base <= 0 or len(learned) < 2:
            return None
        expected = {base, base + 1, base + 2}
        if not learned <= expected:
            return None
        parent_id = device.device_id.upper()
        child_addrs = {
            child.objadr
            for child in self.devices.values()
            if (child.via_device or "").upper() == parent_id
            and child.device_type == "sensor"
            and child.objadr
        }
        if (expected - learned) <= child_addrs:
            return expected
        return None

    def _remember_legacy_tlh_sensor(self, device, channel: int, objadr: int) -> None:
        """Keep the address just read from one old-firmware sensor record."""
        known = getattr(device, "tlh_sensor_objects", None)
        if isinstance(known, dict) and objadr:
            known[channel] = objadr

    async def _async_drop_stale_tlh_sensors(self, parent, valid: set[int]) -> None:
        """Remove sensor children whose object is not in the three channel records.

        Earlier versions guessed adrBase+1/+2/+3. Those entities stay unavailable
        and come back after a restart as long as the config entry still lists them.
        """
        parent_id = parent.device_id.upper()
        stale = [
            child.device_id
            for child in list(self.devices.values())
            if (child.via_device or "").upper() == parent_id
            and child.device_type == "sensor"
            and str(child.device_id).upper().startswith("OBJ")
            and child.objadr not in valid
        ]
        dev_reg = dr.async_get(self._hass)
        ent_reg = er.async_get(self._hass)
        devices = dict(self._entry.options.get("devices", {}))
        changed = False
        parent_reg = dev_reg.async_get_device_by_identifier(
            (DOMAIN, parent_id), self._entry.entry_id
        )
        registry_ids = {child_id.upper() for child_id in stale}
        if parent_reg is not None:
            for registry_device in dr.async_entries_for_config_entry(
                dev_reg, self._entry.entry_id
            ):
                if registry_device.via_device_id != parent_reg.id:
                    continue
                for domain, identifier in registry_device.identifiers:
                    if domain != DOMAIN or not str(identifier).upper().startswith("OBJ"):
                        continue
                    try:
                        objadr = int(str(identifier)[3:])
                    except ValueError:
                        continue
                    if objadr not in valid:
                        registry_ids.add(str(identifier).upper())
        for child_id in sorted(registry_ids):
            registry_device = dev_reg.async_get_device_by_identifier(
                (DOMAIN, child_id), self._entry.entry_id
            )
            if registry_device is not None:
                for entity in er.async_entries_for_device(
                    ent_reg,
                    registry_device.id,
                    include_disabled_entities=True,
                ):
                    ent_reg.async_remove(entity.entity_id)
                dev_reg.async_remove_device(registry_device.id)
            self.devices.pop(child_id, None)
            for key in list(devices):
                if key.upper() == child_id:
                    devices.pop(key)
                    changed = True
            _LOGGER.info(
                "UP-TLH %s removed unused sensor %s", parent.device_id, child_id
            )
        if changed:
            options = dict(self._entry.options)
            options["devices"] = devices
            self._hass.config_entries.async_update_entry(self._entry, options=options)

    async def _async_request_measured_value(self, objadr: int) -> None:
        """Ask one sensor object for its current value."""
        if self._packet_sender is None or not objadr or objadr <= 0:
            return
        await self._packet_sender.send_raw_command(
            ipdst=objadr,
            ddata=bytes([D0_VALUE_REQ, 0x00, 0x00]),
            objsource=self._objadr,
            mi=self._mi,
        )

    async def async_refresh_legacy_tlh_sensors(self) -> None:
        """Read the sensor records of UP-TLH and UP-T modules older than 1.17.

        Those records hold the object address. The value is then requested,
        because these modules do not publish it on the fixed offsets.
        """
        if self._packet_sender is None:
            return
        for device_id, device in list(self.devices.items()):
            if (
                device.device_type != "climate"
                or device.model not in ("UP-TLH", "UP-T")
                or not device_id.startswith("MI")
                or tlh_uses_fixed_sensor_map(device.sw_version)
            ):
                continue
            try:
                mi_addr = int(device_id[2:], 16)
            except ValueError:
                continue
            _LOGGER.info(
                "UP-TLH %s user software %s: reading sensor records",
                device_id,
                device.sw_version,
            )
            device.tlh_sensor_objects = {}
            for index in range(3):
                await self._packet_sender.send_raw_command(
                    ipdst=mi_addr,
                    ddata=bytes([D0_RD_MODULSPEC_DATA, index, 0x00]),
                    objsource=self._objadr,
                    mi=self._mi,
                    type8=SEND_AS_IP,
                )
                await asyncio.sleep(0.25)
            await asyncio.sleep(1.0)
            valid = self._legacy_tlh_valid_addresses(device)
            if valid is not None:
                await self._async_drop_stale_tlh_sensors(device, valid)
            for child in list(self.devices.values()):
                if (child.via_device or "").upper() != device_id.upper():
                    continue
                if child.device_type != "sensor" or not child.objadr:
                    continue
                await self._async_request_measured_value(child.objadr)
                await asyncio.sleep(0.1)

    async def async_activate_all_sensors(self):
        """Ask every sensor object for its current value.

        Temperature, light and humidity answer D0_VALUE_REQ. Other sensors
        answer D0_REQ.
        """
        if self._packet_sender is None:
            _LOGGER.warning("Cannot activate sensors: not connected")
            return
        sensor_count = 0
        for device_id, device in self.devices.items():
            if device.device_type != "sensor" or not device_id.startswith("OBJ"):
                continue
            try:
                obj_addr = int(device_id[3:])
            except ValueError:
                _LOGGER.error(f"Failed to parse OBJ address from {device_id}")
                continue
            if obj_addr <= 0:
                continue
            measured = _is_measured_sensor(device)
            _LOGGER.debug(
                "Reading %s at object %s",
                device_id,
                obj_addr,
            )
            await self._packet_sender.send_raw_command(
                ipdst=obj_addr,
                ddata=bytes([D0_VALUE_REQ if measured else D0_REQ, 0x00, 0x00]),
                objsource=self._objadr,
                mi=self._mi,
                type8=SEND_AS_OBJ_GRP,
            )
            sensor_count += 1
            await asyncio.sleep(0.1)
        _LOGGER.info("Requested current values from %s sensors", sensor_count)

    async def async_refresh_climate_setpoints(self) -> None:
        """Read the current setpoint and the heat/cool controller flags.

        The reply is a D0_ACTOR_ACK from the setpoint object (adrBase). Day and
        night presets come from a different read and are not this value.
        """
        if self._packet_sender is None:
            _LOGGER.warning("Cannot read climate setpoints: not connected")
            return
        for device_id, device in self.devices.items():
            if (
                device.device_type != "climate"
                or device.model not in ("UP-TLH", "UP-T")
                or not device_id.startswith("MI")
            ):
                continue
            objadr = device.objadr if device.objadr and device.objadr > 0 else None
            if objadr is None:
                _LOGGER.info("UP-TLH %s has no setpoint address, setpoint not read", device_id)
                continue
            try:
                _LOGGER.debug("Reading setpoint of %s at object %s", device_id, objadr)
                await self._packet_sender.send_raw_command(
                    ipdst=objadr,
                    ddata=bytes([D0_REQ, 0x00, 0x00]),
                    objsource=self._objadr,
                    mi=self._mi,
                )
                await asyncio.sleep(0.2)
            except (ValueError, Exception) as err:
                _LOGGER.warning("Failed to read setpoint of %s: %s", device_id, err)

    async def async_refresh_preset_values_up_tlh(self):
        """Read day and night presets for UP-TLH and UP-T modules loaded from config."""
        if self._packet_sender is None:
            _LOGGER.warning("Cannot refresh UP-TLH presets: not connected")
            return
        for device_id, device in self.devices.items():
            if (
                device.device_type != "climate"
                or device.model not in ("UP-TLH", "UP-T")
                or not device_id.startswith("MI")
            ):
                continue
            if (
                getattr(device, "presetday", None) is not None
                and getattr(device, "presetnight", None) is not None
            ):
                continue
            try:
                mi_addr = int(device_id[2:], 16)
                _LOGGER.debug("Refreshing preset values (0xF0) for %s", device_id)
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

    def _find_up_tlh_by_objadr(self, objadr: int):
        """Find a UP-TLH or UP-T climate device by its setpoint object address."""
        for device in self.devices.values():
            if (
                device.device_type == "climate"
                and device.model in ("UP-TLH", "UP-T")
                and device.objadr is not None
                and device.objadr == objadr
            ):
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
            update_data = {"targettemp": temperature}
            async_dispatcher_send(self._hass, f"net4home_update_{device_id}", update_data)
            _LOGGER.debug(f"Sent immediate update for targettemp={temperature:.1f}°C to {device_id}")

    async def async_set_climate_presets(
        self, device_id: str, presetday: float, presetnight: float
    ) -> None:
        """Write Tagwert and Nachtwert. The module stores them as one record."""
        device = self.devices.get(device_id)
        if not device or device.model not in ("UP-TLH", "UP-T"):
            _LOGGER.error("Device %s is not a UP-TLH or UP-T", device_id)
            return
        if self._packet_sender is None:
            _LOGGER.error("Cannot write day/night values: not connected")
            return
        try:
            record = pack_day_night_record(presetday, presetnight)
            mi_addr = int(device_id[2:], 16)
        except ValueError as err:
            _LOGGER.error("Cannot write day/night values for %s: %s", device_id, err)
            return

        device.presetday = presetday
        device.presetnight = presetnight
        dispatch_id = device_id.upper()
        async_dispatcher_send(
            self._hass,
            f"net4home_update_{dispatch_id}",
            {"presetday": presetday, "presetnight": presetnight},
        )
        async_dispatcher_send(self._hass, f"net4home_update_{dispatch_id}_presetday", presetday)
        async_dispatcher_send(self._hass, f"net4home_update_{dispatch_id}_presetnight", presetnight)

        await self._packet_sender.send_raw_command(
            ipdst=mi_addr,
            ddata=bytes([D0_ENABLE_CONFIGURATION, D1_ENABLE_CONFIGURATION_OK_BYTE, 0x00]),
            objsource=self._objadr,
            mi=self._mi,
            type8=SEND_AS_IP,
        )
        await asyncio.sleep(0.4)
        await self._packet_sender.send_raw_command(
            ipdst=mi_addr,
            ddata=bytes([D0_WR_MODULSPEC_DATA]) + record,
            objsource=self._objadr,
            mi=self._mi,
            type8=SEND_AS_IP,
        )
        _LOGGER.info(
            "UP-TLH %s day %s °C, night %s °C written",
            device_id,
            presetday,
            presetnight,
        )
        await asyncio.sleep(0.4)
        await self._packet_sender.send_raw_command(
            ipdst=mi_addr,
            ddata=bytes([D0_RD_MODULSPEC_DATA, 0xF0, 0x00]),
            objsource=self._objadr,
            mi=self._mi,
            type8=SEND_AS_IP,
        )
