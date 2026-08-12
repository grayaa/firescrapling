"""URL validation for API requests (SSRF mitigation)."""
from __future__ import annotations

import ipaddress
import os
import socket
from typing import Optional
from urllib.parse import urlparse

# RFC 1918, loopback, link-local, unique local, etc.
_DISALLOW_NETWORKS = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("::ffff:0:0/96"),  # IPv4-mapped — checked after IPv4 resolution
)


def allow_private_urls() -> bool:
    return os.environ.get("API_ALLOW_PRIVATE_URLS", "").strip() in ("1", "true", "yes")


def _host_is_blocked_ip(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return True
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if ip.version == 4:
            for net in _DISALLOW_NETWORKS:
                if net.version == 4 and ip in net:
                    return True
        if ip.version == 6:
            for net in _DISALLOW_NETWORKS:
                if net.version == 6 and ip in net:
                    return True
    return False


def validate_request_url(url: str, *, force_public_only: bool = False) -> Optional[str]:
    """
    Return None if URL is allowed for server-side fetch, else an error message.
    If force_public_only is True, private/local targets are never allowed (for public playground).
    """
    if not url or not isinstance(url, str):
        return "URL is required"
    u = url.strip()
    if len(u) > 8192:
        return "URL too long"
    parsed = urlparse(u)
    if parsed.scheme not in ("http", "https"):
        return "Only http and https URLs are allowed"
    if not parsed.netloc:
        return "Invalid URL"
    host = parsed.hostname
    if not host:
        return "Invalid host"
    if allow_private_urls() and not force_public_only:
        return None
    # Block obvious local hostnames without DNS
    hl = host.lower()
    if hl in ("localhost", "0.0.0.0") or hl.endswith(".local"):
        return "Requests to local or private hosts are not allowed"
    if _host_is_blocked_ip(host):
        return "Requests to private or loopback addresses are not allowed"
    return None
