"""Bus connection for one net4home config entry.

Packet coding lives in protocol.py. Incoming packets live in
packet_dispatch.py. Commands are split by device kind.
"""
import asyncio
import binascii
import logging
from typing import Optional

from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONNECT_TIMEOUT,
    D0_RD_SENSOR_DATA,
    DEFAULT_MI,
    DEFAULT_OBJADR,
    N4H_IP_PORT,
    SEND_AS_IP,
)
from .models import Net4HomeDevice
from .protocol import (
    N4HPacketReceiver,
    N4HPacketSender,
)
from .packet_dispatch import PacketDispatch
from .actor_commands import ActorCommands
from .bell_commands import BellCommands
from .lcd_commands import LcdCommands
from .rf_commands import RfCommands
from .group_commands import GroupCommands
from .alarm_commands import AlarmCommands
from .hs_time_commands import HsTimeCommands
from .si_commands import SiCommands
from .lock_commands import LockCommands
from .climate_commands import ClimateCommands
from .discovery_commands import DiscoveryCommands

_LOGGER = logging.getLogger(__name__)


class Net4HomeApi(
    PacketDispatch,
    ActorCommands,
    BellCommands,
    LcdCommands,
    RfCommands,
    GroupCommands,
    AlarmCommands,
    HsTimeCommands,
    SiCommands,
    LockCommands,
    ClimateCommands,
    DiscoveryCommands,
):
    """Main API class for net4home bus connector communication."""

    def __init__(
        self,
        hass,
        host,
        port: int = N4H_IP_PORT,
        password: str = "",
        mi: int = DEFAULT_MI,
        objadr: int = DEFAULT_OBJADR,
        entry_id: Optional[str] = None,
        entry=None,
        auto_discovery_enabled: bool = True,
        read_groups_on_startup: bool = True,
        read_module_info_on_startup: bool = True,
    ):
        """Initialize the net4home API."""
        self._hass = hass
        self._entry_id = entry_id
        self._host = host
        self._port = port
        self._password = password
        self._mi = mi
        self._objadr = objadr
        self._reader = None
        self._writer = None
        self._packet_receiver = N4HPacketReceiver()
        self._packet_sender: Optional[N4HPacketSender] = None
        self.devices: dict[str, Net4HomeDevice] = {}
        self.groups: list = []
        self._groups_loaded = False
        self._reconnect_enabled = True
        self._entry = entry
        self._auto_discovery_enabled = auto_discovery_enabled
        self.read_groups_on_startup = read_groups_on_startup
        self.read_module_info_on_startup = read_module_info_on_startup
        self._discovery_pending: set[str] = set()
        
        # Detail retrieval queue management
        self._detail_queue: Optional[asyncio.Queue] = None
        self._detail_queue_task: Optional[asyncio.Task] = None
        self._detail_queue_running = False
        self._detail_rate_limit = 2.0  # Seconds between queries (reduced for more traffic)
        self._detail_initial_delay = 3.0  # Initial delay after start (reduced)
        
        # ENUM_ALL state management (for small systems: 3 rounds)
        self._enum_state: int = 0  # 0 = not active, 1-3 = round number
        self._enum_timeout_task: Optional[asyncio.Task] = None
        self._enum_timeout_seconds: float = 0.5  # 500ms timeout (fixed)
        
        # Track MI addresses we've already sent ENUM to (to avoid spam)
        self._enum_sent_to: set[int] = set()
        # Modules whose actor channels were requested again because a channel was missing
        self._missing_actor_reread: set[str] = set()
        self._alarm_poll_tasks: dict[str, asyncio.Task] = {}
        self._alarm_log_pending: set[str] = set()
        self._alarm_config_locks: dict[str, asyncio.Lock] = {}
        self._rf_key_list_tasks: dict[str, asyncio.Task] = {}
        self._hs_time_poll_task: Optional[asyncio.Task] = None
        # One configuration read at a time. The module answers the latest request only.
        self._line_reads: dict[tuple[int, int], dict] = {}
        
        # Listener task management
        self._listen_task: Optional[asyncio.Task] = None
        self.connected = False
        # Last open/closed state per cover channel, read by group covers
        self.cover_closed: dict[str, Optional[bool]] = {}

    def connection_signal(self) -> str:
        """Dispatcher signal sent when the bus connection goes up or down."""
        return f"net4home_connection_{self._entry_id}"

    def _set_connected(self, connected: bool) -> None:
        if self.connected == connected:
            return
        self.connected = connected
        if connected:
            _LOGGER.info("Connection to bus connector %s:%s is up", self._host, self._port)
        else:
            _LOGGER.warning("Connection to bus connector %s:%s is down", self._host, self._port)
        async_dispatcher_send(self._hass, self.connection_signal, connected)

    async def async_connect(self):
        """Connect to the net4home bus connector."""
        await self._async_connect_ip()

    async def _async_connect_ip(self):
        """Connect via IP/TCP."""
        async with asyncio.timeout(CONNECT_TIMEOUT):
            self._reader, self._writer = await asyncio.open_connection(self._host, self._port)
            _LOGGER.info(f"Connect with net4home Bus connector at {self._host}:{self._port}")

            # The bus connector expects the password as a modified MD5 hash.
            # Until that is ported, this fixed login packet is sent.
            packet_bytes = binascii.unhexlify(
                "420000000008ac0f0000cd564c77400c000021203732363343423543464343333646323630364344423338443945363135394535401b0000080700000087000000c000000aac"
            )

            self._writer.write(packet_bytes)
            await self._writer.drain()
        _LOGGER.debug("Credentials to Bus connector sent. Waiting for approval...")

        self._packet_sender = N4HPacketSender(self._writer)
        self._set_connected(True)

    async def async_reconnect(self, max_attempts: int = 5, base_delay: float = 5.0) -> None:
        """Attempt to reconnect to the bus connector."""
        _LOGGER.debug(f"[IP] Starting reconnect process (max {max_attempts} attempts)")
        self._set_connected(False)

        for attempt in range(1, max_attempts + 1):
            if not self._reconnect_enabled:
                return
            delay = base_delay * attempt
            _LOGGER.warning(f"[IP] Try to reconnect - attempt {attempt}/{max_attempts} in {delay:.1f}s...")

            await asyncio.sleep(delay)

            try:
                # Close existing connection if any
                if self._writer:
                    _LOGGER.debug(f"[IP] Closing existing connection before reconnect")
                    try:
                        if hasattr(self._writer, 'is_closing') and not self._writer.is_closing():
                            self._writer.close()
                            if hasattr(self._writer, 'wait_closed'):
                                await self._writer.wait_closed()
                            _LOGGER.debug(f"[IP] Existing connection closed")
                    except Exception as e:
                        _LOGGER.warning(f"[IP] Error closing existing connection: {e}")
                
                _LOGGER.debug(f"[IP] Attempting to establish new connection (attempt {attempt})")
                await self.async_connect()
                
                # Check connection status
                is_connected = self._writer is not None and not self._writer.is_closing()
                _LOGGER.debug(f"[IP] Connection check: writer={self._writer is not None}, is_closing={self._writer.is_closing() if self._writer else 'N/A'}")
                
                if is_connected:
                    _LOGGER.info(f"[IP] Reconnect successful on attempt {attempt}")

                    _LOGGER.debug(f"[IP] Requesting status for {len(self.devices)} devices")
                    for device in self.devices.values():
                        if device.device_type == "switch":
                            await self.async_request_status(device.device_id)
                        if device.device_type == "light":
                            await self.async_request_status(device.device_id)
                    _LOGGER.debug(f"[IP] Status requests completed")
                    return
                else:
                    _LOGGER.warning(f"[IP] Connection established but status check failed")
            except (OSError, TimeoutError) as e:
                _LOGGER.warning("[IP] Reconnect failed (Try %s): %s", attempt, e)
            except Exception as e:
                _LOGGER.error(f"[IP] Reconnect failed (Try {attempt}): {e}", exc_info=True)

        _LOGGER.error(f"[IP] Maximale Reconnect-Versuche erreicht. Keine Verbindung zum Bus möglich.")

    async def async_disconnect(self):
        """Disconnect from the net4home bus connector."""
        _LOGGER.debug("[IP] Starting disconnect process")
        
        # Stop reconnect to prevent reconnection attempts
        self._reconnect_enabled = False
        _LOGGER.debug("[IP] Reconnect disabled")

        background = [
            *self._alarm_poll_tasks.values(),
            *self._rf_key_list_tasks.values(),
        ]
        for task in background:
            if not task.done():
                task.cancel()
        if background:
            await asyncio.gather(*background, return_exceptions=True)
        self._alarm_poll_tasks.clear()
        self._rf_key_list_tasks.clear()

        # Cancel ENUM_ALL timeout if active
        if self._hs_time_poll_task and not self._hs_time_poll_task.done():
            self._hs_time_poll_task.cancel()
            try:
                await self._hs_time_poll_task
            except asyncio.CancelledError:
                pass
            self._hs_time_poll_task = None

        if self._enum_timeout_task:
            _LOGGER.debug("[IP] Cancelling ENUM_ALL timeout task")
            self._enum_timeout_task.cancel()
            try:
                await self._enum_timeout_task
            except asyncio.CancelledError:
                pass
            self._enum_timeout_task = None
        self._enum_state = 0
        
        # Cancel and wait for listener task to finish
        if self._listen_task and not self._listen_task.done():
            _LOGGER.debug("[IP] Cancelling listener task")
            self._listen_task.cancel()
            try:
                # Wait for task to finish with timeout
                await asyncio.wait_for(self._listen_task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                _LOGGER.debug("[IP] Listener task cancelled or timed out")
            except Exception as e:
                _LOGGER.warning(f"[IP] Error waiting for listener task: {e}")
            self._listen_task = None
        
        # Close writer connection with timeout
        if self._writer:
            _LOGGER.debug("[IP] Closing writer connection")
            try:
                self._writer.close()
                if hasattr(self._writer, 'wait_closed'):
                    # Use timeout to prevent blocking
                    try:
                        await asyncio.wait_for(self._writer.wait_closed(), timeout=2.0)
                        _LOGGER.debug("[IP] Connection to net4home Bus connector closed successfully")
                    except asyncio.TimeoutError:
                        _LOGGER.warning("[IP] Timeout waiting for connection to close, forcing close")
                        # Force close if timeout
                        if hasattr(self._writer, 'transport') and self._writer.transport:
                            try:
                                self._writer.transport.abort()
                            except Exception:
                                pass
                else:
                    _LOGGER.debug("[IP] Writer closed (no wait_closed method)")
            except Exception as e:
                _LOGGER.warning(f"[IP] Error closing connection: {e}", exc_info=True)
            finally:
                self._writer = None
        else:
            _LOGGER.debug("[IP] No writer to close")
        
        # Clean up reader
        if self._reader:
            try:
                if hasattr(self._reader, 'transport') and self._reader.transport:
                    self._reader.transport.abort()
            except Exception as e:
                _LOGGER.debug(f"[IP] Error closing reader transport: {e}")
            self._reader = None

        self._set_connected(False)
        _LOGGER.debug("[IP] Disconnect process completed")

    def _expect_line_read(self, ipsrc: int, command: int, index: int) -> asyncio.Event:
        """Arm the waiter for one configuration-table line."""
        event = asyncio.Event()
        self._line_reads[(ipsrc, command)] = {"index": index, "event": event}
        return event

    def _release_line_read(self, ipsrc: int, command: int, index: int) -> None:
        """Wake the reader once the matching line reply has been handled."""
        waiter = self._line_reads.get((ipsrc, command))
        if waiter and waiter["index"] == index and not waiter["event"].is_set():
            waiter["event"].set()

    async def _async_read_one_table_line(
        self,
        mi_addr: int,
        request_cmd: int,
        ack_cmd: int,
        channel: int,
        label: str,
    ) -> bool:
        """Read one configuration line. A lost first request is repeated once."""
        for attempt in (1, 2):
            event = self._expect_line_read(mi_addr, ack_cmd, channel)
            try:
                await self._packet_sender.send_raw_command(
                    ipdst=mi_addr,
                    ddata=bytes([request_cmd, channel, 0x00]),
                    objsource=self._objadr,
                    mi=self._mi,
                    type8=SEND_AS_IP,
                )
                try:
                    await asyncio.wait_for(event.wait(), timeout=2.0)
                    return True
                except TimeoutError:
                    _LOGGER.debug(
                        "%s line %s from MI%04X no answer within 2s (attempt %s)",
                        label,
                        channel,
                        mi_addr,
                        attempt,
                    )
            finally:
                current = self._line_reads.get((mi_addr, ack_cmd))
                if current and current["event"] is event:
                    self._line_reads.pop((mi_addr, ack_cmd), None)
        return False

    async def _async_read_table_lines(
        self,
        mi_addr: int,
        request_cmd: int,
        ack_cmd: int,
        count: int,
        label: str,
        start: int = 0,
    ) -> list:
        """Read configuration lines one by one, the way the configurator does.

        Lines that stay silent are asked once more after the rest of the
        table. A busy bus often answers that second pass.
        """
        missed = []
        for channel in range(start, start + count):
            if not await self._async_read_one_table_line(
                mi_addr, request_cmd, ack_cmd, channel, label
            ):
                missed.append(channel)
        if missed:
            await asyncio.sleep(1.0)
            still = []
            for channel in missed:
                if not await self._async_read_one_table_line(
                    mi_addr, request_cmd, ack_cmd, channel, label
                ):
                    still.append(channel)
            missed = still
        if missed:
            _LOGGER.warning(
                "%s from MI%04X missed lines %s",
                label,
                mi_addr,
                ", ".join(str(channel) for channel in missed),
            )
        return missed

    async def async_request_sensor_data(self, device_id: str, channel: int = 0):
        """Request sensor data for a device (MI address)."""
        try:
            if not device_id.startswith("MI"):
                _LOGGER.warning(f"Invalid device_id: {device_id} for sensor data request (expected MI address).")
                return

            device = self.devices.get(device_id)
            if not device:
                _LOGGER.warning(f"Device {device_id} not found")
                return
            
            mi_addr = int(device_id[2:], 16)

            await self._packet_sender.send_raw_command(
                ipdst=mi_addr,
                ddata=bytes([D0_RD_SENSOR_DATA, channel, 0x00]), 
                objsource=self._objadr,
                mi=self._mi,
                type8=SEND_AS_IP,
            )

            _LOGGER.debug(f"Sensor data request for {device_id} channel {channel} sent")
        except Exception as e:
            _LOGGER.error(f"Error sending sensor data request for {device_id}: {e}")

    async def _async_save_objadr(self, device_id: str, objadr: int) -> None:
        """Persist a module base address so the next start can use it."""
        try:
            devices = dict(self._entry.options.get("devices", {}))
            if device_id not in devices:
                return
            devices[device_id]["objadr"] = objadr
            options = dict(self._entry.options)
            options["devices"] = devices
            self._hass.config_entries.async_update_entry(self._entry, options=options)
        except Exception as e:
            _LOGGER.error(f"Failed to save objadr for {device_id}: {e}")

    def get_known_device(self, device_id: str) -> Optional[Net4HomeDevice]:
        """Get a known device by device_id."""
        device = self.devices.get(device_id)
        if not device:
            _LOGGER.warning(f"Unknown device: {device_id}")
        return device

    async def _async_save_module_metadata(
        self,
        device_id: str,
        sw_version: str,
        module_type: Optional[int],
        ns: Optional[int],
        na: Optional[int],
        nm: Optional[int],
        ng: Optional[int],
    ):
        """Persist module metadata (sw_version, type, na, ng, etc.) to config options.
        Ensures module data is never missing after restart or comparison quirks."""
        if not self._entry:
            return
        try:
            devices = dict(self._entry.options.get("devices", {}))
            if device_id not in devices:
                _LOGGER.debug(
                    "[module metadata] device_id=%s not in options, skipping save",
                    device_id,
                )
                return
            dev = devices[device_id]
            dev["sw_version"] = sw_version or dev.get("sw_version", "")
            if module_type is not None:
                dev["module_type"] = module_type
            if ns is not None:
                dev["ns"] = ns
            if na is not None:
                dev["na"] = na
            if nm is not None:
                dev["nm"] = nm
            if ng is not None:
                dev["ng"] = ng
            new_options = dict(self._entry.options)
            new_options["devices"] = devices
            self._hass.config_entries.async_update_entry(self._entry, options=new_options)
            _LOGGER.debug(
                "[module metadata] Saved for %s: sw_version=%s type=%s na=%s ng=%s",
                device_id, sw_version, module_type, na, ng,
            )
        except Exception as e:
            _LOGGER.warning("Failed to save module metadata for %s: %s", device_id, e)

    async def _async_save_device_detail_status(self, device_id: str, status: str):
        """Save detail_status in Config Entry Options."""
        if not self._entry:
            return
        
        try:
            devices = dict(self._entry.options.get("devices", {}))
            if device_id in devices:
                devices[device_id]["detail_status"] = status
                devices[device_id]["detail_retry_count"] = self.devices[device_id].detail_retry_count
                if self.devices[device_id].last_detail_request:
                    devices[device_id]["last_detail_request"] = self.devices[device_id].last_detail_request.isoformat()
                
                # Update Config Entry
                new_options = dict(self._entry.options)
                new_options["devices"] = devices
                self._hass.config_entries.async_update_entry(self._entry, options=new_options)
                _LOGGER.debug(f"Saved detail_status={status} for {device_id}")
        except Exception as e:
            _LOGGER.error(f"Failed to save detail_status for {device_id}: {e}")

    async def _async_save_actor_settings(self, device_id: str, **fields) -> None:
        """Keep power-up, minimum brightness and state-change flag across a restart.

        Only the keys passed in are written. A value of 0 or False is stored.
        """
        device = self.devices.get(device_id)
        if device is None:
            _LOGGER.warning("Device %s not found, cannot store actor settings", device_id)
            return
        for key, value in fields.items():
            setattr(device, key, value)
        async_dispatcher_send(self._hass, f"net4home_diagnostic_update_{device_id}")
        if not self._entry or not fields:
            return
        try:
            devices = dict(self._entry.options.get("devices", {}))
            if device_id not in devices:
                return
            stored = dict(devices[device_id])
            changed = False
            for key, value in fields.items():
                if stored.get(key) != value:
                    stored[key] = value
                    changed = True
            if not changed:
                return
            devices[device_id] = stored
            options = dict(self._entry.options)
            options["devices"] = devices
            self._hass.config_entries.async_update_entry(self._entry, options=options)
            _LOGGER.debug("Saved actor settings for %s: %s", device_id, fields)
        except Exception as e:
            _LOGGER.error("Failed to save actor settings for %s: %s", device_id, e)

    async def _async_save_device_timer_time1(self, device_id: str, timer_time1: int):
        """Save timer_time1 in Config Entry Options (for cover run time and switch timer)."""
        if not self._entry:
            return
        try:
            devices = dict(self._entry.options.get("devices", {}))
            if device_id in devices:
                devices[device_id]["timer_time1"] = timer_time1
                new_options = dict(self._entry.options)
                new_options["devices"] = devices
                self._hass.config_entries.async_update_entry(self._entry, options=new_options)
                _LOGGER.debug(f"Saved timer_time1={timer_time1} for {device_id}")
            else:
                _LOGGER.debug(
                    "[timer_time1 save] device_id=%r not in options (sample keys: %s)",
                    device_id, list(devices.keys())[:15],
                )
        except Exception as e:
            _LOGGER.error(f"Failed to save timer_time1 for {device_id}: {e}")
