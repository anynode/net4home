"""UP-RF key list commands."""
import asyncio
import logging
import time

from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    D0_ENABLE_CONFIGURATION,
    D0_RD_MODULSPEC_DATA,
    D0_WR_MODULSPEC_DATA,
    D1_ENABLE_CONFIGURATION_OK_BYTE,
    PLATINE_HW_IS_UP_RF2,
    SEND_AS_IP,
)
from .rf_keys import (
    RF_KEY_COUNT,
    RF_KEY_TABLE_LINES,
)
from .models import Net4HomeDevice

_LOGGER = logging.getLogger(__name__)

class RfCommands:
    """UP-RF key list commands."""

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
            self._schedule_rf_key_list(device_id, (8.0, 12.0))
        except Exception as e:
            _LOGGER.error(f"Error starting Masterkey learning for {device_id}: {e}")

    def _rf_key_read_active(self) -> bool:
        """True while a key-table or door-list reply is still expected."""
        now = time.monotonic()
        return any(
            getattr(device, "rf_key_list_until", 0) > now
            for device in self.devices.values()
            if device.device_type == "rf_reader"
        )

    def _ensure_rf_keys(self, device: Net4HomeDevice) -> list:
        """Return the ten key slots stored on an UP-RF module."""
        slots = getattr(device, "rf_keys", None)
        if not isinstance(slots, list) or len(slots) != RF_KEY_COUNT:
            device.rf_keys = [{"code": "", "master": False} for _ in range(RF_KEY_COUNT)]
        return device.rf_keys

    def _apply_rf_master(self, device: Net4HomeDevice) -> None:
        """Mark the slot named by the master index and publish every slot."""
        slots = self._ensure_rf_keys(device)
        master = getattr(device, "rf_master_index", None)
        for index, slot in enumerate(slots):
            slot["master"] = master == index and bool(slot["code"])
            self._publish_rf_slot(device, index)

    def _publish_rf_slot(self, device: Net4HomeDevice, index: int) -> None:
        """Push one key slot to its sensor."""
        slot = device.rf_keys[index]
        async_dispatcher_send(
            self._hass,
            f"net4home_update_{device.device_id.upper()}_rf_slot_{index}",
            {"code": slot["code"] or None, "master": bool(slot["master"])},
        )

    async def async_request_rf_key_list(self, device_id: str) -> None:
        """Read the master index and the ten keys from the module table."""
        device = self.devices.get(device_id)
        if (
            self._packet_sender is None
            or device is None
            or device.device_type != "rf_reader"
            or not device_id.startswith("MI")
        ):
            return
        self._ensure_rf_keys(device)
        device.rf_master_index = None
        device.rf_key_list_until = time.monotonic() + 8.0
        mi_addr = int(device_id[2:], 16)
        use_table = device.module_type == PLATINE_HW_IS_UP_RF2 or (device.nm or 0) > 0
        _LOGGER.info(
            "UP-RF %s key read type=%s nm=%s sw=%s path=%s",
            device_id,
            device.module_type,
            device.nm,
            device.sw_version,
            "table" if use_table else "door",
        )
        if use_table:
            await self._packet_sender.send_raw_command(
                ipdst=mi_addr,
                ddata=bytes([D0_ENABLE_CONFIGURATION, D1_ENABLE_CONFIGURATION_OK_BYTE]),
                objsource=self._objadr,
                mi=self._mi,
                type8=SEND_AS_IP,
            )
            await asyncio.sleep(0.2)
            for line in RF_KEY_TABLE_LINES:
                device.rf_key_list_until = time.monotonic() + 4.0
                await self._packet_sender.send_raw_command(
                    ipdst=mi_addr,
                    ddata=bytes([D0_RD_MODULSPEC_DATA, line, 0x00]),
                    objsource=self._objadr,
                    mi=self._mi,
                    type8=SEND_AS_IP,
                )
                await asyncio.sleep(0.15)
            return
        await self._packet_sender.send_raw_command(
            ipdst=mi_addr,
            ddata=bytes([D0_RD_MODULSPEC_DATA, 0x00, 0x00]),
            objsource=self._objadr,
            mi=self._mi,
            type8=SEND_AS_IP,
        )

    async def async_clear_all_rf_keys(self, device_id: str) -> None:
        """Delete every key stored in an UP-RF module."""
        device = self.devices.get(device_id)
        if (
            self._packet_sender is None
            or device is None
            or device.device_type != "rf_reader"
            or not device_id.startswith("MI")
        ):
            _LOGGER.warning("Cannot delete RF keys for %s", device_id)
            return
        mi_addr = int(device_id[2:], 16)
        await self._packet_sender.send_raw_command(
            ipdst=mi_addr,
            ddata=bytes([D0_WR_MODULSPEC_DATA, 0xFB, 0x00]),
            objsource=self._objadr,
            mi=self._mi,
            type8=SEND_AS_IP,
        )
        slots = self._ensure_rf_keys(device)
        device.rf_master_index = None
        for index in range(RF_KEY_COUNT):
            slots[index] = {"code": "", "master": False}
            self._publish_rf_slot(device, index)
        _LOGGER.info("UP-RF %s delete all keys sent", device_id)
        self._schedule_rf_key_list(device_id, (0.8,))

    def _schedule_rf_key_list(
        self,
        device_id: str,
        delays: tuple[float, ...],
        replace: bool = True,
    ) -> None:
        """Read the key list again after the module has stored or cleared a key."""
        existing = self._rf_key_list_tasks.get(device_id)
        if existing is not None and not existing.done():
            if not replace:
                return
            existing.cancel()

        async def _run() -> None:
            try:
                for delay in delays:
                    await asyncio.sleep(delay)
                    await self.async_request_rf_key_list(device_id)
            except asyncio.CancelledError:
                raise

        self._rf_key_list_tasks[device_id] = asyncio.create_task(_run())

    async def async_refresh_rf_key_lists(self) -> None:
        """Read the stored keys of every UP-RF module."""
        if self._packet_sender is None:
            _LOGGER.warning("Cannot refresh RF key lists: not connected")
            return
        for device_id, device in list(self.devices.items()):
            if (
                device.device_type != "rf_reader"
                or not device_id.startswith("MI")
                or device.via_device
            ):
                continue
            await self.async_request_rf_key_list(device_id)
            await asyncio.sleep(0.4)
