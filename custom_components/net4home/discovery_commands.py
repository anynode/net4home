"""ENUM_ALL and the module detail queue."""
import asyncio
import logging
import time
from datetime import datetime

from .const import (
    D0_ENABLE_CONFIGURATION,
    D0_ENUM_ALL,
    D0_GET_TYP,
    D0_RD_ACTOR_DATA,
    D0_RD_ACTOR_DATA_ACK,
    D0_RD_MODULSPEC_DATA,
    D0_RD_SENSOR_DATA,
    D0_RD_SENSOR_DATA_ACK,
    D0_REQ,
    D1_ENABLE_CONFIGURATION_OK_BYTE,
    MI_ENUM_ALL,
    PLATINE_HW_IS_BELL2,
    PLATINE_HW_IS_LCD3,
    SEND_AS_IP,
)
from .models import Net4HomeDevice

_LOGGER = logging.getLogger(__name__)

class DiscoveryCommands:
    """ENUM_ALL and the module detail queue."""

    async def _enum_timeout_handler(self):
        """Handle ENUM_ALL timeout - start next round or complete enumeration."""
        if self._enum_state == 0:
            return
        
        if self._enum_state < 3:
            # Start next round
            self._enum_state += 1
            _LOGGER.debug(f"[ENUM_ALL] Timeout after round {self._enum_state - 1}, starting round {self._enum_state}")
            await self._send_enum_all_round()
        else:
            # Enumeration complete
            _LOGGER.debug(f"[ENUM_ALL] All 3 rounds completed, enumeration finished")
            self._enum_state = 0
            _LOGGER.debug("[ENUM_ALL] Detail retrieval can now continue")
        
        self._enum_timeout_task = None

    async def _send_enum_all_round(self):
        """Send a single ENUM_ALL round and start timeout timer."""
        try:
            ipdst = MI_ENUM_ALL
            ddata = bytes([D0_ENUM_ALL])
            objsource = 0
            
            _LOGGER.debug(f"[ENUM_ALL] Sending round {self._enum_state}")
            await self._packet_sender.send_raw_command(
                ipdst=ipdst,
                ddata=ddata,
                objsource=objsource,
                mi=self._mi,
                type8=SEND_AS_IP,
            )
            
            # Start timeout timer
            self._enum_timeout_task = asyncio.create_task(
                self._wait_for_timeout()
            )
        except Exception as e:
            _LOGGER.error(f"[ENUM_ALL] Error sending ENUM_ALL round: {e}", exc_info=True)
            self._enum_state = 0
            self._enum_timeout_task = None

    async def _wait_for_timeout(self):
        """Wait for timeout period and then call timeout handler."""
        try:
            await asyncio.sleep(self._enum_timeout_seconds)
            await self._enum_timeout_handler()
        except asyncio.CancelledError:
            # Task was cancelled (timer reset), this is expected
            pass

    async def send_enum_all(self):
        """
        Send a device discovery to the bus.
        
        For small systems (≤250 modules): 3 rounds with 500ms timeout.
        ENUM_ALL is sent to MI address 0xFFFF (MIFFFF).
        - ipdst: MI_ENUM_ALL (0xFFFF = 65535) - MI address for ENUM_ALL
        - mi: MI address of sender (configurator)
        - objsource: 0 (no OBJ address, as it is a module command)
        - ddata: Only [D0_ENUM_ALL] (one byte, value 0x02)
        
        All modules on the bus respond with D0_ACK_TYP.
        """
        # Check if enumeration is already in progress
        if self._enum_state > 0:
            _LOGGER.warning("[ENUM_ALL] Enumeration already in progress, ignoring request")
            return
        
        try:
            # Initialize enumeration state
            self._enum_state = 1
            
            # Start first round
            await self._send_enum_all_round()

        except Exception as e:
            _LOGGER.error(f"[ENUM_ALL] Error starting ENUM_ALL: {e}", exc_info=True)
            self._enum_state = 0
            if self._enum_timeout_task:
                self._enum_timeout_task.cancel()
                self._enum_timeout_task = None

    async def async_wait_for_enumeration(self, timeout: float = 120) -> None:
        """Wait until a running ENUM_ALL has finished."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while self._enum_state > 0 and loop.time() < deadline:
            await asyncio.sleep(0.1)
        if self._enum_state > 0:
            _LOGGER.warning(
                "[ENUM_ALL] Still running after %.0fs, continuing startup", timeout
            )

    async def async_wait_for_detail_queue(self, timeout: float = 900) -> None:
        """Wait until no device is waiting for its module info.

        A short quiet period covers a device that is queued a moment later,
        for example a channel created while its module is still being read.
        """
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        quiet_since = None
        while loop.time() < deadline:
            busy = self._detail_queue is not None and not self._detail_queue.empty()
            if not busy:
                busy = any(
                    device.detail_status in ("pending", "in_progress")
                    for device in self.devices.values()
                )
            if not busy:
                if quiet_since is None:
                    quiet_since = loop.time()
                elif loop.time() - quiet_since >= 2:
                    return
            else:
                quiet_since = None
            await asyncio.sleep(0.5)
        _LOGGER.warning(
            "Module info still running after %.0fs, continuing startup", timeout
        )

    async def async_start_detail_retrieval(self):
        """Start the continuous detail queue manager."""
        if self._detail_queue_running:
            _LOGGER.debug("Detail queue already running")
            return
        
        if self._detail_queue is None:
            self._detail_queue = asyncio.Queue()
        
        self._detail_queue_running = True
        self._detail_queue_task = asyncio.create_task(self._async_process_detail_queue())
        _LOGGER.info("Detail retrieval queue manager started")
        
        # On start: Load all pending devices into queue
        await self._async_load_pending_devices_to_queue()

    async def async_stop_detail_retrieval(self):
        """Stop the detail queue manager."""
        self._detail_queue_running = False
        if self._detail_queue_task:
            self._detail_queue_task.cancel()
            try:
                await self._detail_queue_task
            except asyncio.CancelledError:
                pass
        _LOGGER.info("Detail retrieval queue manager stopped")

    async def async_queue_device_for_details(self, device_id: str):
        """Add a device to the detail queue (called at D0_ACK_TYP)."""
        device = self.devices.get(device_id)
        if not device:
            _LOGGER.warning(f"Device {device_id} not found for detail queue")
            return
        
        # A running read already asked the module for its type. Queueing
        # again from that reply starts the same read a second time.
        if device.detail_status in ("completed", "in_progress"):
            _LOGGER.debug(
                "Device %s detail read is %s, not queueing again",
                device_id,
                device.detail_status,
            )
            return
        
        # Setze Status auf pending (nur wenn noch nicht completed)
        device.detail_status = "pending"
        device.discovered_at = datetime.now()
        
        # Speichere Status in Config Entry
        await self._async_save_device_detail_status(device_id, "pending")
        
        # Add to queue (if queue is running)
        if self._detail_queue is not None:
            await self._detail_queue.put(device_id)
            _LOGGER.info(f"Device {device_id} ({device.model}) queued for detail retrieval")
        else:
            _LOGGER.warning(f"Detail queue not initialized, cannot queue {device_id}")

    async def _async_process_detail_queue(self):
        """Main loop for detail queue processing."""
        initial_delay_applied = False
        _LOGGER.debug("Detail queue worker loop started")
        
        while self._detail_queue_running:
            try:
                # Wait if ENUM_ALL is active
                if self._enum_state > 0:
                    _LOGGER.debug(f"ENUM_ALL in progress (state={self._enum_state}), pausing detail retrieval")
                    await asyncio.sleep(0.5)  # Check every 500ms
                    continue
                
                # Initial delay beim ersten Start (nur wenn ENUM_ALL nicht aktiv war)
                if not initial_delay_applied:
                    _LOGGER.debug(f"Applying initial delay of {self._detail_initial_delay} seconds")
                    await asyncio.sleep(self._detail_initial_delay)
                    initial_delay_applied = True
                    _LOGGER.debug("Initial delay completed, starting detail retrieval")
                
                # Wait for device in queue (with timeout for graceful shutdown)
                try:
                    _LOGGER.debug(f"Waiting for device from queue (queue size: {self._detail_queue.qsize() if self._detail_queue else 'N/A'})")
                    device_id = await asyncio.wait_for(
                        self._detail_queue.get(), 
                        timeout=1.0
                    )
                    _LOGGER.info(f"Processing device {device_id} from detail queue")
                except asyncio.TimeoutError:
                    continue
                
                # Process device
                _LOGGER.debug(f"Calling _async_fetch_device_details for {device_id}")
                await self._async_fetch_device_details(device_id)
                
                # Rate limiting: Wait between queries (increased to avoid bus overload)
                await asyncio.sleep(self._detail_rate_limit)
                
            except asyncio.CancelledError:
                _LOGGER.debug("Detail queue processing cancelled")
                break
            except Exception as e:
                _LOGGER.error(f"Error in detail queue processing: {e}", exc_info=True)
                await asyncio.sleep(1.0)  # Pause on error (reduced for more traffic)

    async def _async_refresh_module_values(self, device: Net4HomeDevice) -> None:
        """Ask a module and its channels for the values they hold right now."""
        if self._packet_sender is None:
            return
        if device.device_type == "climate" and device.objadr:
            await self.async_request_status(device.device_id)
            await asyncio.sleep(0.05)
        if device.model == "HS-Time":
            await self._async_query_hs_time(device)
        if device.model == "HS-Safety":
            await self._async_request_alarm_status(device.device_id)
        refreshed = 0
        for child in list(self.devices.values()):
            if child.via_device != device.device_id or not child.objadr:
                continue
            if child.device_type not in (
                "light",
                "switch",
                "cover",
                "binary_sensor",
                "sensor",
            ):
                continue
            await self.async_request_status(child.device_id)
            refreshed += 1
            await asyncio.sleep(0.05)
        _LOGGER.info(
            "Read %s (%s) requested %s current values",
            device.device_id,
            device.model,
            refreshed,
        )

    async def _async_fetch_device_details(self, device_id: str):
        """Perform detail query for a device."""
        device = self.devices.get(device_id)
        if not device:
            _LOGGER.warning(f"Device {device_id} not found for detail retrieval")
            return
        
        # Check if details have already been successfully retrieved
        if device.detail_status == "completed":
            _LOGGER.debug(f"Device {device_id} already has completed detail retrieval, skipping")
            return
        
        device.detail_status = "in_progress"
        device.last_detail_request = datetime.now()
        await self._async_save_device_detail_status(device_id, "in_progress")
        
        try:
            _LOGGER.debug(f"Fetching details for device {device_id} ({device.model}, type: {device.device_type})")
            
            # Distinguish between MI devices (modules) and OBJ devices (child devices)
            # IMPORTANT: A device with via_device is ALWAYS an OBJ device (child device),
            # even if device_id starts with "MI". Only devices WITHOUT via_device
            # and with device_id.startswith("MI") are real MI devices (modules).
            if device.via_device:
                # Device has via_device -> it is an OBJ device (child device)
                is_mi_device = False
                is_obj_device = True
            else:
                # Device has no via_device -> check device_id
                is_mi_device = device_id.startswith("MI")
                is_obj_device = device_id.startswith("OBJ")
            
            if is_mi_device:
                # The konfigurator asks the module for its type before it reads
                # any table. Stored counts can be empty after a restart.
                mi_addr = int(device_id[2:], 16)
                asked_at = time.monotonic()
                device.ack_typ_at = 0
                await self._packet_sender.send_raw_command(
                    ipdst=mi_addr,
                    ddata=bytes([D0_GET_TYP]),
                    objsource=self._objadr,
                    mi=self._mi,
                    type8=SEND_AS_IP,
                )
                for _ in range(20):
                    if getattr(device, "ack_typ_at", 0) >= asked_at:
                        break
                    await asyncio.sleep(0.05)
                else:
                    _LOGGER.info(
                        "%s did not answer D0_GET_TYP, using stored counts ns=%s na=%s nm=%s",
                        device_id,
                        device.ns,
                        device.na,
                        device.nm,
                    )

                if device.module_type is None or (device.ns is None and device.na is None and device.nm is None):
                    _LOGGER.warning(
                        f"Module type information not yet available for {device_id}, "
                        f"skipping detail queries. module_type={device.module_type}, "
                        f"ns={device.ns}, na={device.na}, nm={device.nm}"
                    )
                    device.detail_status = "pending"
                    await self._async_save_device_detail_status(device_id, "pending")
                    return

                _LOGGER.info(
                    "Reading %s (%s) ns=%s na=%s nm=%s",
                    device_id,
                    device.model,
                    device.ns,
                    device.na,
                    device.nm,
                )
                
                # Aktiviere Konfigurationsmodus vor den Detailabfragen
                _LOGGER.debug(f"Enabling configuration mode for {device_id} (MI={mi_addr:04X})")
                await self._packet_sender.send_raw_command(
                    ipdst=mi_addr,
                    ddata=bytes([D0_ENABLE_CONFIGURATION, D1_ENABLE_CONFIGURATION_OK_BYTE]),
                    objsource=self._objadr,
                    mi=self._mi,
                    type8=SEND_AS_IP,  
                )
                
                _LOGGER.debug(f"Configuration mode enabled for {device_id}")
           
           
                # Basierend auf Modultyp-Eigenschaften Abfragen senden xxx
                # 1. Aktoren abfragen (wenn na > 0)
                
                if device.na and device.na > 0:
                    await self._async_read_table_lines(
                        mi_addr,
                        D0_RD_ACTOR_DATA,
                        D0_RD_ACTOR_DATA_ACK,
                        device.na,
                        "Actor",
                    )

                # 2. Sensoren abfragen (wenn ns > 0). One line at a time:
                # the module replaces an unanswered read with the next request.
                if device.ns and device.ns > 0:
                    await self._async_read_table_lines(
                        mi_addr,
                        D0_RD_SENSOR_DATA,
                        D0_RD_SENSOR_DATA_ACK,
                        device.ns,
                        "Sensor",
                    )
                
                # Warte zwischen Aktor- und Sensor-Abfragen
                if device.na and device.na > 0 and device.ns and device.ns > 0:
                    await asyncio.sleep(0.3)
                
                # 3. ModulSpec. Special modules keep a base address even when
                # the stored table length is 0, so they are not skipped.
                needs_modulspec = (device.nm or 0) > 0 or device.model in (
                    "UP-TLH",
                    "UP-T",
                    "HS-Time",
                    "HS-Safety",
                    "EXT-LD",
                    ".WAV-Bell",
                    "UP-LCD",
                ) or device.module_type in (PLATINE_HW_IS_BELL2, PLATINE_HW_IS_LCD3)
                if needs_modulspec:
                    # Special case: UP-TLH and UP-T need ModulSpec data for all 3 sensors (index 0, 1, 2)
                    # as well as special indices 0xF0 (day/night preset) and 0xF1 (heat/cool object addresses)
                    if device.model in ('UP-TLH', 'UP-T'):
                        # Base address first. Sensor channels 0..2 need it on firmware >= 1.17.
                        device.tlh_f1_reply = None
                        await self._packet_sender.send_raw_command(
                            ipdst=mi_addr,
                            ddata=bytes([D0_RD_MODULSPEC_DATA, 0xF1]),
                            objsource=self._objadr,
                            mi=self._mi,
                            type8=SEND_AS_IP,
                        )
                        for _ in range(40):
                            if device.objadr or getattr(device, "tlh_f1_reply", None) == 0:
                                break
                            await asyncio.sleep(0.05)

                        if not device.objadr and getattr(device, "tlh_f1_reply", None) != 0:
                            device.detail_retry_count += 1
                            if device.detail_retry_count < 3:
                                _LOGGER.warning(
                                    "0xF1 for %s has not arrived, retrying (%s/3)",
                                    device_id,
                                    device.detail_retry_count,
                                )
                                device.detail_status = "pending"
                                await self._async_save_device_detail_status(device_id, "pending")
                                if self._detail_queue is not None:
                                    await self._detail_queue.put(device_id)
                                return
                            _LOGGER.warning(
                                f"Cannot send D0_REQ for {device_id}: objadr not yet set (0xF1 packet may not have arrived)"
                            )

                        await self._packet_sender.send_raw_command(
                            ipdst=mi_addr,
                            ddata=bytes([D0_RD_MODULSPEC_DATA, 0xF0]),
                            objsource=self._objadr,
                            mi=self._mi,
                            type8=SEND_AS_IP,
                        )
                        await asyncio.sleep(0.1)

                        for modulspec_index in range(3):
                            await self._packet_sender.send_raw_command(
                                ipdst=mi_addr,
                                ddata=bytes([D0_RD_MODULSPEC_DATA, modulspec_index]),
                                objsource=self._objadr,
                                mi=self._mi,
                                type8=SEND_AS_IP,
                            )
                            if modulspec_index < 2:
                                await asyncio.sleep(0.2)

                        if device.objadr is not None:
                            await self._packet_sender.send_raw_command(
                                ipdst=device.objadr,
                                ddata=bytes([D0_REQ, 0x00, 0x00]),
                                objsource=self._objadr,
                                mi=self._mi,
                            )
                            _LOGGER.debug(f"Sent D0_REQ for targettemp to {device_id} (OBJ={device.objadr})")
                        _LOGGER.debug(f"Sent D0_RD_MODULSPEC_DATA for {device_id} (UP-TLH/UP-T, 0xF1, 0xF0, 3 sensors)")
                    elif device.model == "HS-Time":
                        # For HS-Time: Query for module info (0xFF) to get base address
                        await self._packet_sender.send_raw_command(
                            ipdst=mi_addr,
                            ddata=bytes([D0_RD_MODULSPEC_DATA, 0xFF]),
                            objsource=self._objadr,
                            mi=self._mi,
                            type8=SEND_AS_IP,
                        )
                        _LOGGER.debug(f"Sent D0_RD_MODULSPEC_DATA for {device_id} (HS-Time, 0xFF for Modul-Info)")
                        await asyncio.sleep(0.2)
                    elif device.model == ".WAV-Bell" or device.module_type == PLATINE_HW_IS_BELL2:
                        await self.async_load_bell_config(device, force=True)
                    elif device.model == "HS-Safety":
                        await self._packet_sender.send_raw_command(
                            ipdst=mi_addr,
                            ddata=bytes([D0_RD_MODULSPEC_DATA, 0x00]),
                            objsource=self._objadr,
                            mi=self._mi,
                            type8=SEND_AS_IP,
                        )
                        for _ in range(40):
                            if device.objadr and device.objadr > 0:
                                break
                            await asyncio.sleep(0.05)
                        if device.objadr and device.objadr > 0:
                            await self._async_request_alarm_status(device_id)
                            _LOGGER.info(
                                "HS-Safety %s status requested at object %s",
                                device_id,
                                device.objadr,
                            )
                        else:
                            _LOGGER.warning(
                                "HS-Safety %s has no base address after reading modulspec line 0",
                                device_id,
                            )
                    elif device.model == "UP-LCD" or device.module_type == PLATINE_HW_IS_LCD3:
                        await self.async_ensure_lcd_address(device)
                    else:
                        # The konfigurator reads every modulspec line, 0 .. nm-1.
                        line_count = min(int(device.nm or 0), 16)
                        for line in range(line_count):
                            await self._packet_sender.send_raw_command(
                                ipdst=mi_addr,
                                ddata=bytes([D0_RD_MODULSPEC_DATA, line, 0x00]),
                                objsource=self._objadr,
                                mi=self._mi,
                                type8=SEND_AS_IP,
                            )
                            await asyncio.sleep(0.1)
                        if (device.nm or 0) > line_count:
                            _LOGGER.info(
                                "%s modulspec has %s lines, read the first %s",
                                device_id,
                                device.nm,
                                line_count,
                            )
                
                # Warte zwischen Sensor- und ModulSpec-Abfragen
                if device.ns and device.ns > 0 and needs_modulspec:
                    await asyncio.sleep(0.3)
                
                # Wait additionally so all responses can be processed
                # before we mark the device as "completed"
                await asyncio.sleep(0.1)
                await self._async_refresh_module_values(device)
                
                _LOGGER.debug(f"Hardware type-specific detail queries for {device_id} completed")
            elif is_obj_device:
                # OBJ devices (child devices) need status query
                # Perform detail queries based on device type
                if device.device_type in ("light", "switch", "cover"):
                    # For actors: Query status (D0_REQ leads to D0_ACTOR_ACK)
                    await self.async_request_status(device_id)
                elif device.device_type == "climate":
                    # For climate: Query status
                    await self.async_request_status(device_id)
                elif device.device_type == "binary_sensor":
                    # For binary sensors: Query status
                    await self.async_request_status(device_id)
                elif device.device_type == "sensor":
                    # For sensors: Query status
                    await self.async_request_status(device_id)
                else:
                    # For unknown types: Query status
                    await self.async_request_status(device_id)
            else:
                # Unbekanntes Format - markiere als completed
                _LOGGER.warning(f"Unknown device ID format: {device_id}")
            
            # Mark as completed (for MI devices already set, for OBJ devices after status query)
            device.detail_status = "completed"
            device.detail_retry_count = 0
            await self._async_save_device_detail_status(device_id, "completed")
            _LOGGER.debug(f"Detail retrieval completed for {device_id}")
            
        except Exception as e:
            device.detail_retry_count += 1
            if device.detail_retry_count < 3:
                device.detail_status = "pending"
                await self._async_save_device_detail_status(device_id, "pending")
                # Back to queue with delay
                retry_delay = 3.0 * device.detail_retry_count  # Exponential backoff (reduced for more traffic)
                _LOGGER.warning(
                    f"Detail retrieval failed for {device_id}, retrying ({device.detail_retry_count}/3) "
                    f"after {retry_delay}s: {e}"
                )
                await asyncio.sleep(retry_delay)
                if self._detail_queue is not None:
                    await self._detail_queue.put(device_id)
            else:
                device.detail_status = "failed"
                await self._async_save_device_detail_status(device_id, "failed")
                _LOGGER.error(f"Detail retrieval failed for {device_id} after 3 retries: {e}")

    async def _async_load_pending_devices_to_queue(self):
        """Load all pending devices into the queue on start."""
        if not self.read_module_info_on_startup:
            _LOGGER.info("Module info read on startup is off, pending modules stay unread")
            return
        pending_count = 0
        for device_id, device in self.devices.items():
            if device.detail_status in ("pending", "in_progress"):
                if self._detail_queue is not None:
                    await self._detail_queue.put(device_id)
                    pending_count += 1
                    _LOGGER.debug(f"Restored pending device {device_id} to detail queue")
        
        if pending_count > 0:
            _LOGGER.info(f"Restored {pending_count} pending devices to detail queue")
