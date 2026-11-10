"""HS-Time commands."""
import asyncio
import logging

from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    D0_ENABLE_CONFIGURATION,
    D0_RD_MODULSPEC_DATA,
    D0_RD_MODULSPEC_DATA_ACK,
    D0_REQ,
    D0_SET,
    D0_VALUE_REQ,
    D1_ENABLE_CONFIGURATION_OK_BYTE,
    SEND_AS_IP,
)
from .hs_time import (
    profile_mask_with,
    schedule_rows_from_lines,
    sun_object_offsets,
)

_LOGGER = logging.getLogger(__name__)

class HsTimeCommands:
    """HS-Time commands."""

    async def _async_query_hs_time(self, device) -> None:
        """Read the clock, the profile mask and today's sunrise and sunset."""
        if (
            self._packet_sender is None
            or device is None
            or not device.objadr
            or device.objadr <= 0
        ):
            return
        await self._packet_sender.send_raw_command(
            ipdst=device.objadr,
            ddata=bytes([D0_VALUE_REQ, 0x00, 0x00]),
            objsource=self._objadr,
            mi=self._mi,
        )
        await asyncio.sleep(0.1)
        await self._packet_sender.send_raw_command(
            ipdst=device.objadr,
            ddata=bytes([D0_REQ, 0x00, 0x00]),
            objsource=self._objadr,
            mi=self._mi,
        )
        sunrise_offset, sunset_offset = sun_object_offsets(
            getattr(device, "sw_version", None),
            getattr(device, "hs_tab_count", None),
        )
        device.hs_sunrise_obj = device.objadr + sunrise_offset
        device.hs_sunset_obj = device.objadr + sunset_offset
        for offset in (sunrise_offset, sunset_offset):
            await asyncio.sleep(0.1)
            await self._packet_sender.send_raw_command(
                ipdst=device.objadr + offset,
                ddata=bytes([D0_VALUE_REQ, 0x00, 0x00]),
                objsource=self._objadr,
                mi=self._mi,
            )

    async def _async_adopt_hs_time_base(
        self,
        device,
        objadr: int,
        *,
        guessed: bool,
        source: str,
    ) -> None:
        """Remember the HS-Time base object and read mask, sunrise and sunset."""
        if device is None or not objadr or objadr <= 0:
            return
        changed = device.objadr != objadr
        device.objadr = objadr
        device.hs_objadr_guessed = guessed
        if changed:
            await self._async_save_objadr(device.device_id, objadr)
            _LOGGER.info(
                "HS-Time %s object %s from %s%s",
                device.device_id,
                objadr,
                source,
                ", guessed from the module number" if guessed else "",
            )
        sunrise_offset, sunset_offset = sun_object_offsets(
            getattr(device, "sw_version", None),
            getattr(device, "hs_tab_count", None),
        )
        device.hs_sunrise_obj = objadr + sunrise_offset
        device.hs_sunset_obj = objadr + sunset_offset
        if changed or getattr(device, "hs_profile_mask", None) is None:
            await self._async_query_hs_time(device)

    async def async_set_hs_time_profile(self, device_id: str, index: int, turn_on: bool) -> None:
        """Turn one of the eight HS-Time profiles on or off."""
        device = self.devices.get(device_id)
        mask = getattr(device, "hs_profile_mask", None) if device else None
        if (
            self._packet_sender is None
            or device is None
            or device.model != "HS-Time"
            or mask is None
            or not device.objadr
            or device.objadr <= 0
        ):
            return
        new_mask = profile_mask_with(int(mask), index, turn_on)
        device.hs_profile_mask = new_mask
        async_dispatcher_send(
            self._hass,
            f"net4home_update_{device.device_id.upper()}_hs_profile",
            new_mask,
        )
        await self._packet_sender.send_raw_command(
            ipdst=device.objadr,
            ddata=bytes([D0_SET, new_mask, 0x00]),
            objsource=self._objadr,
            mi=self._mi,
        )
        await asyncio.sleep(0.3)
        await self._packet_sender.send_raw_command(
            ipdst=device.objadr,
            ddata=bytes([D0_REQ, 0x00, 0x00]),
            objsource=self._objadr,
            mi=self._mi,
        )

    async def async_refresh_hs_time(self, *, include_schedule: bool = True) -> None:
        """Read every HS-Time clock and profile mask, then keep polling."""
        if self._packet_sender is None:
            return
        for device in list(self.devices.values()):
            if device.model != "HS-Time" or not str(device.device_id).startswith("MI"):
                continue
            await self._async_query_hs_time(device)
            await asyncio.sleep(0.2)
            if include_schedule:
                await self._async_load_hs_schedule(device)
        if self._hs_time_poll_task is not None and not self._hs_time_poll_task.done():
            return

        async def _poll() -> None:
            try:
                while True:
                    await asyncio.sleep(60)
                    for item in list(self.devices.values()):
                        if item.model != "HS-Time" or not str(item.device_id).startswith("MI"):
                            continue
                        await self._async_query_hs_time(item)
                        await asyncio.sleep(0.2)
            except asyncio.CancelledError:
                raise

        self._hs_time_poll_task = asyncio.create_task(_poll())

    async def _async_load_hs_schedule(self, device) -> None:
        """Read the switching table once. Empty rows stay out of the result."""
        if self._packet_sender is None or device is None:
            return
        if not str(device.device_id).startswith("MI"):
            return
        if getattr(device, "hs_schedule", None) is not None:
            return
        try:
            mi_addr = int(device.device_id[2:], 16)
        except ValueError:
            return
        count = getattr(device, "hs_tab_count", None)
        if count not in (16, 48):
            sunrise, _sunset = sun_object_offsets(getattr(device, "sw_version", None), None)
            count = 48 if sunrise == 49 else 16
        device.hs_schedule_lines = {}
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
            D0_RD_MODULSPEC_DATA,
            D0_RD_MODULSPEC_DATA_ACK,
            count,
            "HS-Time",
        )
        rows = schedule_rows_from_lines(
            device.hs_schedule_lines,
            count,
            device.objadr if device.objadr and device.objadr > 0 else None,
        )
        device.hs_schedule = rows
        _LOGGER.info(
            "HS-Time %s schedule: %s rows from %s of %s lines",
            device.device_id,
            len(rows),
            len(device.hs_schedule_lines),
            count,
        )
        for row in rows:
            _LOGGER.debug(
                "HS-Time %s #%s %s %s %s adr %s cmd %s profile %s",
                device.device_id,
                row["nr"],
                row["mode"],
                row["time"],
                row["weekdays"],
                row["address"],
                "".join(f"{byte:02X}" for byte in row["command"]),
                row["profiles"],
            )
        async_dispatcher_send(
            self._hass,
            f"net4home_update_{device.device_id.upper()}_hs_schedule",
            rows,
        )
