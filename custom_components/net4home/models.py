# custom_components/net4home/models.py

from typing import Optional

class Net4HomeDevice:
    def __init__(
        self,
        device_id: str,
        name: str,
        model: str,
        device_type: str,
        via_device: Optional[str] = None,
        objadr: Optional[int] = None,
    ):
        self.device_id = device_id
        self.name = name
        self.model = model
        self.device_type = device_type
        self.via_device = via_device
        self.objadr = objadr
