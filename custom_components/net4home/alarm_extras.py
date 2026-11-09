"""Entities derived from an HS-Safety panel and its contact list.

- Bereit (Extern): every contact that Extern monitors is closed
- Alarm: the panel is armed and a contact of that level is open
- one binary sensor per trigger of the Tab1 list (open/closed)
- Scharf-Stufe: the arming level as text
- buttons for arming without the contact check, disabled by default
"""

import logging

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.components.button import ButtonEntity
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .alarm_layout import (
    ALARM_SET_AWAY_UNCHECKED,
    ALARM_SET_HOME_UNCHECKED,
    ALARM_SET_NIGHT_UNCHECKED,
    LEVEL_LABELS,
    STATE_ARMED_AWAY,
    breach,
    open_contact_names,
    ready_for_away,
    trigger_level_names,
    unknown_contact_names,
)
from .const import DOMAIN
from .helpers import parent_device_link

_LOGGER = logging.getLogger(__name__)


def _device_info(entity, entry, device) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, device.device_id.upper())},
        name=device.name,
        manufacturer="net4home",
        model=device.model,
        **parent_device_link(entity.hass, entry.entry_id, device.via_device),
    )


class _AlarmSignalMixin:
    """Refresh on panel status replies and on trigger or contact updates."""

    _attr_has_entity_name = False

    def _init_alarm(self, api, entry, device) -> None:
        self.api = api
        self.entry = entry
        self.device = device

    @property
    def device_info(self) -> DeviceInfo:
        return _device_info(self, self.entry, self.device)

    def _refresh(self) -> None:
        """Recompute the value from the device attributes."""

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        mi = self.device.device_id.upper()
        for signal in (f"net4home_update_{mi}", f"net4home_alarm_{mi}"):
            self.async_on_remove(
                async_dispatcher_connect(self.hass, signal, self._handle_alarm_signal)
            )
        self._refresh()

    @callback
    def _handle_alarm_signal(self, _data=None) -> None:
        self._refresh()
        self.async_write_ha_state()

    def _triggers(self) -> dict:
        return getattr(self.device, "alarm_triggers", None) or {}

    def _contacts(self) -> dict:
        return getattr(self.device, "alarm_contacts", None) or {}


class Net4HomeAlarmReadyBinarySensor(_AlarmSignalMixin, BinarySensorEntity):
    """On when every contact that Extern monitors is closed.

    Stays unknown while a monitored contact has no status reply. Those
    contacts are listed as attribute, so the reason is visible.
    """

    _attr_should_poll = False

    _attr_icon = "mdi:shield-check"

    def __init__(self, api, entry, device) -> None:
        self._init_alarm(api, entry, device)
        self._attr_name = f"{device.name} Bereit (Extern)"
        self._attr_unique_id = f"{entry.entry_id}_{device.device_id.lower()}_ready"
        self._value = None
        self._open: list[str] = []
        self._unknown: list[str] = []
        self._refresh()

    @property
    def is_on(self) -> bool | None:
        return self._value

    @property
    def extra_state_attributes(self):
        return {"open_contacts": self._open, "unknown_contacts": self._unknown}

    def _refresh(self) -> None:
        triggers, contacts = self._triggers(), self._contacts()
        self._value = ready_for_away(triggers, contacts)
        self._open = open_contact_names(triggers, contacts, STATE_ARMED_AWAY)
        self._unknown = unknown_contact_names(triggers, contacts, STATE_ARMED_AWAY)


class Net4HomeAlarmBreachBinarySensor(_AlarmSignalMixin, BinarySensorEntity):
    """On while armed and a contact of the armed level is open."""

    _attr_should_poll = False

    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(self, api, entry, device) -> None:
        self._init_alarm(api, entry, device)
        self._attr_name = f"{device.name} Alarm"
        self._attr_unique_id = f"{entry.entry_id}_{device.device_id.lower()}_breach"
        self._value = None
        self._open: list[str] = []
        self._refresh()

    @property
    def is_on(self) -> bool | None:
        return self._value

    @property
    def extra_state_attributes(self):
        return {"open_contacts": self._open}

    def _refresh(self) -> None:
        state = getattr(self.device, "alarm_state", None)
        self._value = breach(self._triggers(), self._contacts(), state)
        self._open = (
            open_contact_names(self._triggers(), self._contacts(), state)
            if self._value
            else []
        )


class Net4HomeAlarmContactBinarySensor(_AlarmSignalMixin, BinarySensorEntity):
    """One contact of the Tab1 trigger list. On means open."""

    _attr_should_poll = False

    _attr_device_class = BinarySensorDeviceClass.OPENING

    def __init__(self, api, entry, device, index: int) -> None:
        self._init_alarm(api, entry, device)
        self._index = index
        trigger = self._trigger() or {"name": "", "address": 0}
        label = trigger.get("name") or f"Auslöser {index + 1}"
        self._attr_name = f"{device.name} {label}"
        self._attr_unique_id = f"{entry.entry_id}_{device.device_id.lower()}_trigger_{index}"

    def _trigger(self):
        return self._triggers().get(self._index)

    @property
    def is_on(self) -> bool | None:
        trigger = self._trigger()
        if trigger is None:
            return None
        closed = self._contacts().get(trigger["address"])
        return None if closed is None else not closed

    @property
    def extra_state_attributes(self):
        trigger = self._trigger()
        if trigger is None:
            return {}
        return {
            "address": trigger["address"],
            "armed_levels": trigger_level_names(trigger),
            "sabotage_contact": trigger["sabotage"],
            "normally_open": trigger["normally_open"],
            "normally_closed": trigger["normally_closed"],
        }


