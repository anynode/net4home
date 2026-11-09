"""Find the local net4home service published by the add-on.

The add-on announces service name ``net4home``. That name stays when the
add-on repository, and therefore its slug prefix, changes.
"""

from __future__ import annotations

SERVICE = "net4home"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 3478


def endpoint_from_config(config: dict | None) -> dict:
    """Return host and port from a discovery config object."""
    config = config or {}
    host = config.get("host") or DEFAULT_HOST
    port = config.get("port") or DEFAULT_PORT
    try:
        port = int(port)
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    return {"host": str(host), "port": port}


def local_endpoint_from_discovery(items) -> dict | None:
    """Return the local endpoint from Supervisor discovery messages."""
    for item in items:
        service = getattr(item, "service", None)
        config = getattr(item, "config", None)
        if service is None and isinstance(item, dict):
            service = item.get("service")
            config = item.get("config")
        if service != SERVICE:
            continue
        if not isinstance(config, dict):
            config = {}
        return endpoint_from_config(config)
    return None
