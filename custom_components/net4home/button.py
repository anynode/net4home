from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from .api import Net4HomeApi, Net4HomeDevice

from .const import DOMAIN

class Net4HomeDeviceRefreshButton(ButtonEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:refresh"

    def __init__(self, api, entry, device):
        self.api = api
        self.entry = entry
        self.device = device
        self._attr_name = f"{device.name} Read state"
        self._attr_unique_id = f"{entry.entry_id}_diagnostic_refresh_{device.device_id}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id.upper())},
            name=self.device.name,
            manufacturer="net4home",
            model=self.device.model,
            via_device=(DOMAIN, self.device.via_device.upper()) if self.device.via_device else None,
        )

    async def async_press(self) -> None:
        """Handle the button press to refresh status."""
        await self.api.async_request_status(self.device.device_id)


async def async_setup_entry(hass, entry, async_add_entities):
    api: Net4HomeApi = hass.data[DOMAIN][entry.entry_id]
    buttons = []
    for device in api.devices.values():
        if device.device_type == "binary_sensor":
            buttons.append(Net4HomeDeviceRefreshButton(api, entry, device))
    async_add_entities(buttons)

    async def async_new_device(device: Net4HomeDevice):
        if device.device_type == "binary_sensor":
            async_add_entities([Net4HomeDeviceRefreshButton(api, entry, device)])

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"net4home_new_device_{entry.entry_id}", async_new_device
        )
    )

