# custom_components/net4home/models.py

from typing import Optional
from typing import NamedTuple

class Net4HomeDevice:
    def __init__(
        self,
        device_id: str,
        name: str,
        model: str,
        device_type: str,
        via_device: Optional[str] = None,
        objadr: Optional[int] = None,
        send_state_changes: bool = False,
        inverted: Optional[bool] = False         
    ):
        self.device_id = device_id
        self.name = name
        self.model = model
        self.device_type = device_type
        self.via_device = via_device
        self.objadr = objadr
        self.send_state_changes = send_state_changes
        self.inverted = inverted


class TN4Hpaket(NamedTuple):
    type8: int
    ipsrc: int
    ipdest: int
    objsrc: int
    ddatalen: int
    ddata: bytes
    csRX: int
    csCalc: int
    length: int
    posb: int
