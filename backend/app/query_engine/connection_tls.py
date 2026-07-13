"""Validation and lifecycle management for PostgreSQL TLS material."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
import shutil
import tempfile

from cryptography import x509
from cryptography.hazmat.primitives import serialization

from app.core.config import settings
from app.core.errors import BadRequestError
from app.db.models.connection import ConnectionRequest


class TlsMaterial:
    def __init__(self, directory: str, connect_args: dict[str, str]) -> None:
        self.directory = directory
        self.connect_args = connect_args

    def cleanup(self) -> None:
        if self.directory:
            shutil.rmtree(self.directory, ignore_errors=True)
            self.directory = ""


def _bounded(value: str | None, label: str) -> bytes | None:
    if value is None:
        return None
    encoded = value.encode("utf-8")
    if len(encoded) > settings.connection_tls_cert_max_bytes:
        raise BadRequestError(f"{label} exceeds the configured size limit.", code="connection_certificate_invalid")
    return encoded


def validate_tls_configuration(config: ConnectionRequest) -> None:
    if config.ssl_mode not in {"disable", "require", "verify-ca", "verify-full"}:
        raise BadRequestError("Unsupported PostgreSQL SSL mode.", code="connection_certificate_invalid")
    root = _bounded(config.ssl_root_certificate, "Root CA certificate")
    cert = _bounded(config.ssl_client_certificate, "Client certificate")
    key = _bounded(config.ssl_client_private_key, "Client private key")
    if config.ssl_mode in {"verify-ca", "verify-full"} and not root:
        raise BadRequestError("A root CA certificate is required for the selected SSL mode.", code="connection_certificate_invalid")
    if bool(cert) != bool(key):
        raise BadRequestError("Client certificate and private key must be provided together.", code="connection_certificate_invalid")
    try:
        certificates = []
        if root:
            certificates.append(x509.load_pem_x509_certificate(root))
        client_cert = x509.load_pem_x509_certificate(cert) if cert else None
        if client_cert:
            certificates.append(client_cert)
        now = datetime.now(timezone.utc)
        for certificate in certificates:
            expires_at = getattr(certificate, "not_valid_after_utc", None)
            if expires_at is None:
                expires_at = certificate.not_valid_after.replace(tzinfo=timezone.utc)
            if expires_at <= now:
                raise ValueError("expired certificate")
        private_key = serialization.load_pem_private_key(key, password=None) if key else None
        if client_cert and private_key:
            cert_public = client_cert.public_key().public_bytes(
                serialization.Encoding.DER,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            key_public = private_key.public_key().public_bytes(
                serialization.Encoding.DER,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            if cert_public != key_public:
                raise ValueError("certificate/key mismatch")
    except (TypeError, ValueError) as exc:
        raise BadRequestError(
            "Certificate material is invalid, encrypted, expired, or does not match.",
            code="connection_certificate_invalid",
        ) from exc


def create_tls_material(config: ConnectionRequest) -> TlsMaterial | None:
    validate_tls_configuration(config)
    values = {
        "sslrootcert": config.ssl_root_certificate,
        "sslcert": config.ssl_client_certificate,
        "sslkey": config.ssl_client_private_key,
    }
    if not any(values.values()):
        return None
    directory = tempfile.mkdtemp(prefix="querymind-tls-")
    try:
        os.chmod(directory, 0o700)
        args: dict[str, str] = {}
        for option, value in values.items():
            if not value:
                continue
            path = Path(directory) / f"{option}.pem"
            path.write_text(value, encoding="utf-8")
            os.chmod(path, 0o600)
            args[option] = str(path)
        return TlsMaterial(directory, args)
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise


__all__ = ["TlsMaterial", "create_tls_material", "validate_tls_configuration"]
