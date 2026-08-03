"""Host:port formatting and parsing that doesn't break on IPv6
addresses, which use bracket notation (``[::1]:9000``) precisely because
a bare ``rsplit(":", 1)`` can't tell an address colon from a port colon.
"""

from __future__ import annotations


def format_addr(host: str, port: int) -> str:
    if ":" in host:
        return f"[{host}]:{port}"
    return f"{host}:{port}"


def split_addr(addr: str) -> tuple[str, int]:
    if addr.startswith("["):
        host, _, rest = addr[1:].partition("]:")
        return host, int(rest)
    host, port = addr.rsplit(":", 1)
    return host, int(port)
