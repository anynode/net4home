"""SI energy module commands."""
import asyncio
import logging

from .const import (
    D0_ENABLE_CONFIGURATION,
    D0_RD_MODULSPEC_DATA,
    D0_RD_MODULSPEC_DATA_ACK,
    D0_REQ,
    D1_ENABLE_CONFIGURATION_OK_BYTE,
    SEND_AS_IP,
)
from .si_layout import (
    SI_MODEL_CHANNELS,
    ensure_si_runtime,
    si_channel_for_objadr,
    si_channel_objects,
)

_LOGGER = logging.getLogger(__name__)

class SiCommands:
    """SI energy module commands."""

    def _si_channel_owner(self, objsrc: int):
        """Return (UP-SI / HS-SI6 module, channel) that owns this object address."""
        if not objsrc:
            return None
        for candidate in self.devices.values():
            info = getattr(candidate, "si_info", None)
            if info is None:
                continue
            channel = si_channel_for_objadr(info, objsrc)
            if channel is not None:
                return candidate, channel
        return None

    async def async_request_si_power(self, device_id: str) -> None:
        """Ask every channel object of a UP-SI / HS-SI6 for its current power."""
        device = self.devices.get(device_id)
        info = getattr(device, "si_info", None)
        if self._packet_sender is None or info is None:
            return
        for objadr in si_channel_objects(info):
            await self._packet_sender.send_raw_command(
                ipdst=objadr,
                ddata=bytes([D0_REQ, 0x00, 0x00]),
                objsource=self._objadr,
                mi=self._mi,
            )

    async def async_load_si_entries(self, device) -> None:
        """Read module info (index $FF) and all threshold lines. Read only, once at startup."""
        if self._packet_sender is None or device is None:
            return
        if not str(device.device_id).startswith("MI"):
            return
        ensure_si_runtime(device)
        try:
            mi_addr = int(device.device_id[2:], 16)
        except ValueError:
            return
        device.si_info = None
        device.si_entries = {}
        await self._packet_sender.send_raw_command(
            ipdst=mi_addr,
            ddata=bytes([D0_ENABLE_CONFIGURATION, D1_ENABLE_CONFIGURATION_OK_BYTE]),
            objsource=self._objadr,
            mi=self._mi,
            type8=SEND_AS_IP,
        )
        await asyncio.sleep(0.2)
        event = self._expect_line_read(mi_addr, D0_RD_MODULSPEC_DATA_ACK, 0xFF)
        try:
            await self._packet_sender.send_raw_command(
                ipdst=mi_addr,
                ddata=bytes([D0_RD_MODULSPEC_DATA, 0xFF]),
                objsource=self._objadr,
                mi=self._mi,
                type8=SEND_AS_IP,
            )
            try:
                await asyncio.wait_for(event.wait(), timeout=2.0)
            except TimeoutError:
                _LOGGER.warning("%s %s module info did not answer", device.model, device.device_id)
                return
        finally:
            current = self._line_reads.get((mi_addr, D0_RD_MODULSPEC_DATA_ACK))
            if current and current["event"] is event:
                self._line_reads.pop((mi_addr, D0_RD_MODULSPEC_DATA_ACK), None)

        info = device.si_info
        if info is None:
            return
        await self._async_read_table_lines(
            mi_addr,
            D0_RD_MODULSPEC_DATA,
            D0_RD_MODULSPEC_DATA_ACK,
            info.lines,
            f"{device.model} threshold",
        )

    async def async_refresh_si_modules(self) -> None:
        """Startup: load info and thresholds of every UP-SI / HS-SI6. No polling afterwards."""
        if self._packet_sender is None:
            _LOGGER.warning("Cannot refresh SI modules: not connected")
            return
        for device_id, device in list(self.devices.items()):
            if device.model not in SI_MODEL_CHANNELS or not device_id.startswith("MI"):
                continue
            await self.async_load_si_entries(device)
            await asyncio.sleep(0.2)
