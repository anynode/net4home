"""Group tables stored on the switching modules.

A used line says which actor channel of that module follows one group
address. The same address on twenty modules is one group with twenty
members. The module stores no name, only the address and the channel.
"""

MIN_GROUP_ADDRESS = 0x8001
MAX_GROUP_ADDRESS = 0xFFFE


def parse_group_line(payload: bytes) -> dict | None:
    """Return one membership from a D0_RD_GRP_DATA_ACK payload.

    The payload is the full reply: command, line index, used flag,
    address high, address low, channel. An unused line has used flag 0.
    Bit 7 of the channel marks an input memory, not an output.
    """
    if len(payload) < 6 or payload[2] != 1:
        return None
    address = ((payload[3] << 8) | payload[4]) | 0x8000
    if address < MIN_GROUP_ADDRESS or address > MAX_GROUP_ADDRESS:
        return None
    raw_channel = payload[5]
    return {
        "index": payload[1],
        "address": address,
        "number": address & 0x7FFF,
        "channel": raw_channel & 0x7F,
        "input_memory": bool(raw_channel & 0x80),
    }


def group_label(address: int) -> str:
    """G123 for the bus address 0x8000 + 123."""
    return f"G{address & 0x7FFF}"


def group_default_name(number: int) -> str:
    """Start name. Users rename the entity in Home Assistant; the bus has no name."""
    return f"Gruppe {number}"


def actor_channel_of(device) -> int | None:
    """Return the 0-based actor channel stored on a device, or parsed from CHn_."""
    channel = getattr(device, "actor_channel", None)
    if isinstance(channel, int):
        return channel
    name = getattr(device, "name", "") or ""
    if name.startswith("CH") and "_" in name:
        number = name[2:name.index("_")]
        if number.isdigit() and int(number) > 0:
            return int(number) - 1
    return None


def _member(module_id: str, channel: int, devices: dict) -> dict:
    """Find the actor device that owns this module channel."""
    found = None
    for candidate in devices.values():
        via = (getattr(candidate, "via_device", None) or "").upper()
        if via != module_id.upper():
            continue
        if actor_channel_of(candidate) == channel:
            found = candidate
            break
    if found is None:
        return {
            "module": module_id,
            "channel": channel,
            "device_id": None,
            "name": f"{module_id} CH{channel + 1}",
            "device_type": None,
        }
    return {
        "module": module_id,
        "channel": channel,
        "device_id": found.device_id,
        "name": found.name,
        "device_type": found.device_type,
    }


def _kind(members: list[dict]) -> str:
    """Light, cover, or a plain on/off switch when the members differ."""
    resolved = {
        member["device_type"]
        for member in members
        if member.get("device_type") in ("light", "cover", "switch")
    }
    if resolved == {"light"}:
        return "light"
    if resolved == {"cover"}:
        return "cover"
    return "switch"


def index_groups(lines_by_module: dict, devices: dict) -> list[dict]:
    """Turn every module's used lines into one record per group address."""
    buckets: dict[int, list] = {}
    seen: set[tuple] = set()
    for module_id, lines in lines_by_module.items():
        for payload in lines.values():
            row = parse_group_line(payload)
            if row is None or row["input_memory"]:
                continue
            key = (module_id.upper(), row["channel"], row["address"])
            if key in seen:
                continue
            seen.add(key)
            buckets.setdefault(row["address"], []).append(
                _member(module_id, row["channel"], devices)
            )
    groups = []
    for address in sorted(buckets):
        members = buckets[address]
        number = address & 0x7FFF
        groups.append(
            {
                "address": address,
                "number": number,
                "label": group_label(address),
                "name": group_default_name(number),
                "members": members,
                "kind": _kind(members),
            }
        )
    return groups


def groups_for_device(groups, device_id: str) -> list:
    """Groups whose membership list contains this channel."""
    if not device_id:
        return []
    wanted = device_id.upper()
    found = []
    for group in groups or []:
        for member in group["members"]:
            member_id = member.get("device_id")
            if member_id and str(member_id).upper() == wanted:
                found.append(group)
                break
    return found


def labels_for(groups, device_id: str) -> str:
    """Comma-separated group addresses a channel belongs to."""
    return ", ".join(group["label"] for group in groups_for_device(groups, device_id))
