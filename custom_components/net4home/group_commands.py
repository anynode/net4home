"""Group table reads and group commands."""
import asyncio
import logging

from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    D0_ENABLE_CONFIGURATION,
    D0_RD_GRP_DATA,
    D0_RD_GRP_DATA_ACK,
    D0_SET,
    D1_ENABLE_CONFIGURATION_OK_BYTE,
    SEND_AS_IP,
)
from .cover_motion import (
    MOTION_DOWN,
    MOTION_STOP,
    MOTION_UP,
)
from .groups import (
    index_groups,
    parse_group_line,
)

_LOGGER = logging.getLogger(__name__)

class GroupCommands:
    """Group table reads and group commands."""

    async def async_set_group(self, address: int, value: int) -> None:
        """Send one D0_SET to a group address. Every member applies it."""
        if self._packet_sender is None:
            return
        await self._packet_sender.send_raw_command(
            ipdst=address,
            ddata=bytes([D0_SET, value & 0xFF, 0x00]),
            objsource=self._objadr,
            mi=self._mi,
        )
        _LOGGER.info("Group %s command %s", address & 0x7FFF, value & 0xFF)
        self._dispatch_cover_motion(address, value & 0xFF)

    def _dispatch_cover_motion(self, address: int, value: int) -> None:
        """Tell covers that a run command went to their address or group."""
        if value not in (MOTION_STOP, MOTION_DOWN, MOTION_UP):
            return
        targets = {
            device.device_id
            for device in self.devices.values()
            if device.device_type == "cover" and device.objadr == address
        }
        for group in self.groups:
            if group.get("address") != address:
                continue
            targets.update(
                member["device_id"]
                for member in group.get("members", [])
                if member.get("device_id") and member.get("device_type") == "cover"
            )
        for device_id in targets:
            async_dispatcher_send(
                self._hass, f"net4home_update_{device_id.upper()}", {"motion": value}
            )

    async def _async_read_group_lines(self, mi_addr: int, count: int) -> None:
        """Read every line of one group table.

        An empty slot still answers. A missing reply is one lost line, not
        the end of the table, so the read continues through the capacity.
        """
        missed = []
        for channel in range(count):
            if not await self._async_read_one_group_line(mi_addr, channel):
                missed.append(channel)
        if missed:
            await asyncio.sleep(1.0)
            still = []
            for channel in missed:
                if not await self._async_read_one_group_line(mi_addr, channel):
                    still.append(channel)
            missed = still
        if missed:
            _LOGGER.warning(
                "MI%04X group table missed lines %s of %s",
                mi_addr,
                ", ".join(str(channel) for channel in missed),
                count,
            )

    async def _async_read_one_group_line(self, mi_addr: int, channel: int) -> bool:
        """Read one group-table line. A lost first request is repeated once."""
        for attempt in (1, 2):
            event = self._expect_line_read(mi_addr, D0_RD_GRP_DATA_ACK, channel)
            try:
                await self._packet_sender.send_raw_command(
                    ipdst=mi_addr,
                    ddata=bytes([D0_RD_GRP_DATA, channel, 0x00]),
                    objsource=self._objadr,
                    mi=self._mi,
                    type8=SEND_AS_IP,
                )
                try:
                    await asyncio.wait_for(event.wait(), timeout=2.0)
                    return True
                except TimeoutError:
                    _LOGGER.debug(
                        "Gruppe line %s from MI%04X no answer within 2s (attempt %s)",
                        channel,
                        mi_addr,
                        attempt,
                    )
            finally:
                current = self._line_reads.get((mi_addr, D0_RD_GRP_DATA_ACK))
                if current and current["event"] is event:
                    self._line_reads.pop((mi_addr, D0_RD_GRP_DATA_ACK), None)
        return False

    def _drop_stored_group_names(self) -> None:
        """Remove a name list that was written into the config entry by mistake."""
        if self._entry is None or "group_names" not in self._entry.options:
            return
        options = dict(self._entry.options)
        options.pop("group_names", None)
        self._hass.config_entries.async_update_entry(self._entry, options=options)

    def _save_groups(self, groups: list) -> None:
        """Keep the last group index so a later start can skip the bus read."""
        if self._entry is None:
            return
        stored = []
        for group in groups:
            stored.append(
                {
                    "address": group["address"],
                    "number": group["number"],
                    "label": group["label"],
                    "name": group["name"],
                    "kind": group["kind"],
                    "members": [
                        {
                            "module": member.get("module"),
                            "channel": member.get("channel"),
                            "device_id": member.get("device_id"),
                            "name": member.get("name"),
                            "device_type": member.get("device_type"),
                        }
                        for member in group.get("members", [])
                    ],
                }
            )
        options = dict(self._entry.options)
        options["groups"] = stored
        self._hass.config_entries.async_update_entry(self._entry, options=options)

    def _publish_stored_groups(self) -> None:
        """Rebuild group entities from the last read, without asking the bus."""
        stored = []
        if self._entry is not None:
            stored = list(self._entry.options.get("groups") or [])
        self.groups = stored
        if not stored:
            _LOGGER.info("Group read on startup is off and no groups are stored yet")
            return
        _LOGGER.info("Using %s stored groups, bus tables were not read", len(stored))
        async_dispatcher_send(
            self._hass,
            f"net4home_groups_{self._entry_id}",
            self.groups,
        )

    async def async_load_groups(self) -> None:
        """Read every switching module's group table and publish the groups."""
        if self._groups_loaded:
            return
        self._groups_loaded = True
        self._drop_stored_group_names()
        if not self.read_groups_on_startup:
            self._publish_stored_groups()
            await self._async_request_group_member_status()
            return
        if self._packet_sender is None:
            return
        modules = []
        for device in self.devices.values():
            if device.via_device or not str(device.device_id).startswith("MI"):
                continue
            ng = device.ng
            if not isinstance(ng, int) or ng <= 0 or ng == 0xFF:
                continue
            modules.append(device)
        _LOGGER.info("Reading group tables of %s modules", len(modules))
        lines_by_module = {}
        for device in modules:
            try:
                mi_addr = int(device.device_id[2:], 16)
            except ValueError:
                continue
            device.group_lines = {}
            await self._packet_sender.send_raw_command(
                ipdst=mi_addr,
                ddata=bytes([D0_ENABLE_CONFIGURATION, D1_ENABLE_CONFIGURATION_OK_BYTE]),
                objsource=self._objadr,
                mi=self._mi,
                type8=SEND_AS_IP,
            )
            await asyncio.sleep(0.2)
            await self._async_read_group_lines(mi_addr, device.ng)
            lines_by_module[device.device_id] = dict(device.group_lines)
            used = sum(
                1
                for payload in device.group_lines.values()
                if parse_group_line(payload) is not None
            )
            _LOGGER.info(
                "%s group table: %s used of %s lines",
                device.device_id,
                used,
                device.ng,
            )
        self.groups = index_groups(lines_by_module, self.devices)
        self._save_groups(self.groups)
        for group in self.groups:
            _LOGGER.info(
                "Group %s %s: %s",
                group["label"],
                group["kind"],
                ", ".join(member["name"] for member in group["members"]),
            )
        async_dispatcher_send(
            self._hass,
            f"net4home_groups_{self._entry_id}",
            self.groups,
        )
        await self._async_request_group_member_status()

    async def _async_request_group_member_status(self) -> None:
        """Ask each member once so a restored group shows a state."""
        if self._packet_sender is None or not self.groups:
            return
        await asyncio.sleep(1)
        asked = set()
        for group in self.groups:
            for member in group["members"]:
                device_id = member.get("device_id")
                if not device_id or device_id in asked:
                    continue
                asked.add(device_id)
                await self.async_request_status(device_id)
                await asyncio.sleep(0.05)
