"""URL validation and public-destination checks for the MVP.

This is defense-in-depth, not a hardened production SSRF gateway. Network egress
controls are still required for deployment in a sensitive environment.
"""
from __future__ import annotations
import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit

class URLValidationError(ValueError):
    pass

def normalize_url(raw_url: str) -> str:
    if not isinstance(raw_url, str) or not raw_url.strip():
        raise URLValidationError("Enter a URL.")
    raw_url = raw_url.strip()
    if any(ord(ch) < 32 for ch in raw_url):
        raise URLValidationError("URL contains control characters.")
    if "://" not in raw_url:
        raw_url = "https://" + raw_url
    try:
        p = urlsplit(raw_url)
        port = p.port
    except ValueError as exc:
        raise URLValidationError("Malformed URL or invalid port.") from exc
    if p.scheme.lower() not in {"http", "https"}:
        raise URLValidationError("Only HTTP and HTTPS URLs are allowed.")
    if not p.hostname:
        raise URLValidationError("URL must include a hostname.")
    if p.username is not None or p.password is not None:
        raise URLValidationError("URLs containing usernames or passwords are not allowed.")
    host = p.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost") or host.endswith(".local"):
        raise URLValidationError("Local or internal hostnames are not allowed.")
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        ip = None
    if ip and not ip.is_global:
        raise URLValidationError("Private, loopback, link-local, or reserved IP addresses are not allowed.")
    netloc = host
    if ":" in host and not host.startswith("["):
        netloc = f"[{host}]"
    if port is not None:
        default = (p.scheme.lower() == "http" and port == 80) or (p.scheme.lower() == "https" and port == 443)
        if not default:
            netloc += f":{port}"
    path = p.path or "/"
    return urlunsplit((p.scheme.lower(), netloc, path, p.query, ""))

def validate_public_destination(url: str, resolve_dns: bool = True) -> str:
    """Normalize URL and reject hosts resolving to any non-global address."""
    normalized = normalize_url(url)
    host = urlsplit(normalized).hostname
    try:
        ip = ipaddress.ip_address(host)
        addresses = [ip]
    except ValueError:
        if not resolve_dns:
            return normalized
        try:
            records = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise URLValidationError(f"Hostname could not be resolved: {host}") from exc
        addresses = []
        for record in records:
            try:
                addresses.append(ipaddress.ip_address(record[4][0].split("%")[0]))
            except ValueError:
                continue
        if not addresses:
            raise URLValidationError("Hostname did not resolve to an IP address.")
    if any(not addr.is_global for addr in addresses):
        raise URLValidationError("Destination resolves to a private, loopback, link-local, or reserved IP address.")
    return normalized
