"""Switch, light and cover commands."""
import asyncio
import logging
from datetime import datetime

from .const import (
    D0_ENABLE_CONFIGURATION,
    D0_RD_ACTOR_DATA,
    D0_RD_ACTOR_DATA_ACK,
    D0_REQ,
    D0_RESET_MODUL,
    D0_SET,
    D0_TOGGLE,
    D1_ENABLE_CONFIGURATION_OK_BYTE,
    SEND_AS_IP,
)
from .dimmer_layout import light_on_command

_LOGGER = logging.getLogger(__name__)

class ActorCommands:
    """Switch, light and cover commands."""

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

    async def async_request_missing_actor_channels(self, device_id: str) -> None:
        """Read actor channels again when a module's OBJ channel is missing."""
        device = self.devices.get(device_id)
        if not device or not device_id.startswith("MI"):
            return
        if device_id in self._missing_actor_reread:
            return
        self._missing_actor_reread.add(device_id)

        channel_count = device.na if device.na and device.na > 0 else 8
        known_children = {
            child.device_id
            for child in self.devices.values()
            if child.via_device == device_id
        }
        _LOGGER.info(
            "Requesting %s actor channels from %s",
            channel_count,
            device_id,
        )
        try:
            mi_addr = int(device_id[2:], 16)
            await self._packet_sender.send_raw_command(
                ipdst=mi_addr,
                ddata=bytes([D0_ENABLE_CONFIGURATION, D1_ENABLE_CONFIGURATION_OK_BYTE]),
                objsource=self._objadr,
                mi=self._mi,
                type8=SEND_AS_IP,
            )
            await asyncio.sleep(0.2)
            await self._async_read_table_lines(
                mi_addr,
                D0_RD_ACTOR_DATA,
                D0_RD_ACTOR_DATA_ACK,
                channel_count,
                "Actor",
            )
            for _ in range(10):
                appeared = [
                    child.device_id
                    for child in self.devices.values()
                    if child.via_device == device_id and child.device_id not in known_children
                ]
                if appeared:
                    _LOGGER.info("Actor channels from %s: %s", device_id, appeared)
                    return
                await asyncio.sleep(0.1)
            _LOGGER.debug(
                "No new actor channel from %s (unused output or empty object address)",
                device_id,
            )
        except Exception as e:
            _LOGGER.error("Actor channel request for %s failed: %s", device_id, e)
            self._missing_actor_reread.discard(device_id)

    async def async_reread_incomplete_actor_modules(self) -> None:
        """Request actor data for modules that have fewer channels than na."""
        for device in list(self.devices.values()):
            if device.device_type != "module" or not device.device_id.startswith("MI"):
                continue
            if not device.na or device.na <= 0:
                continue
            children = sum(
                1
                for child in self.devices.values()
                if child.via_device == device.device_id
                and child.device_type in ("light", "switch", "cover")
            )
            if children >= device.na:
                continue
            _LOGGER.info(
                "%s has %s of %s actor channels, requesting the missing ones",
                device.device_id,
                children,
                device.na,
            )
            await self.async_request_missing_actor_channels(device.device_id)

    async def async_load_missing_actor_settings(self) -> None:
        """Read actor lines once when power-up was never stored.

        After this read the values stay in the config entry, so the next
        start does not ask again.
        """
        pending = []
        for device in list(self.devices.values()):
            if device.device_type != "module" or not str(device.device_id).startswith("MI"):
                continue
            if not device.na or device.na <= 0:
                continue
            children = [
                child
                for child in self.devices.values()
                if child.via_device == device.device_id
                and child.device_type in ("light", "switch")
            ]
            if not children:
                continue
            if all(getattr(child, "powerup_status", None) is not None for child in children):
                continue
            pending.append(device.device_id)
        if not pending:
            return
        _LOGGER.info("Reading stored actor settings for %s modules", len(pending))
        for device_id in pending:
            await self.async_read_device_config(device_id)

    async def async_reset_module(self, device_id: str) -> None:
        """Reboot one MI module. Same command as Reset in the configurator."""
        if self._packet_sender is None:
            _LOGGER.warning("Cannot reset %s: not connected", device_id)
            return
        if not str(device_id).startswith("MI"):
            _LOGGER.warning("Invalid device_id: %s for reset (expected MI address)", device_id)
            return
        device = self.devices.get(device_id)
        if device is None or device.via_device:
            _LOGGER.warning("Reset refused for %s: not an MI module", device_id)
            return
        try:
            mi_addr = int(device_id[2:], 16)
        except ValueError:
            _LOGGER.warning("Invalid MI address: %s", device_id)
            return
        await self._packet_sender.send_raw_command(
            ipdst=mi_addr,
            ddata=bytes([D0_RESET_MODUL, 0x00, 0x00]),
            objsource=self._objadr,
            mi=self._mi,
            type8=SEND_AS_IP,
        )
        _LOGGER.info("Reset sent to %s (%s)", device_id, device.model)

    async def async_read_device_config(self, device_id: str):
        """Read device configuration for MI device (queues device for detail retrieval)."""
        try:
            if not device_id.startswith("MI"):
                _LOGGER.warning(f"Invalid device_id: {device_id} for config read (expected MI address).")
                return

            device = self.devices.get(device_id)
            if not device:
                _LOGGER.warning(f"Device {device_id} not found")
                return
            
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
                # Try to start the queue if it's not running
                await self.async_start_detail_retrieval()
            
            if self._detail_queue is not None and self._detail_queue_running:
                await self._detail_queue.put(device_id)
                queue_size = self._detail_queue.qsize()
                _LOGGER.info(f"Device {device_id} ({device.model}) queued for detail retrieval (queue running: {self._detail_queue_running}, queue size after put: {queue_size})")
            else:
                _LOGGER.warning(f"Detail queue not running, cannot queue {device_id}. Queue running: {self._detail_queue_running}")

            if device.device_type == "rf_reader":
                self._schedule_rf_key_list(device_id, (0.8,))
            
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

    async def async_turn_on_light(self, device_id: str, brightness: int | None = 255):
        """Turn a dimmer on. None on a timer dimmer recalls the last level."""
        device = self.devices.get(device_id)

        if not device:
            _LOGGER.warning(f"No light device with ID {device_id} found")
            return
        objadr = device.objadr

        if objadr is None:
            _LOGGER.warning(f"No objadr for light {device_id}")
            return
        command = light_on_command(device.model, brightness)
        await self._packet_sender.send_raw_command(
            ipdst=objadr,
            ddata=command,
            objsource=self._objadr,
            mi=self._mi,
        )
        _LOGGER.debug(
            "Turn light ON %s command %s (OBJ=%s)",
            device_id,
            command.hex(),
            objadr,
        )

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
