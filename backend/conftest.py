"""Test-wide environment defaults.

Loaded by pytest before any test module is imported, so these land before
app.core.config instantiates the settings singleton. Values are inert
placeholders: real env vars (and CI-provided ones) take precedence via
setdefault, and no test should reach a live external service.
"""

import os

_TEST_ENV_DEFAULTS = {
    "ENCRYPTION_KEY": "TZZoA4e_0aRy3zO0u7FzjHwBq2L8y6b9R9oV8XmQ_Jw=",
    "APP_DATABASE_URL": "postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/query_mind_test",
    "GROQ_API_KEY": "groq-test-key",
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_ANON_KEY": "anon-test-key",
    "SUPABASE_SERVICE_ROLE_KEY": "service-role-key",
    "SUPABASE_JWT_SECRET": "jwt-secret",
    "LEMON_SQUEEZY_WEBHOOK_SECRET": "webhook-secret",
}

for _key, _value in _TEST_ENV_DEFAULTS.items():
    os.environ.setdefault(_key, _value)
