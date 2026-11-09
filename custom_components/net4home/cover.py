from datetime import timedelta
import logging
import time
from typing import Callable

from homeassistant import config_entries
from homeassistant.components.cover import ATTR_POSITION, CoverEntity, CoverEntityFeature
from homeassistant.const import STATE_CLOSED, STATE_OPEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import slugify

from .api import Net4HomeApi, Net4HomeDevice
from .const import DOMAIN
from .cover_motion import MOTION_DOWN, MOTION_STOP, MOTION_UP, CoverTravel
from .group_entity import (
    ATTR_GROUPS,
    Net4HomeGroupCover,
    cover_state_signal,
    group_labels,
    listen_group_attribute,
    take_new_groups,
)
from .helpers import bus_connected, ensure_connected, listen_connection, parent_device_link

_LOGGER = logging.getLogger(__name__)

# The actor stops by itself at the end of its run time; allow for bus delay.
END_MARGIN = 0.5
REFRESH_WHILE_MOVING = timedelta(seconds=1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: Callable[[list[CoverEntity], bool], None]
) -> None:
    """Set up net4home cover entities."""
    api: Net4HomeApi = hass.data[DOMAIN][entry.entry_id]

    cover_devices = [d for d in api.devices.values() if d.device_type == "cover"]
    _LOGGER.debug("[Cover] Creating %s cover entities", len(cover_devices))
    async_add_entities([Net4HomeCover(api, entry, device) for device in cover_devices])

    async def async_new_device(device: Net4HomeDevice):
        if device.device_type != "cover":
            return
        async_add_entities([Net4HomeCover(api, entry, device)])

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"net4home_new_device_{entry.entry_id}", async_new_device
        )
    )

    seen_groups: set[int] = set()

    async def async_new_groups(groups):
        fresh = take_new_groups(
            "cover",
            seen_groups,
            groups,
            lambda group: Net4HomeGroupCover(api, entry, group),
        )
        if fresh:
            async_add_entities(fresh)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"net4home_groups_{entry.entry_id}", async_new_groups
        )
    )


