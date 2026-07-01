"""Guardrails for outbound database connection attempts."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import logging
import socket
import time
from typing import Iterable

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.errors import AppError, BadRequestError, ServiceUnavailableError
from app.db.models.connection import ConnectionRequest

logger = logging.getLogger(__name__)


class RateLimitError(AppError):
    def __init__(self, message: str = "Too many database connection attempts. Please wait and try again.") -> None:
        super().__init__(message, code="rate_limited", status_code=429)


@dataclass(frozen=True)
class ConnectionAttemptTarget:
    host: str | None
    port: int | None
    target_kind: str


_DEFAULT_PORTS = {
    "postgresql": 5432,
    "mysql": 3306,
    "mariadb": 3306,
    "sqlserver": 1433,
    "mssql": 1433,
}

_METADATA_HOSTS = {
    "metadata",
    "metadata.google.internal",
    "169.254.169.254",
    "100.100.100.200",
}

_METADATA_IPS = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("100.100.100.200"),
}

_memory_rate_limits: dict[str, tuple[int, float]] = {}


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _normalize_host(host: str | None) -> str:
    return (host or "").strip().strip("[]").rstrip(".").lower()


def _allowed_hosts() -> set[str]:
    return {_normalize_host(host) for host in settings.db_connect_allowed_hosts}


def _allowed_networks() -> list[ipaddress._BaseNetwork]:
    networks: list[ipaddress._BaseNetwork] = []
    for cidr in settings.db_connect_allowed_cidrs:
        try:
            networks.append(ipaddress.ip_network(cidr, strict=False))
        except ValueError:
            logger.warning("Ignoring invalid DB_CONNECT_ALLOWED_CIDRS entry: %s", cidr)
    return networks


def connection_attempt_target(config: ConnectionRequest) -> ConnectionAttemptTarget:
    if config.use_ssh:
        return ConnectionAttemptTarget(config.ssh_host, config.ssh_port or 22, "ssh_host")
    return ConnectionAttemptTarget(config.host, config.port or _DEFAULT_PORTS.get(config.db_type), "database_host")


def _literal_ip(host: str) -> ipaddress._BaseAddress | None:
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None


def _resolve_ips(host: str, port: int | None) -> list[ipaddress._BaseAddress]:
    literal = _literal_ip(host)
    if literal is not None:
        return [literal]

    try:
        infos = socket.getaddrinfo(host, port or 0, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return []

    ips: list[ipaddress._BaseAddress] = []
    for info in infos:
        address = info[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            continue
        if ip not in ips:
            ips.append(ip)
    return ips


def _is_metadata_ip(ip: ipaddress._BaseAddress) -> bool:
    return ip in _METADATA_IPS


def _is_blocked_ip(ip: ipaddress._BaseAddress) -> bool:
    return (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
    )


def _is_allowed_ip(ip: ipaddress._BaseAddress, networks: Iterable[ipaddress._BaseNetwork]) -> bool:
    return any(ip in network for network in networks)


def validate_connection_target(config: ConnectionRequest) -> None:
    if config.db_type == "sqlite":
        return

    target = connection_attempt_target(config)
    host = _normalize_host(target.host)
    if not host:
        raise BadRequestError("Database host is required.")
    if target.port is not None and not 1 <= int(target.port) <= 65535:
        raise BadRequestError("Database port is invalid.")

    if host in _METADATA_HOSTS:
        raise BadRequestError("Database target is blocked by connection security policy.")

    if host in _allowed_hosts():
        return

    allowed_networks = _allowed_networks()
    ips = _resolve_ips(host, target.port)

    for ip in ips:
        if _is_metadata_ip(ip):
            raise BadRequestError("Database target is blocked by connection security policy.")

    allow_private = not settings.is_production and settings.db_connect_allow_private_in_dev
    if allow_private:
        return

    for ip in ips:
        if _is_blocked_ip(ip) and not _is_allowed_ip(ip, allowed_networks):
            raise BadRequestError("Database target is blocked by connection security policy.")


def get_redis_client() -> Redis | None:
    redis_url = settings.resolved_redis_url
    if not redis_url:
        return None
    return Redis.from_url(redis_url, decode_responses=True)


def _enforce_memory_rate_limit(owner_id: str) -> None:
    limit = settings.db_connect_rate_limit_attempts
    window = settings.db_connect_rate_limit_window_seconds
    if limit <= 0 or window <= 0:
        return

    now = time.monotonic()
    count, reset_at = _memory_rate_limits.get(owner_id, (0, now + window))
    if now >= reset_at:
        count = 0
        reset_at = now + window
    count += 1
    _memory_rate_limits[owner_id] = (count, reset_at)
    if count > limit:
        raise RateLimitError()


def enforce_connection_attempt_rate_limit(owner_id: str) -> None:
    limit = settings.db_connect_rate_limit_attempts
    window = settings.db_connect_rate_limit_window_seconds
    if limit <= 0 or window <= 0:
        return

    try:
        client = get_redis_client()
        if client is None:
            raise RedisError("Redis URL is not configured.")
        key = f"qm:db-connect-attempts:{owner_id}"
        count = int(client.incr(key))
        if count == 1:
            client.expire(key, window)
        if count > limit:
            raise RateLimitError()
    except RateLimitError:
        raise
    except Exception as exc:
        if settings.is_production:
            raise ServiceUnavailableError("Connection attempt rate limiting is temporarily unavailable.") from exc
        logger.warning("Falling back to in-memory database connection rate limits: %s", exc)
        _enforce_memory_rate_limit(owner_id)


__all__ = [
    "ConnectionAttemptTarget",
    "RateLimitError",
    "connection_attempt_target",
    "enforce_connection_attempt_rate_limit",
    "get_redis_client",
    "validate_connection_target",
]
