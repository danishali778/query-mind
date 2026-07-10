import pytest

from app.core import secrets


def test_get_encryption_key_requires_value(monkeypatch):
    monkeypatch.setattr(secrets.settings, "encryption_key", None)

    with pytest.raises(RuntimeError, match="encryption_key"):
        secrets.get_encryption_key()


def test_validate_core_credentials_requires_all(monkeypatch):
    monkeypatch.setattr(secrets.settings, "encryption_key", None)
    monkeypatch.setattr(secrets.settings, "supabase_url", None)
    monkeypatch.setattr(secrets.settings, "supabase_service_role_key", None)
    monkeypatch.setattr(secrets.settings, "supabase_jwt_secret", None)
    monkeypatch.setattr(secrets.settings, "groq_api_key", None)

    with pytest.raises(RuntimeError, match="Missing required configuration values"):
        secrets.validate_core_credentials()


def test_validate_core_credentials_passes_with_all_values(monkeypatch):
    monkeypatch.setattr(secrets.settings, "encryption_key", "key")
    monkeypatch.setattr(secrets.settings, "supabase_url", "https://example.supabase.co")
    monkeypatch.setattr(secrets.settings, "supabase_service_role_key", "service-role")
    monkeypatch.setattr(secrets.settings, "supabase_jwt_secret", "jwt-secret")
    monkeypatch.setattr(secrets.settings, "groq_api_key", "groq-key")

    secrets.validate_core_credentials()
