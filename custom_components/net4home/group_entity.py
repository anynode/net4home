"""One Home Assistant entity per bus group address.

Turning it on sends a single command to the group address. Every module
that listed the address applies it to its own channel.
"""

from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .cover_motion import MOTION_DOWN, MOTION_STOP, MOTION_UP
from .groups import groups_for_device
from .helpers import bus_connected, ensure_connected, listen_connection, registry_device_id

ATTR_GROUPS = "groups"
ATTR_ADDRESS = "address"
ATTR_MEMBERS = "members"


def cover_state_signal(device_id: str) -> str:
    """Sent by a cover channel after its open/closed state changed."""
    return f"net4home_cover_state_{device_id.upper()}"


def listen_group_attribute(entity) -> None:
    """Refresh a channel entity once the group tables have been read."""

    @callback
    def _groups_read(_groups) -> None:
        entity.async_write_ha_state()

    entity.async_on_remove(
        async_dispatcher_connect(
            entity.hass,
            f"net4home_groups_{entity.entry.entry_id}",
            _groups_read,
        )
    )


def group_labels(entity) -> str:
    """Names of the groups this channel belongs to.

    A name set on the group entity in Home Assistant wins. Otherwise the
    address is shown, for example G510.
    """
    found = groups_for_device(getattr(entity.api, "groups", []), entity.device.device_id)
    registry = er.async_get(entity.hass) if getattr(entity, "hass", None) else None
    names = []
    for group in found:
        names.append(_group_name(entity, group, registry))
    return ", ".join(names)


def _group_name(entity, group: dict, registry) -> str:
    if registry is None:
        return group["label"]
    unique_id = f"{entity.entry.entry_id}_gruppe_{group['number']}"
    for domain in ("light", "switch", "cover"):
        entity_id = registry.async_get_entity_id(domain, DOMAIN, unique_id)
        if not entity_id:
            continue
        registered = registry.async_get(entity_id)
        if registered is None:
            continue
        return registered.name or registered.original_name or group["label"]
    return group["label"]


def _member_channel_name(hass, entry_id: str, member: dict) -> str:
    """The channel's own name, as shown on its entity, e.g. Jalousie links.

    Falls back to the actor device name (CH1_32001) if no entity is found.
    """
    fallback = member.get("name") or member.get("device_id") or ""
    if hass is None or not member.get("device_id"):
        return fallback
    device_registry_id = registry_device_id(hass, entry_id, member["device_id"])
    if not device_registry_id:
        return fallback
    registry = er.async_get(hass)
    for registered in er.async_entries_for_device(registry, device_registry_id):
        if registered.disabled_by or registered.domain not in ("cover", "light", "switch", "lock"):
            continue
        return registered.name or registered.original_name or fallback
    return fallback


def take_new_groups(kind: str, seen: set, groups, factory) -> list:
    """Build entities for group addresses this platform has not added yet."""
    fresh = []
    for group in groups or []:
        if group.get("kind") != kind or group["address"] in seen:
            continue
        seen.add(group["address"])
        fresh.append(factory(group))
    return fresh


