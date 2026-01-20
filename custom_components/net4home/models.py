# custom_components/net4home/models.py

from typing import Optional
from typing import NamedTuple
from datetime import datetime

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
        inverted: Optional[bool] = False,
        detail_status: str = "pending",
        detail_retry_count: int = 0,
        last_detail_request: Optional[datetime] = None,
        discovered_at: Optional[datetime] = None,
        module_type: Optional[int] = None,  # PLATINE_HW_IS_* Konstante
        ns: Optional[int] = None,  # Anzahl Sensoren
        na: Optional[int] = None,  # Anzahl Aktoren
        nm: Optional[int] = None,  # ModulSpec-Tabellen-Länge
        ng: Optional[int] = None,  # Gruppentabellen-Länge
        powerup_status: Optional[int] = None,  # Powerup-Status (0-4)
        min_hell: Optional[int] = None,  # Minimale Helligkeit bei Dimmern (0-100)
        timer_time1: Optional[int] = None,  # Timer Zeit1 in Sekunden (bei Timer-Aktoren und Jalousien)
    ):
        self.device_id = device_id
        self.name = name
        self.model = model
        self.device_type = device_type
        self.via_device = via_device
        self.objadr = objadr
        self.send_state_changes = send_state_changes
        self.inverted = inverted
        self.detail_status = detail_status  # pending, in_progress, completed, failed
        self.detail_retry_count = detail_retry_count
        self.last_detail_request = last_detail_request
        self.discovered_at = discovered_at or datetime.now()
        self.module_type = module_type
        self.ns = ns
        self.na = na
        self.nm = nm
        self.ng = ng
        self.powerup_status = powerup_status
        self.min_hell = min_hell
        self.timer_time1 = timer_time1


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
