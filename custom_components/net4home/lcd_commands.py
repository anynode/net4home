"""UP-LCD commands."""
import asyncio
import logging

from .const import (
    D0_ENABLE_CONFIGURATION,
    D0_RD_MODULSPEC_DATA,
    D0_RD_MODULSPEC_DATA_ACK,
    D1_ENABLE_CONFIGURATION_OK_BYTE,
    SEND_AS_IP,
    SEND_AS_OBJ_GRP,
)
from .lcd_layout import (
    lcd_ok_key,
    lcd_text_command,
)

_LOGGER = logging.getLogger(__name__)

class LcdCommands:
    """UP-LCD commands."""

    async def async_ensure_lcd_address(self, device) -> int | None:
        """Read UP-LCD line 0 when the object address is not stored yet."""
        if device.objadr and device.objadr > 0:
            return device.objadr
        if self._packet_sender is None or not str(device.device_id).startswith("MI"):
            return None
        try:
            mi_addr = int(device.device_id[2:], 16)
        except ValueError:
            return None
        for attempt in (1, 2):
            device.lcd_modulspec_raw = None
            await self._packet_sender.send_raw_command(
                ipdst=mi_addr,
                ddata=bytes([D0_ENABLE_CONFIGURATION, D1_ENABLE_CONFIGURATION_OK_BYTE]),
                objsource=self._objadr,
                mi=self._mi,
                type8=SEND_AS_IP,
            )
            await asyncio.sleep(0.1)
            event = self._expect_line_read(mi_addr, D0_RD_MODULSPEC_DATA_ACK, 0)
            try:
                await self._packet_sender.send_raw_command(
                    ipdst=mi_addr,
                    ddata=bytes([D0_RD_MODULSPEC_DATA, 0x00, 0x00]),
                    objsource=self._objadr,
                    mi=self._mi,
                    type8=SEND_AS_IP,
                )
                try:
                    await asyncio.wait_for(event.wait(), timeout=2.0)
                except TimeoutError:
                    _LOGGER.warning(
                        "UP-LCD %s line 0 no answer (attempt %s), last reply %s",
                        device.device_id,
                        attempt,
                        getattr(device, "lcd_modulspec_raw", None),
                    )
            finally:
                current = self._line_reads.get((mi_addr, D0_RD_MODULSPEC_DATA_ACK))
                if current and current["event"] is event:
                    self._line_reads.pop((mi_addr, D0_RD_MODULSPEC_DATA_ACK), None)
            if device.objadr and device.objadr > 0:
                return device.objadr
        return None

    async def async_send_lcd_text(self, device_id: str, message: str = "", **options) -> bool:
        """Show a free text on an UP-LCD. Options match the configurator dialog."""
        try:
            device = self.devices.get(device_id)
            if not device:
                _LOGGER.warning("No device with ID %s found", device_id)
                return False
            objadr = await self.async_ensure_lcd_address(device)
            if not objadr:
                _LOGGER.warning(
                    "UP-LCD %s has no object address, text was not sent",
                    device_id,
                )
                return False
            packet = lcd_text_command(message, **options)
            await self._packet_sender.send_raw_command(
                ipdst=objadr,
                ddata=packet,
                objsource=self._objadr,
                mi=self._mi,
                type8=SEND_AS_OBJ_GRP,
            )
            _LOGGER.info(
                "UP-LCD %s text to object %s (%s bytes): %s",
                device_id,
                objadr,
                len(packet),
                message,
            )
            return True
        except Exception as e:
            _LOGGER.error("Error sending LCD text for %s: %s", device_id, e)
            return False

    async def async_acknowledge_lcd(self, device_id: str) -> bool:
        """Stop blink with clear, then press OK so the buzzer ends."""
        cleared = await self.async_send_lcd_text(
            device_id,
            "",
            light=False,
            light_long=False,
            blink=False,
            buzzer=False,
            clear=True,
        )
        device = self.devices.get(device_id)
        objadr = device.objadr if device and device.objadr and device.objadr > 0 else None
        if not objadr or self._packet_sender is None:
            return cleared
        try:
            await self._packet_sender.send_raw_command(
                ipdst=objadr,
                ddata=lcd_ok_key(),
                objsource=self._objadr,
                mi=self._mi,
                type8=SEND_AS_OBJ_GRP,
            )
            _LOGGER.info("UP-LCD %s OK key to object %s", device_id, objadr)
            return True
        except Exception as e:
            _LOGGER.error("Error sending LCD OK key for %s: %s", device_id, e)
            return False