class _GroupMembers:
    """Shared state and device card for a group entity."""

    _attr_should_poll = False
    _attr_translation_key = "group"

    def __init__(self, api, entry, group: dict):
        self.api = api
        self.entry = entry
        self._group = group
        self._attr_name = group["name"]
        self._attr_has_entity_name = False
        self._attr_assumed_state = True
        self._reported: dict[str, bool] = {}
        self._brightness: dict[str, int] = {}

    @property
    def unique_id(self) -> str:
        return f"{self.entry.entry_id}_gruppe_{self._group['number']}"

    @property
    def available(self) -> bool:
        return bus_connected(self.api)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.entry.entry_id}_gruppen")},
            name="Gruppen",
            manufacturer="net4home",
            model="Schaltgruppe",
        )

    @property
    def extra_state_attributes(self) -> dict:
        names = []
        for member in self._group["members"]:
            if member.get("device_id"):
                names.append(
                    _member_channel_name(
                        getattr(self, "hass", None), self.entry.entry_id, member
                    )
                )
            else:
                names.append(f"{member['module']} CH{member['channel'] + 1}")
        return {
            ATTR_ADDRESS: self._group["label"],
            ATTR_MEMBERS: names,
        }

    def _member_ids(self, kinds: tuple[str, ...] | None = None) -> list[str]:
        ids = []
        for member in self._group["members"]:
            device_id = member.get("device_id")
            if not device_id:
                continue
            if kinds is not None and member.get("device_type") not in kinds:
                continue
            ids.append(str(device_id).upper())
        return ids

    def _listen(self, kinds: tuple[str, ...] | None = None, signal=None) -> None:
        listen_connection(self)
        for device_id in self._member_ids(kinds):
            name = signal(device_id) if signal else f"net4home_update_{device_id}"
            self.async_on_remove(
                async_dispatcher_connect(self.hass, name, self._member_callback(device_id))
            )

    def _member_callback(self, device_id: str):
        @callback
        def _update(payload) -> None:
            self._remember(device_id, payload)

        return _update

    def _remember(self, device_id: str, payload) -> None:
        if isinstance(payload, dict):
            if "is_on" in payload:
                self._reported[device_id] = bool(payload.get("is_on"))
            if payload.get("brightness") is not None:
                self._brightness[device_id] = payload["brightness"]
        else:
            self._reported[device_id] = bool(payload)
        self.async_write_ha_state()

    async def _send(self, value: int) -> None:
        ensure_connected(self.api)
        await self.api.async_set_group(self._group["address"], value)


class Net4HomeGroupLight(_GroupMembers, LightEntity):
    """A group whose members are all lights."""

    _attr_has_entity_name = False

    _attr_supported_color_modes = frozenset({ColorMode.BRIGHTNESS})
    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(self, api, entry, group: dict):
        _GroupMembers.__init__(self, api, entry, group)

    @property
    def is_on(self):
        if not self._reported:
            return None
        return any(self._reported.values())

    @property
    def brightness(self):
        values = list(self._brightness.values())
        return max(values) if values else None

    async def async_added_to_hass(self) -> None:
        self._listen(("light",))

    async def async_turn_on(self, **kwargs):
        level = kwargs.get("brightness", 255)
        percent = 100 if level is None else round(level * 100 / 255)
        await self._send(percent)

    async def async_turn_off(self, **kwargs):
        await self._send(0)


class Net4HomeGroupSwitch(_GroupMembers, SwitchEntity):
    """A group of switches, or a mix of lights and covers."""

    _attr_has_entity_name = False

    def __init__(self, api, entry, group: dict):
        _GroupMembers.__init__(self, api, entry, group)

    @property
    def is_on(self):
        if not self._reported:
            return None
        return any(self._reported.values())

    async def async_added_to_hass(self) -> None:
        self._listen(("light", "switch"))

    async def async_turn_on(self, **kwargs):
        await self._send(100)

    async def async_turn_off(self, **kwargs):
        await self._send(0)


class Net4HomeGroupCover(_GroupMembers, CoverEntity):
    """A group whose members are all covers."""

    _attr_has_entity_name = False

    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    def __init__(self, api, entry, group: dict):
        _GroupMembers.__init__(self, api, entry, group)
        self._closed: dict[str, bool | None] = {}

    @property
    def is_closed(self):
        known = [value for value in self._closed.values() if value is not None]
        if not known:
            return None
        return all(known)

    @callback
    def _remember(self, device_id: str, payload) -> None:
        """Payload is the member cover's is_closed, True means closed."""
        self._closed[device_id] = payload
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        known = getattr(self.api, "cover_closed", {})
        for device_id in self._member_ids(("cover",)):
            self._closed[device_id] = known.get(device_id)
        self._listen(("cover",), signal=cover_state_signal)

    async def async_open_cover(self, **kwargs):
        await self._send(MOTION_UP)

    async def async_close_cover(self, **kwargs):
        await self._send(MOTION_DOWN)

    async def async_stop_cover(self, **kwargs):
        await self._send(MOTION_STOP)
