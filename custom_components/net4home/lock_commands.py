"""EXT-LD motor lock commands."""
import asyncio
import logging

from homeassistant.exceptions import HomeAssistantError

from .const import (
    D0_RD_MODULSPEC_DATA,
    D0_REQ,
    D0_SET,
    SEND_AS_IP,
)
from .ext_ld_layout import (
    EXT_LD_LOCK_VALUE,
    EXT_LD_UNLOCK_BUZZ_VALUE,
    EXT_LD_UNLOCK_VALUE,
)

_LOGGER = logging.getLogger(__name__)

class LockCommands:
    """EXT-LD motor lock commands."""

    async def _async_load_ext_ld_base(self, device) -> None:
        """Read EE_ADR_LOCAL_ADR (base object) from EXT-LD modulspec line 0 if still unknown."""
        if device.objadr and device.objadr > 0:
            return
        if self._packet_sender is None or not device.device_id.startswith("MI"):
            return
        try:
            mi_addr = int(device.device_id[2:], 16)
        except ValueError:
            return
        await self._packet_sender.send_raw_command(
            ipdst=mi_addr,
            ddata=bytes([D0_RD_MODULSPEC_DATA, 0x00, 0x00]),
            objsource=self._objadr,
            mi=self._mi,
            type8=SEND_AS_IP,
        )
        for _ in range(40):
            if device.objadr and device.objadr > 0:
                return
            await asyncio.sleep(0.05)
        _LOGGER.warning("EXT-LD %s base address was not in modulspec line 0", device.device_id)

    async def async_request_ext_ld_status(self, device_id: str) -> None:
        """Ask an EXT-LD module for its status (D0_REQ to the base object, answer D0_ACTOR_ACK)."""
        device = self.devices.get(device_id)
        if device is None or self._packet_sender is None:
            return
        if not device.objadr or device.objadr <= 0:
            await self._async_load_ext_ld_base(device)
        if not device.objadr or device.objadr <= 0:
            return
        await self._packet_sender.send_raw_command(
            ipdst=device.objadr,
            ddata=bytes([D0_REQ, 0x00, 0x00]),
            objsource=self._objadr,
            mi=self._mi,
        )

    async def async_refresh_ext_ld_locks(self) -> None:
        """Read the base address and the status of every EXT-LD lock after startup."""
        for device_id, device in list(self.devices.items()):
            if device.device_type != "lock" or not device_id.startswith("MI"):
                continue
            await self._async_load_ext_ld_base(device)
            await self.async_request_ext_ld_status(device_id)
            await asyncio.sleep(0.2)

    async def async_set_ext_ld_lock(self, device_id: str, locked: bool) -> None:
        """Lock (D0_SET 1) or unlock (D0_SET 3) an EXT-LD motor lock.

        The status is read again shortly after the command, so the entity follows
        the module's answer and not this call.
        """
        value = EXT_LD_LOCK_VALUE if locked else EXT_LD_UNLOCK_VALUE
        await self.async_send_ext_ld_command(
            device_id,
            value,
            "verriegeln" if locked else "entriegeln",
        )

    async def async_unlock_ext_ld_buzz(self, device_id: str) -> None:
        """Unlock and buzz (D0_SET 4, "Entriegeln und Summen") an EXT-LD motor lock."""
        await self.async_send_ext_ld_command(
            device_id,
            EXT_LD_UNLOCK_BUZZ_VALUE,
            "entriegeln und summen",
        )

    async def async_send_ext_ld_command(self, device_id: str, value: int, label: str) -> None:
        """Send one D0_SET value to the EXT-LD base object and poll the status."""
        device = self.devices.get(device_id)
        if device is None or device.device_type != "lock":
            _LOGGER.warning("No EXT-LD lock %s", device_id)
            return
        if self._packet_sender is None:
            _LOGGER.warning("Cannot switch EXT-LD %s: not connected", device_id)
            return
        if not device.objadr or device.objadr <= 0:
            await self._async_load_ext_ld_base(device)
        objadr = device.objadr
        if not objadr or objadr <= 0:
            raise HomeAssistantError(f"EXT-LD {device_id}: base address is not known yet")

        await self._packet_sender.send_raw_command(
            ipdst=objadr,
            ddata=bytes([D0_SET, value, 0x00]),
            objsource=self._objadr,
            mi=self._mi,
        )
        _LOGGER.info(
            "EXT-LD %s %s sent to object %s",
            device_id,
            label,
            objadr,
        )

        async def _poll() -> None:
            for delay in (0.5, 2.0):
                await asyncio.sleep(delay)
                await self.async_request_ext_ld_status(device_id)

        self._hass.async_create_task(_poll())