class Net4HomeCover(RestoreEntity, CoverEntity):
    """A net4home cover channel.

    The actor reports no position. With a run time configured on the
    channel, the position follows from how long the motor ran.
    """

    _attr_has_entity_name = False
    _attr_assumed_state = True
    _attr_should_poll = False
    _attr_translation_key = "channel"

    def __init__(self, api: Net4HomeApi, entry, device: Net4HomeDevice):
        """Initialize the cover."""
        self.api = api
        self.entry = entry
        self.device = device
        self._attr_name = device.name
        self._travel = CoverTravel()
        self._cancel_end: Callable[[], None] | None = None
        self._cancel_target: Callable[[], None] | None = None
        self._cancel_refresh: Callable[[], None] | None = None
        self._published: bool | None | object = object()

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the entity."""
        via = (self.device.via_device or "unknown").lower()
        return f"{self.entry.entry_id}_{slugify(via)}_{slugify(self.device.device_id)}"

    @property
    def _run_time(self) -> float | None:
        value = getattr(self.device, "timer_time1", None)
        return float(value) if isinstance(value, (int, float)) and value > 0 else None

    @property
    def available(self) -> bool:
        return bus_connected(self.api)

    @property
    def supported_features(self) -> CoverEntityFeature:
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        if self._run_time:
            features |= CoverEntityFeature.SET_POSITION
        return features

    @property
    def current_cover_position(self) -> int | None:
        return self._travel.position_at(time.monotonic(), self._run_time)

    @property
    def is_closed(self) -> bool | None:
        return self._travel.is_closed()

    @property
    def is_opening(self) -> bool:
        return self._travel.motion == MOTION_UP

    @property
    def is_closing(self) -> bool:
        return self._travel.motion == MOTION_DOWN

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id.upper())},
            name=self.device.name,
            manufacturer="net4home",
            model=self.device.model,
            **parent_device_link(self.hass, self.entry.entry_id, self.device.via_device),
        )

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        return {
            "device_id": self.device.device_id,
            "model": self.device.model,
            "via_device": self.device.via_device or "",
            "send_state_changes": bool(getattr(self.device, "send_state_changes", False)),
            ATTR_GROUPS: group_labels(self),
        }

    async def async_added_to_hass(self):
        """Run when entity is added to Home Assistant."""
        last = await self.async_get_last_state()
        if last is not None:
            if last.state in (STATE_OPEN, STATE_CLOSED):
                self._travel.closed = last.state == STATE_CLOSED
                position = last.attributes.get("current_position")
                if isinstance(position, (int, float)):
                    self._travel.position = int(position)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"net4home_update_{self.device.device_id.upper()}",
                self._handle_update,
            )
        )
        self.async_on_remove(self._cancel_timers)
        listen_group_attribute(self)
        listen_connection(self)
        self._publish()

    @callback
    def _handle_update(self, payload) -> None:
        """A run command seen on the bus, or the position reported by the actor."""
        if not isinstance(payload, dict):
            return
        if "position" in payload:
            if self._travel.report(payload["position"], time.monotonic()):
                self._cancel(end=True, target=True, refresh=True)
            self._write()
            return
        if "motion" not in payload:
            return
        motion = payload["motion"]
        if motion != self._travel.motion:
            self._cancel(target=True)
        self._apply(motion)

    @callback
    def _request_position(self) -> None:
        self.hass.async_create_task(self.api.async_request_status(self.device.device_id))

    @callback
    def _apply(self, motion: int) -> None:
        now = time.monotonic()
        run_time = self._run_time
        if not self._travel.start(motion, now, run_time):
            return
        self._cancel(end=True, refresh=True)
        if self._travel.motion != MOTION_STOP and run_time:
            self._cancel_end = async_call_later(
                self.hass, self._seconds_to_end(run_time) + END_MARGIN, self._reached_end
            )
            self._cancel_refresh = async_track_time_interval(
                self.hass, self._refresh, REFRESH_WHILE_MOVING
            )
        self._write()

    def _seconds_to_end(self, run_time: float) -> float:
        position = self._travel.position
        if position is None:
            return run_time
        remaining = 100 - position if self._travel.motion == MOTION_UP else position
        return remaining * run_time / 100.0

    @callback
    def _reached_end(self, _now) -> None:
        self._cancel_end = None
        self._travel.stop(time.monotonic(), self._run_time)
        self._cancel(refresh=True)
        self._write()
        if bus_connected(self.api):
            self._request_position()

    @callback
    def _refresh(self, _now) -> None:
        self.async_write_ha_state()

    @callback
    def _cancel(self, *, end: bool = False, target: bool = False, refresh: bool = False) -> None:
        if end and self._cancel_end:
            self._cancel_end()
            self._cancel_end = None
        if target and self._cancel_target:
            self._cancel_target()
            self._cancel_target = None
        if refresh and self._cancel_refresh:
            self._cancel_refresh()
            self._cancel_refresh = None

    @callback
    def _cancel_timers(self) -> None:
        self._cancel(end=True, target=True, refresh=True)

    @callback
    def _write(self) -> None:
        self.async_write_ha_state()
        self._publish()

    @callback
    def _publish(self) -> None:
        closed = self._travel.is_closed()
        if closed == self._published:
            return
        self._published = closed
        device_id = self.device.device_id.upper()
        self.api.cover_closed[device_id] = closed
        async_dispatcher_send(self.hass, cover_state_signal(device_id), closed)

    async def _command(self, motion: int) -> None:
        ensure_connected(self.api)
        if motion == MOTION_UP:
            await self.api.async_open_cover(self.device.device_id)
        elif motion == MOTION_DOWN:
            await self.api.async_close_cover(self.device.device_id)
        else:
            await self.api.async_stop_cover(self.device.device_id)
        self._apply(motion)

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        self._cancel(target=True)
        await self._command(MOTION_UP)

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        self._cancel(target=True)
        await self._command(MOTION_DOWN)

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        self._cancel(target=True)
        await self._command(MOTION_STOP)

    async def async_set_cover_position(self, **kwargs):
        """Run towards a position and stop after the computed time."""
        target = int(kwargs[ATTR_POSITION])
        run_time = self._run_time
        self._cancel(target=True)
        if target >= 100:
            await self._command(MOTION_UP)
            return
        if target <= 0:
            await self._command(MOTION_DOWN)
            return
        current = self._travel.position_at(time.monotonic(), run_time)
        if run_time is None or current is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="position_unknown",
                translation_placeholders={"name": self.name or self.device.device_id},
            )
        if target == current:
            if self._travel.motion != MOTION_STOP:
                await self._command(MOTION_STOP)
            return
        motion = MOTION_UP if target > current else MOTION_DOWN
        seconds = abs(target - current) * run_time / 100.0
        await self._command(motion)
        self._cancel_target = async_call_later(
            self.hass, seconds, self._target_reached_callback(target)
        )

    def _target_reached_callback(self, target: int):
        async def _reached(_now) -> None:
            self._cancel_target = None
            if self._travel.motion == MOTION_STOP:
                return
            try:
                await self._command(MOTION_STOP)
            except HomeAssistantError:
                _LOGGER.warning("%s: stop at %s%% not sent, bus is down", self.device.device_id, target)
                return
            self._travel.position = target
            self._travel.closed = False
            self._write()
            self._request_position()

        return _reached
