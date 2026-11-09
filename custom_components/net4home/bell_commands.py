"""WAV bell commands."""
import asyncio
import logging

from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    D0_DEC,
    D0_ENABLE_CONFIGURATION,
    D0_INC,
    D0_RD_MODULSPEC_DATA,
    D0_RD_MODULSPEC_DATA_ACK,
    D1_ENABLE_CONFIGURATION_OK_BYTE,
    SEND_AS_IP,
    SEND_AS_OBJ_GRP,
)
from .bell_layout import (
    LINE_COUNT,
    adjust_attenuation,
    config_from_payload,
    db_from_attenuation,
    ensure_bell_runtime,
    is_wav_bell,
    mute_command,
    parse_bell_ack,
    power_command,
    toggle_command,
    track_command,
    tracks_from_lines,
    volume_command,
)

_LOGGER = logging.getLogger(__name__)

class BellCommands:
    """WAV bell commands."""

    def _publish_bell(self, device) -> None:
        async_dispatcher_send(self._hass, f"net4home_bell_{device.device_id.upper()}")

    async def _async_handle_bell_modulspec(self, device, ddata: bytes) -> None:
        """Store one 32-byte modulspec line and wake the line reader."""
        ensure_bell_runtime(device)
        known = device.objadr if device.objadr and device.objadr > 0 else None
        parsed = parse_bell_ack(ddata, device.bell_frame, known)
        if parsed is None:
            _LOGGER.warning(
                "WAV-Bell %s modulspec reply is too short (%s bytes): %s",
                device.device_id,
                len(ddata),
                ddata.hex(),
            )
            return
        frame, index, payload = parsed
        device.bell_frame = frame
        device.bell_lines[index] = payload
        changed = False
        if index == 0:
            cfg = config_from_payload(payload)
            if cfg:
                address = cfg["objadr"]
                if address and address != device.objadr:
                    device.objadr = address
                    await self._async_save_objadr(device.device_id, address)
                    async_dispatcher_send(
                        self._hass,
                        f"net4home_device_updated_{self._entry.entry_id}",
                        device.device_id,
                    )
                device.bell_volume = cfg["volume"]
                device.bell_alarm_volume = cfg["alarm_volume"]
                device.bell_on = cfg["on"]
                device.bell_toggle_track = cfg["toggle"]
                changed = True
                _LOGGER.info(
                    "WAV-Bell %s line 0 (%s): AdrUK=%s, volume %s dB, alarm %s dB, on=%s, standard track %s",
                    device.device_id,
                    frame,
                    address,
                    db_from_attenuation(cfg["volume"]),
                    db_from_attenuation(cfg["alarm_volume"]),
                    cfg["on"],
                    None if cfg["toggle"] is None else cfg["toggle"] + 1,
                )
        tracks = tracks_from_lines(device.bell_lines)
        if tracks is not None and tracks != device.bell_tracks:
            device.bell_tracks = tracks
            device.bell_loaded = True
            changed = True
            names = ", ".join(f"{track['index'] + 1}:{track['name']}" for track in tracks)
            _LOGGER.info("WAV-Bell %s tracks: %s", device.device_id, names or "keine")
        if changed:
            self._publish_bell(device)
        try:
            mi_addr = int(device.device_id[2:], 16)
        except ValueError:
            return
        self._release_line_read(mi_addr, D0_RD_MODULSPEC_DATA_ACK, index)

    async def async_ensure_bell_objadr(self, device) -> int | None:
        """Read the WAV-Bell config when AdrUK is not stored yet."""
        if device.objadr:
            return device.objadr
        await self.async_load_bell_config(device)
        return device.objadr

    async def async_load_missing_bell_addresses(self) -> None:
        """Load AdrUK for WAV-Bell modules that have no object address yet."""
        await self.async_load_bell_modules()

    async def async_load_bell_modules(self) -> None:
        """Read track names, volume and the on/off byte of every WAV-Bell."""
        for device in list(self.devices.values()):
            if is_wav_bell(device):
                await self.async_load_bell_config(device)

    async def async_load_bell_config(self, device, force: bool = False) -> None:
        """Read all 25 modulspec lines. A second caller waits for the first."""
        ensure_bell_runtime(device)
        if not force and device.bell_loaded:
            return
        if self._packet_sender is None or not str(device.device_id).startswith("MI"):
            return
        inflight = device.bell_load_event
        if inflight is not None and not inflight.is_set():
            await inflight.wait()
        if device.bell_loaded and not force:
            return
        device.bell_load_event = asyncio.Event()
        try:
            if force:
                device.bell_lines = {}
                device.bell_loaded = False
                device.bell_tracks = None
            mi_addr = int(device.device_id[2:], 16)
            await self._packet_sender.send_raw_command(
                ipdst=mi_addr,
                ddata=bytes([D0_ENABLE_CONFIGURATION, D1_ENABLE_CONFIGURATION_OK_BYTE]),
                objsource=self._objadr,
                mi=self._mi,
                type8=SEND_AS_IP,
            )
            await asyncio.sleep(0.1)
            await self._async_read_table_lines(
                mi_addr,
                D0_RD_MODULSPEC_DATA,
                D0_RD_MODULSPEC_DATA_ACK,
                LINE_COUNT,
                "WAV-Bell",
            )
            if len(device.bell_lines) < LINE_COUNT:
                _LOGGER.warning(
                    "WAV-Bell %s config incomplete, lines %s",
                    device.device_id,
                    sorted(device.bell_lines),
                )
        except Exception as err:
            _LOGGER.error("WAV-Bell config read for %s failed: %s", device.device_id, err)
        finally:
            device.bell_load_event.set()

    async def _async_bell_object(self, device, alarm: bool = False) -> int | None:
        objadr = device.objadr or await self.async_ensure_bell_objadr(device)
        if not objadr:
            _LOGGER.warning(
                "No objadr for WAV-Bell %s. AdrUK was not in the module config reply.",
                device.device_id,
            )
            return None
        return objadr + (1 if alarm else 0)

    async def _async_send_bell(self, device, objadr: int, ddata: bytes, label: str) -> None:
        await self._packet_sender.send_raw_command(
            ipdst=objadr,
            ddata=ddata,
            objsource=self._objadr,
            mi=self._mi,
            type8=SEND_AS_OBJ_GRP,
        )
        _LOGGER.info(
            "WAV-Bell %s %s -> object %s (%s)",
            device.device_id,
            label,
            objadr,
            ddata.hex(),
        )
        self._publish_bell(device)

    async def async_send_bell_command(self, device_id: str, command: str) -> None:
        """Send on, off, volume step or the standard-track trigger."""
        device = self.get_known_device(device_id)
        if not device:
            _LOGGER.warning("WAV-Bell: device %s not found", device_id)
            return
        ensure_bell_runtime(device)
        objadr = await self._async_bell_object(device)
        if objadr is None:
            return
        if command == "ON":
            ddata = power_command(True, True)
            device.bell_on = True
        elif command == "OFF":
            ddata = power_command(False, True)
            device.bell_on = False
        elif command == "ON_SILENT":
            ddata = power_command(True, False)
            device.bell_on = True
        elif command == "OFF_SILENT":
            ddata = power_command(False, False)
            device.bell_on = False
        elif command == "INC_VOL":
            ddata = bytes([D0_INC, 0, 0])
            device.bell_volume = adjust_attenuation(device.bell_volume, True)
        elif command == "DEC_VOL":
            ddata = bytes([D0_DEC, 0, 0])
            device.bell_volume = adjust_attenuation(device.bell_volume, False)
        elif command == "TOGGLE":
            ddata = toggle_command()
        else:
            _LOGGER.warning("WAV-Bell: unknown command %s", command)
            return
        await self._async_send_bell(device, objadr, ddata, command)

    async def async_send_bell_volume(self, device_id: str, attenuation: int, alarm: bool = False) -> None:
        """Set the live volume. Alarm volume is the next object address."""
        device = self.get_known_device(device_id)
        if not device:
            _LOGGER.warning("WAV-Bell: device %s not found", device_id)
            return
        ensure_bell_runtime(device)
        objadr = await self._async_bell_object(device, alarm=alarm)
        if objadr is None:
            return
        if alarm:
            device.bell_alarm_volume = attenuation
        else:
            device.bell_volume = attenuation
        await self._async_send_bell(
            device,
            objadr,
            volume_command(attenuation),
            "Alarm-Lautstärke" if alarm else "Lautstärke",
        )

    async def async_send_bell_mute(self, device_id: str, minutes: int) -> None:
        """Turn the bell off, with the confirmation beep, for 60, 120 or 240 minutes."""
        device = self.get_known_device(device_id)
        if not device:
            _LOGGER.warning("WAV-Bell: device %s not found", device_id)
            return
        objadr = await self._async_bell_object(device)
        if objadr is None:
            return
        await self._async_send_bell(device, objadr, mute_command(minutes), f"Stumm {minutes} min")

    async def async_send_bell_track(
        self,
        device_id: str,
        track: int,
        repeats: int = 1,
        interrupt: bool = True,
        dnr: bool = False,
    ) -> None:
        """Play a WAV-Bell track with D0_SET_N. Track is 0–31."""
        device = self.get_known_device(device_id)
        if not device:
            _LOGGER.warning("WAV-Bell: device %s not found", device_id)
            return
        objadr = await self._async_bell_object(device)
        if objadr is None:
            return
        try:
            ddata = track_command(track, repeats, interrupt, dnr)
        except ValueError as err:
            _LOGGER.warning("WAV-Bell %s: %s", device_id, err)
            return
        await self._async_send_bell(
            device,
            objadr,
            ddata,
            f"Spur {track + 1} repeats={max(1, min(16, int(repeats)))} interrupt={interrupt} dnr={dnr}",
        )
