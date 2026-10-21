"""Bounded HTTP fetcher with manual redirect validation."""
from __future__ import annotations
import time
from urllib.parse import urljoin
import requests
from config import MAX_REDIRECTS, MAX_RESPONSE_BYTES, REQUEST_TIMEOUT_SECONDS, USER_AGENT
from modules.url_validator import URLValidationError, validate_public_destination

class FetchError(RuntimeError):
    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = category

def fetch_webpage(url: str) -> dict:
    current = validate_public_destination(url)
    start = time.monotonic()
    session = requests.Session()
    session.trust_env = False
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5"}
    try:
        for hop in range(MAX_REDIRECTS + 1):
            # Re-check every redirect target, including DNS resolution.
            current = validate_public_destination(current)
            try:
                response = session.get(
                    current, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS,
                    allow_redirects=False, stream=True, verify=True
                )
            except requests.Timeout as exc:
                raise FetchError("timeout", "The website did not respond before the timeout.") from exc
            except requests.RequestException as exc:
                raise FetchError("network", f"HTTP request failed: {type(exc).__name__}.") from exc

            if response.is_redirect or response.is_permanent_redirect:
                location = response.headers.get("Location")
                response.close()
                if not location:
                    raise FetchError("redirect", "Redirect response did not include a Location header.")
                if hop >= MAX_REDIRECTS:
                    raise FetchError("redirect_limit", "Maximum redirect count exceeded.")
                current = urljoin(current, location)
                try:
                    current = validate_public_destination(current)
                except URLValidationError as exc:
                    raise FetchError("unsafe_redirect", f"Redirect blocked: {exc}") from exc
                continue

            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type.lower() and "application/xhtml+xml" not in content_type.lower():
                response.close()
                raise FetchError("content_type", f"Expected HTML but received '{content_type or 'unknown content type'}'.")
            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    if int(content_length) > MAX_RESPONSE_BYTES:
                        response.close()
                        raise FetchError("size_limit", "Response exceeds the configured size limit.")
                except ValueError:
                    pass
            chunks, total = [], 0
            try:
                for chunk in response.iter_content(chunk_size=65536):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > MAX_RESPONSE_BYTES:
                        raise FetchError("size_limit", "Response exceeded the configured size limit.")
                    chunks.append(chunk)
            finally:
                response.close()
            encoding = response.encoding or "utf-8"
            html = b"".join(chunks).decode(encoding, errors="replace")
            return {
                "requested_url": url, "final_url": current, "status_code": response.status_code,
                "content_type": content_type, "html": html,
                "fetch_duration_seconds": round(time.monotonic() - start, 3),
                "redirect_count": hop, "error": None,
            }
        raise FetchError("redirect_limit", "Maximum redirect count exceeded.")
    finally:
        session.close()
