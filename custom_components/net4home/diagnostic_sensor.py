from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import EntityCategory


from .const import DOMAIN

# Diagnostic für inverted-Flag (binary_sensor)
class Net4HomeInvertedDiagnosticSensor(SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:swap-vertical"

    def __init__(self, entry, device):
        self.entry = entry
        self.device = device
        self._attr_name = f"{device.name} Inverted"
        self._attr_unique_id = f"{entry.entry_id}_diagnostic_inverted_{device.device_id}"

    @property
    def native_value(self):
        devices_opts = self.entry.options.get("devices", {})
        dev_opts = devices_opts.get(self.device.device_id, {})
        return dev_opts.get("inverted", False)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id.upper())},
            name=self.device.name,
            manufacturer="net4home",
            model=self.device.model,
            via_device=(DOMAIN, self.device.via_device.upper()) if self.device.via_device else None,
        )

# Diagnostic für send_state_changes
class Net4HomeSendStateChangesDiagnosticSensor(SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:sync-alert"


    def __init__(self, entry, device):
        self.entry = entry
        self.device = device
        self._attr_name = f"{device.name} Send state changes"
        self._attr_unique_id = f"{entry.entry_id}_diagnostic_send_state_changes_{device.device_id}"

    @property
    def native_value(self):
        devices_opts = self.entry.options.get("devices", {})
        dev_opts = devices_opts.get(self.device.device_id, {})
        value = dev_opts.get("send_state_changes", getattr(self.device, "send_state_changes", False))
        return "true" if value else "false"
        
    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id.upper())},
            name=self.device.name,
            manufacturer="net4home",
            model=self.device.model,
            via_device=(DOMAIN, self.device.via_device.upper()) if self.device.via_device else None,
        )

