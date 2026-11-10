"""HS-Safety commands."""
import asyncio
import logging

from homeassistant.helpers.dispatcher import async_dispatcher_send

from .alarm_layout import (
    ALARM_SET_VALUES,
    alarm_log_from_lines,
    ensure_alarm_runtime,
)
from .const import (
    D0_ENABLE_CONFIGURATION,
    D0_RD_MODULSPEC_DATA,
    D0_RD_MODULSPEC_DATA_ACK,
    D0_REQ,
    D0_SET,
    D1_ENABLE_CONFIGURATION_OK_BYTE,
    SEND_AS_IP,
)

_LOGGER = logging.getLogger(__name__)

class AlarmCommands:
    """HS-Safety commands."""

    def _alarm_from_sensor_ack(self, paket):
        """Return the HS-Safety module this status belongs to.

        A zone reply keeps its own object address, so it stays a binary
        sensor. The arming status uses the module base address.
        """
        sender_id = f"MI{paket.ipsrc:04X}"
        for candidate in self.devices.values():
            if candidate.model != "HS-Safety":
                continue
            if candidate.objadr and candidate.objadr == paket.objsrc:
                return candidate
            if candidate.device_id == sender_id and not paket.objsrc:
                return candidate
        return None

    async def _async_load_alarm_base(self, device) -> None:
        """Read EE_LC_ADR from modulspec line 0."""
        if self._packet_sender is None or not device.device_id.startswith("MI"):
            return
        try:
            mi_addr = int(device.device_id[2:], 16)
        except ValueError:
            return
        previous = device.objadr if device.objadr and device.objadr > 0 else None
        device.objadr = None
        for attempt in (1, 2):
            await self._packet_sender.send_raw_command(
                ipdst=mi_addr,
                ddata=bytes([D0_ENABLE_CONFIGURATION, D1_ENABLE_CONFIGURATION_OK_BYTE]),
                objsource=self._objadr,
                mi=self._mi,
                type8=SEND_AS_IP,
            )
            await asyncio.sleep(0.2)
            await self._packet_sender.send_raw_command(
                ipdst=mi_addr,
                ddata=bytes([D0_RD_MODULSPEC_DATA, 0x00]),
                objsource=self._objadr,
                mi=self._mi,
                type8=SEND_AS_IP,
            )
            for _ in range(40):
                if device.objadr and device.objadr > 0:
                    return
                await asyncio.sleep(0.05)
            _LOGGER.debug(
                "HS-Safety %s base address no answer (attempt %s)",
                device.device_id,
                attempt,
            )
        for _ in range(20):
            if device.objadr and device.objadr > 0:
                _LOGGER.info(
                    "HS-Safety %s base address %s arrived late",
                    device.device_id,
                    device.objadr,
                )
                return
            await asyncio.sleep(0.5)
        if previous:
            device.objadr = previous
            _LOGGER.warning(
                "HS-Safety %s did not answer the base address, keeping %s",
                device.device_id,
                previous,
            )
            return
        _LOGGER.warning(
            "HS-Safety %s did not answer the base address",
            device.device_id,
        )

    async def _async_request_alarm_status(self, device_id: str) -> None:
        """Ask an HS-Safety module for its current arming level."""
        device = self.devices.get(device_id)
        if (
            self._packet_sender is None
            or device is None
            or not device.objadr
            or device.objadr <= 0
        ):
            return
        await self._packet_sender.send_raw_command(
            ipdst=device.objadr,
            ddata=bytes([D0_REQ, 0x00, 0x00]),
            objsource=self._objadr,
            mi=self._mi,
        )

    def _schedule_alarm_poll(self, device_id: str) -> None:
        """Read the status again while an arming check can still be running."""
        existing = self._alarm_poll_tasks.get(device_id)
        if existing is not None and not existing.done():
            existing.cancel()

        async def _poll() -> None:
            try:
                for delay in (0.3, 1.2, 2.5):
                    await asyncio.sleep(delay)
                    await self._async_request_alarm_status(device_id)
            except asyncio.CancelledError:
                raise

        self._alarm_poll_tasks[device_id] = asyncio.create_task(_poll())

    async def async_refresh_alarm_panels(self) -> None:
        """Load a missing base address and request the current alarm status."""
        if self._packet_sender is None:
            _LOGGER.warning("Cannot refresh alarm panels: not connected")
            return
        for device_id, device in list(self.devices.items()):
            if device.model != "HS-Safety" or not device_id.startswith("MI"):
                continue
            await self._async_load_alarm_base(device)
            await self._async_request_alarm_status(device_id)
            await self.async_load_alarm_triggers(device)
            await asyncio.sleep(0.2)

    async def async_load_alarm_triggers(self, device) -> None:
        """Read the Tab1 trigger list: contact address, level flags and name.

        First the module info (index $FF) gives the table lengths, then the
        trigger lines follow the Tab0 lines. Read only, nothing is written.
        """
        if self._packet_sender is None or device is None:
            return
        if not str(device.device_id).startswith("MI"):
            return
        ensure_alarm_runtime(device)
        async with self._alarm_config_lock(device.device_id):
            try:
                mi_addr = int(device.device_id[2:], 16)
            except ValueError:
                return
            device.alarm_tab_counts = None
            await self._packet_sender.send_raw_command(
                ipdst=mi_addr,
                ddata=bytes([D0_ENABLE_CONFIGURATION, D1_ENABLE_CONFIGURATION_OK_BYTE]),
                objsource=self._objadr,
                mi=self._mi,
                type8=SEND_AS_IP,
            )
            await asyncio.sleep(0.2)
            for attempt in (1, 2):
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
                        break
                    except TimeoutError:
                        _LOGGER.info(
                            "HS-Safety %s module info no answer (attempt %s)",
                            device.device_id,
                            attempt,
                        )
                finally:
                    current = self._line_reads.get((mi_addr, D0_RD_MODULSPEC_DATA_ACK))
                    if current and current["event"] is event:
                        self._line_reads.pop((mi_addr, D0_RD_MODULSPEC_DATA_ACK), None)
            else:
                # A busy bus can deliver the info reply well after the 2s wait.
                for _ in range(60):
                    if device.alarm_tab_counts:
                        break
                    await asyncio.sleep(0.5)
                if not device.alarm_tab_counts:
                    _LOGGER.warning("HS-Safety %s module info did not answer", device.device_id)
                    return
                _LOGGER.info("HS-Safety %s module info arrived late", device.device_id)

            counts = device.alarm_tab_counts
            device.alarm_triggers = {}
            if not counts or counts.tab1 <= 0:
                _LOGGER.info("HS-Safety %s has no trigger table", device.device_id)
            else:
                await self._async_read_table_lines(
                    mi_addr,
                    D0_RD_MODULSPEC_DATA,
                    D0_RD_MODULSPEC_DATA_ACK,
                    counts.tab1,
                    "HS-Safety trigger",
                    start=counts.tab0,
                )
                names = ", ".join(
                    f"{trigger['index'] + 1}:{trigger['name'] or '-'} @{trigger['address']} {trigger['levels']}"
                    for trigger in sorted(device.alarm_triggers.values(), key=lambda t: t["index"])
                )
                _LOGGER.info(
                    "HS-Safety %s triggers: %s of %s lines",
                    device.device_id,
                    len(device.alarm_triggers),
                    counts.tab1,
                )
                _LOGGER.debug(
                    "HS-Safety %s trigger lines: %s",
                    device.device_id,
                    names or "keine",
                )
                async_dispatcher_send(
                    self._hass, f"net4home_alarm_{device.device_id.upper()}", "triggers"
                )
                await self._async_request_alarm_contacts(device)
            await self._async_read_alarm_log(device)

    def _alarm_config_lock(self, device_id: str) -> asyncio.Lock:
        """One modulspec read per panel. A second read would steal the replies."""
        lock = self._alarm_config_locks.get(device_id)
        if lock is None:
            lock = asyncio.Lock()
            self._alarm_config_locks[device_id] = lock
        return lock

    def _schedule_alarm_log(self, device) -> None:
        """Read the protocol again after the arming level changed."""
        self._alarm_log_pending.add(device.device_id)
        key = f"log:{device.device_id}"
        existing = self._alarm_poll_tasks.get(key)
        if existing is not None and not existing.done():
            return

        async def _read() -> None:
            try:
                while True:
                    self._alarm_log_pending.discard(device.device_id)
                    async with self._alarm_config_lock(device.device_id):
                        await self._async_read_alarm_log(device)
                    if device.device_id not in self._alarm_log_pending:
                        break
            except Exception:
                _LOGGER.exception("HS-Safety %s protocol read failed", device.device_id)

        self._alarm_poll_tasks[key] = asyncio.create_task(_read())

    async def _async_read_alarm_log(self, device) -> None:
        """Read Tab4, the protocol, and publish it to the dashboard sensor."""
        if self._packet_sender is None or device is None:
            return
        if not str(device.device_id).startswith("MI"):
            return
        ensure_alarm_runtime(device)
        counts = device.alarm_tab_counts
        if not counts or counts.log_lines <= 0:
            device.alarm_log = []
            async_dispatcher_send(
                self._hass, f"net4home_alarm_{device.device_id.upper()}", "log"
            )
            return
        try:
            mi_addr = int(device.device_id[2:], 16)
        except ValueError:
            return
        device.alarm_log_lines = {}
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
            counts.log_lines,
            "HS-Safety protocol",
            start=counts.log_start,
        )
        device.alarm_log = alarm_log_from_lines(
            device.alarm_log_lines,
            counts,
            device.alarm_triggers,
        )
        _LOGGER.info(
            "HS-Safety %s protocol: %s entries",
            device.device_id,
            len(device.alarm_log),
        )
        if device.alarm_log:
            _LOGGER.debug(
                "HS-Safety %s newest protocol line: %s",
                device.device_id,
                device.alarm_log[0]["line"],
            )
        async_dispatcher_send(
            self._hass, f"net4home_alarm_{device.device_id.upper()}", "log"
        )

    async def _async_request_alarm_contacts(self, device) -> None:
        """Ask every monitored contact for its state (D0_REQ to its address)."""
        if self._packet_sender is None or device is None:
            return
        for trigger in list(device.alarm_triggers.values()):
            await self._packet_sender.send_raw_command(
                ipdst=trigger["address"],
                ddata=bytes([D0_REQ, 0x00, 0x00]),
                objsource=self._objadr,
                mi=self._mi,
            )
            await asyncio.sleep(0.05)

    def _alarm_contact_owner(self, objsrc: int):
        """Return the HS-Safety module that monitors this contact address."""
        if not objsrc:
            return None
        for candidate in self.devices.values():
            if candidate.model != "HS-Safety":
                continue
            for trigger in (getattr(candidate, "alarm_triggers", None) or {}).values():
                if trigger["address"] == objsrc:
                    return candidate
        return None

    async def async_set_alarm_state(self, device_id: str, mode: int):
        """Set the HS-Safety arming level.

        mode 0 disarms. 11, 12 and 13 arm Intern 1, Intern 2 and Extern
        after the module has checked that every contact is closed.
        The card state follows the status reply, not this call.
        """
        try:
            device = self.devices.get(device_id)
            if not device:
                _LOGGER.warning(f"Device {device_id} not found for alarm control")
                return
            if self._packet_sender is None:
                _LOGGER.warning(f"Cannot set alarm state for {device_id}: not connected")
                return
            if mode not in ALARM_SET_VALUES:
                _LOGGER.warning(f"Invalid alarm mode: {mode}")
                return
            if not device.objadr or device.objadr <= 0:
                await self._async_load_alarm_base(device)
            objadr = device.objadr
            if not objadr or objadr <= 0:
                _LOGGER.warning(
                    "No base object address (EE_LC_ADR) for alarm %s",
                    device_id,
                )
                return

            await self._packet_sender.send_raw_command(
                ipdst=objadr,
                ddata=bytes([D0_SET, mode, 0x00]),
                objsource=self._objadr,
                mi=self._mi,
            )
            _LOGGER.info(
                "HS-Safety %s command %s sent to object %s",
                device_id,
                mode,
                objadr,
            )
            self._schedule_alarm_poll(device_id)

        except Exception as e:
            _LOGGER.error(f"Error setting alarm state for {device_id}: {e}", exc_info=True)
