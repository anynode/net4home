"""RF-key directory and access events for UP-RF readers.

Every presentation of a key is counted in a key book that survives restarts
(Home Assistant Store). Each reader gets an event entity whose event carries
the key and, once assigned, the person and key name.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import voluptuous as vol

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .rf_key_book import RfKeyBook, normalize_key_code

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
DETECTED_EVENT = "net4home_rf_key_detected"
ACCESS_SIGNAL = "net4home_rf_access_{device_id}"
BOOK_CHANGED_SIGNAL = "net4home_rf_book_changed_{entry_id}"
STORE_KEY = "rf_store:{entry_id}"
SAVE_DELAY = 5

SERVICE_ASSIGN = "assign_rf_key"
SERVICE_REMOVE = "remove_rf_key"


class RfKeyStore:
    """Owns the key book of one config entry and reacts to key presentations."""

    def __init__(self, hass: HomeAssistant, entry_id: str, api: Any) -> None:
        self._hass = hass
        self._entry_id = entry_id
        self._api = api
        self._store: Store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.rf_keys_{entry_id}")
        self.book = RfKeyBook()

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self.book = RfKeyBook(data.get("keys"))
        _LOGGER.info("RF key book loaded: %s keys", len(self.book))

    def _save_later(self) -> None:
        self._store.async_delay_save(self.book.to_dict, SAVE_DELAY)

    async def async_save(self) -> None:
        """Write now, e.g. on unload, so no pending change is lost."""
        await self._store.async_save(self.book.to_dict())

    def _notify_changed(self) -> None:
        async_dispatcher_send(self._hass, BOOK_CHANGED_SIGNAL.format(entry_id=self._entry_id))

    def _person_name(self, person: Optional[str]) -> Optional[str]:
        if not person:
            return None
        state = self._hass.states.get(person)
        if state is None:
            return person
        return state.name or person

    @callback
    def handle_detected(self, event) -> None:
        """Bus listener for net4home_rf_key_detected."""
        data = event.data
        reader = str(data.get("device_id", "")).upper()
        if reader not in self._api.devices:
            return
        when = dt_util.now().isoformat()
        valid, new = self.book.record(
            data.get("rf_key", ""), reader, data.get("state", "unknown"), when
        )
        if not valid:
            return
        normalized = normalize_key_code(data.get("rf_key"))
        entry = self.book.resolve(normalized) or {}
        if new:
            _LOGGER.info("New RF key %s seen at %s", normalized, reader)
        self._save_later()
        self._notify_changed()

        async_dispatcher_send(
            self._hass,
            ACCESS_SIGNAL.format(device_id=reader),
            {
                "state": data.get("state", "unknown"),
                "rf_key": normalized,
                "key_name": entry.get("name"),
                "person": entry.get("person"),
                "person_name": self._person_name(entry.get("person")),
            },
        )

    def assign(self, code: str, person: Optional[str], name: Optional[str]) -> bool:
        if not self.book.assign(code, person=person, name=name):
            return False
        self._save_later()
        self._notify_changed()
        return True

    def remove(self, code: str) -> bool:
        if not self.book.remove(code):
            return False
        self._save_later()
        self._notify_changed()
        return True


def _store_for(hass: HomeAssistant, entry_id: Optional[str]) -> Optional[RfKeyStore]:
    stores = {
        key.split(":", 1)[1]: value
        for key, value in hass.data.get(DOMAIN, {}).items()
        if isinstance(key, str) and key.startswith("rf_store:")
    }
    if entry_id:
        return stores.get(entry_id)
    if len(stores) == 1:
        return next(iter(stores.values()))
    return None


def async_setup_services(hass: HomeAssistant) -> None:
    """Register the key services once for the integration."""
    if hass.services.has_service(DOMAIN, SERVICE_ASSIGN):
        return

    async def _assign(call: ServiceCall) -> None:
        store = _store_for(hass, call.data.get("entry_id"))
        if store is None:
            _LOGGER.warning("assign_rf_key: no net4home entry or more than one; pass entry_id")
            return
        code = call.data["code"]
        if normalize_key_code(code) is None:
            _LOGGER.warning("assign_rf_key: %s is not a valid key code", code)
            return
        person = call.data.get("person")
        name = call.data.get("name")
        if not store.assign(code, person=person, name=name):
            _LOGGER.warning("assign_rf_key: %s could not be stored", code)

    async def _remove(call: ServiceCall) -> None:
        store = _store_for(hass, call.data.get("entry_id"))
        if store is None:
            _LOGGER.warning("remove_rf_key: no net4home entry or more than one; pass entry_id")
            return
        if not store.remove(call.data["code"]):
            _LOGGER.warning("remove_rf_key: %s is not in the key book", call.data["code"])

    common = {vol.Optional("entry_id"): cv.string}
    hass.services.async_register(
        DOMAIN,
        SERVICE_ASSIGN,
        _assign,
        schema=vol.Schema(
            {
                vol.Required("code"): cv.string,
                vol.Optional("person"): vol.Any(None, cv.entity_id),
                vol.Optional("name"): vol.Any(None, cv.string),
                **common,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE,
        _remove,
        schema=vol.Schema({vol.Required("code"): cv.string, **common}),
    )


class RfKeyDirectorySensor(SensorEntity):
    """Number of known keys; the keys themselves are in the attributes."""

    _attr_should_poll = False

    _attr_has_entity_name = False
    _attr_icon = "mdi:key-chain"
    _attr_name = "RF-Schlüsselverzeichnis"

    def __init__(self, entry_id: str, store: RfKeyStore) -> None:
        self._entry_id = entry_id
        self._store = store
        self._attr_unique_id = f"{entry_id}_rf_key_directory"

    @property
    def native_value(self) -> int:
        return len(self._store.book)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"keys": self._store.book.listing()}

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                BOOK_CHANGED_SIGNAL.format(entry_id=self._entry_id),
                self._handle_changed,
            )
        )

    @callback
    def _handle_changed(self) -> None:
        self.async_write_ha_state()


def store_key(entry_id: str) -> str:
    return STORE_KEY.format(entry_id=entry_id)


def access_signal(device_id: str) -> str:
    return ACCESS_SIGNAL.format(device_id=device_id.upper())