class Net4HomeAlarmLevelSensor(_AlarmSignalMixin, SensorEntity):
    """Current arming level of the panel."""

    _attr_should_poll = False

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(LEVEL_LABELS.values())
    _attr_icon = "mdi:shield-half-full"

    def __init__(self, api, entry, device) -> None:
        self._init_alarm(api, entry, device)
        self._attr_name = f"{device.name} Scharf-Stufe"
        self._attr_unique_id = f"{entry.entry_id}_{device.device_id.lower()}_level"

    @property
    def native_value(self) -> str | None:
        return LEVEL_LABELS.get(getattr(self.device, "alarm_state", None))


class Net4HomeAlarmLogSensor(_AlarmSignalMixin, SensorEntity):
    """Protocol stored on the panel. The state is the newest line."""

    _attr_should_poll = False

    _attr_icon = "mdi:clipboard-text-clock"

    def __init__(self, api, entry, device) -> None:
        self._init_alarm(api, entry, device)
        self._attr_name = f"{device.name} Protokoll"
        self._attr_unique_id = f"{entry.entry_id}_{device.device_id.lower()}_log"
        self._rows: list[dict] = []
        self._value = None
        self._refresh()

    @property
    def native_value(self) -> str | None:
        return self._value

    @property
    def extra_state_attributes(self):
        return {"rows": self._rows, "entries": [row["line"] for row in self._rows]}

    def _refresh(self) -> None:
        log = getattr(self.device, "alarm_log", None)
        if log is None:
            self._rows = []
            self._value = None
            return
        self._rows = [
            {
                "time": event["time"],
                "trigger": event["trigger"],
                "text": event["text"],
                "line": event["line"],
            }
            for event in log
        ]
        self._value = log[0]["line"] if log else "Keine Einträge"


class Net4HomeAlarmUncheckedArmButton(ButtonEntity):
    """Arm a level without the contact check. An open contact then alarms at once."""

    _attr_should_poll = False

    _attr_icon = "mdi:shield-alert"
    _attr_entity_registry_enabled_default = False

    def __init__(self, api, entry, device, mode: int, label: str) -> None:
        self.api = api
        self.entry = entry
        self.device = device
        self._mode = mode
        self._attr_name = f"{device.name} Scharf ohne Prüfung: {label}"
        self._attr_unique_id = f"{entry.entry_id}_{device.device_id.lower()}_unchecked_{mode}"

    @property
    def device_info(self) -> DeviceInfo:
        return _device_info(self, self.entry, self.device)

    async def async_press(self) -> None:
        _LOGGER.warning(
            "HS-Safety %s armed without contact check (command %s)",
            self.device.device_id,
            self._mode,
        )
        await self.api.async_set_alarm_state(self.device.device_id, self._mode)


def alarm_binary_sensors(api, entry, device) -> list:
    """Ready and breach sensors for one HS-Safety panel."""
    return [
        Net4HomeAlarmReadyBinarySensor(api, entry, device),
        Net4HomeAlarmBreachBinarySensor(api, entry, device),
    ]


def alarm_level_sensors(api, entry, device) -> list:
    return [
        Net4HomeAlarmLevelSensor(api, entry, device),
        Net4HomeAlarmLogSensor(api, entry, device),
    ]


def alarm_unchecked_buttons(api, entry, device) -> list:
    return [
        Net4HomeAlarmUncheckedArmButton(api, entry, device, ALARM_SET_HOME_UNCHECKED, "Intern 1"),
        Net4HomeAlarmUncheckedArmButton(api, entry, device, ALARM_SET_NIGHT_UNCHECKED, "Intern 2"),
        Net4HomeAlarmUncheckedArmButton(api, entry, device, ALARM_SET_AWAY_UNCHECKED, "Extern"),
    ]


def async_listen_alarm_contacts(hass, entry, api, device, add_entities) -> None:
    """Create one contact sensor per trigger, also for lists read after startup."""
    known: set[int] = set()
    mi = device.device_id.upper()

    @callback
    def _add_new(_data=None) -> None:
        triggers = getattr(device, "alarm_triggers", None) or {}
        new = [
            Net4HomeAlarmContactBinarySensor(api, entry, device, index)
            for index in sorted(triggers)
            if index not in known
        ]
        if new:
            known.update(sensor._index for sensor in new)
            add_entities(new)

    entry.async_on_unload(
        async_dispatcher_connect(hass, f"net4home_alarm_{mi}", _add_new)
    )
    _add_new()
