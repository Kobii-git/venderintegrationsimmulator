"""Shared validation and migration helpers for outbound HTTP URLs."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote, urlsplit, urlunsplit

EMBEDDED_CREDENTIALS_ERROR = (
    "URL must not include embedded credentials; configure authentication separately."
)


@dataclass(frozen=True)
class EmbeddedUrlCredentials:
    username: str | None
    password: str | None

    @property
    def complete(self) -> bool:
        return bool(self.username) and bool(self.password)


def get_embedded_url_credentials(url: str) -> EmbeddedUrlCredentials | None:
    """Return decoded URL user-info when either username or password is present."""
    try:
        parsed = urlsplit(url)
    except ValueError:
        return _fallback_embedded_url_credentials(url)
    if parsed.username is None and parsed.password is None:
        return _fallback_embedded_url_credentials(url) if not parsed.netloc else None
    return EmbeddedUrlCredentials(
        username=unquote(parsed.username) if parsed.username is not None else None,
        password=unquote(parsed.password) if parsed.password is not None else None,
    )


def reject_embedded_url_credentials(url: str) -> None:
    """Reject URLs that would store or expose credentials in user-info."""
    if get_embedded_url_credentials(url) is not None:
        raise ValueError(EMBEDDED_CREDENTIALS_ERROR)


def strip_embedded_url_credentials(url: str) -> str:
    """Remove user-info while preserving the original encoded host and port."""
    try:
        parsed = urlsplit(url)
    except ValueError:
        return _fallback_strip_user_info(url)
    if "@" not in parsed.netloc:
        return _fallback_strip_user_info(url)
    netloc = parsed.netloc.rsplit("@", 1)[1]
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def _fallback_embedded_url_credentials(url: str) -> EmbeddedUrlCredentials | None:
    authority = url.split("://", 1)[-1].split("/", 1)[0]
    if "@" not in authority:
        return None
    user_info = authority.rsplit("@", 1)[0]
    username, separator, password = user_info.partition(":")
    return EmbeddedUrlCredentials(
        username=unquote(username) if username else None,
        password=unquote(password) if separator and password else None,
    )


def _fallback_strip_user_info(url: str) -> str:
    prefix = ""
    remainder = url
    if "://" in url:
        scheme, remainder = url.split("://", 1)
        prefix = f"{scheme}://"
    authority, separator, path = remainder.partition("/")
    if "@" not in authority:
        return url
    sanitized = prefix + authority.rsplit("@", 1)[1]
    return sanitized + (separator + path if separator else "")
