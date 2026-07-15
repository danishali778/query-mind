# Authentication Layer — Security & QA Assessment

**Target:** query-mind (FastAPI backend + React frontend)
**Component under test:** Authentication layer (signup, login, refresh, logout, session, JWT verification, CSRF, rate limiting, cookie handling)
**Test type:** Authorized security assessment (grey-box: source review + live dynamic testing) on a local instance
**Environment:** Backend `http://localhost:8000`, Frontend `http://localhost:5173`, auth wired to a **real Supabase** project
**Date:** 2026-07-14 / 15
**Verdict:** 🟢 **Robust.** No critical or high vulnerability. One medium-severity design gap, plus a handful of low/informational hardening items.

> **Post-assessment correction (2026-07-15):** Source verification found that
> positive `is_active` checks are cached for up to 60 seconds, so direct database
> deactivation is not inherently immediate. It also found that the logout route
> previously ignored remote Supabase revocation failure. Remediation is tracked
> on `fix/auth-security-remediation`; the original dynamic evidence below is
> retained as the pre-remediation baseline.

**Remediation status:** AUTH-001 is implemented on
`fix/auth-security-remediation` in the following commits:

- `03a3148` — JWT algorithm pinning, durable current-session revocation,
  refresh-session revocation enforcement, bounded credential validation,
  account-state cache invalidation, cleanup, and diagnostics.
- `111bfd0` — matching signup validation and accessibility in the frontend.
- `117ed27` — automated backend security regression coverage.

Automated coverage is located in:

- `backend/tests/test_auth_backend.py`
- `backend/tests/test_auth_security.py`
- `backend/app/tests/unit/test_auth_dependencies.py`
- `backend/app/tests/unit/test_auth_user_cache.py`
- `frontend/tests/auth-page.test.tsx`

Post-remediation verification completed with 60 focused backend authentication
tests, 367 full non-integration backend tests, 37 frontend tests, frontend lint
and production build, a single Alembic head at `20260715_0017`, no ORM schema
drift, and valid Docker Compose configuration.

---

## 1. Executive Summary

The authentication layer is well-built and stood up to a broad battery of attacks. Token forgery, CSRF, brute-force, and endpoint authorization were all tested and held. The one finding that warrants a product decision is that **logout does not revoke the already-issued access token** — it stays valid until it expires (up to 1 hour). Everything else is low-severity hardening.

| Severity | Count | Findings |
|---|---|---|
| 🔴 Critical | 0 | — |
| 🟠 High | 0 | — |
| 🟡 Medium | 1 | F-01 Logout does not revoke the access token |
| 🟢 Low | 3 | F-02 JWT accepts HS256+ES256 · F-03 No app-layer input validation · F-04 Crafted token returns 500 not 401 |
| ⚪ Info | 3 | F-05 Refresh reuse grace window · F-06 Cookie domain shared across localhost ports · F-07 Prod auth fails-closed on Redis outage |

---

## 2. Scope & Methodology

### Endpoints tested
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/signup` | Create account |
| POST | `/api/auth/login` | Password login |
| POST | `/api/auth/refresh` | Rotate session via refresh token |
| POST | `/api/auth/logout` | Terminate session |
| GET | `/api/auth/session` | Current session / token validation |

Plus the supporting machinery: JWT verification (`app/integrations/supabase_auth/jwt.py`, `dependencies.py`), CSRF middleware (`app/core/middleware.py`), rate limiter (`app/core/auth_rate_limit.py`), cookie handling (`app/core/supabase_auth.py`).

### Techniques applied
- **JWT attacks:** algorithm confusion (HS256-forge with the EC public key), `alg:none`, attacker-key signing, payload tampering.
- **Input validation / fuzzing:** missing fields, wrong types, null, non-JSON, oversized, malformed `Authorization` headers.
- **CSRF:** Origin-header bypass matrix (missing / `null` / evil / subdomain / case / trailing-slash).
- **Brute-force:** repeated failed logins to trip the rate limiter.
- **Authorization:** unauthenticated access across a sample of protected endpoints.
- **Session lifecycle (live, authenticated):** access-token validity, refresh-token rotation & reuse, logout revocation window, refresh-after-logout.
- **Info leakage:** error messages, user enumeration.

### A note on password handling
The tester did **not** submit the account password directly. The authenticated-session tests were performed by having the account owner log in through the browser, then capturing the resulting HttpOnly session cookies from browser DevTools for controlled replay in Python.

---

## 3. Strengths — What's Working Well

These were explicitly tested and passed. They are the reason the overall verdict is "robust."

### 3.1 JWT forgery is not possible
- **Algorithm confusion blocked.** The verifier is configured with an EC **public** JWK (`kty=EC`, `x`/`y` only, no private `d`). Five different HMAC-secret encodings of that public key (PEM, raw uncompressed point, JWK JSON, x‖y) were used to forge `HS256` tokens. python-jose refuses to use an asymmetric key as an HMAC secret; all attempts failed. `alg:none` was rejected (`401`).
- **Signature verification is real.** A token signed with an attacker-generated ES256 key — but with the correct `iss`/`aud`/`sub` — was rejected (`401`). A tampered-payload token was rejected.
- **Issuer and audience are pinned** (`aud="authenticated"`, `iss=<supabase>/auth/v1`).

### 3.2 CSRF protection is strong
`CookieOriginMiddleware` enforces an **exact-match Origin allowlist** on every unsafe method (POST/PUT/PATCH/DELETE) whenever an auth cookie is present. Bypass matrix (all with a valid auth cookie):

| Attack vector | Result |
|---|---|
| No `Origin` header (classic CSRF form POST) | **403 blocked** |
| `Origin: https://evil.com` | **403 blocked** |
| `Origin: null` (sandboxed iframe / data: URL) | **403 blocked** |
| Subdomain trick `http://localhost:5173.evil.com` | **403 blocked** |
| Case variant `HTTP://LOCALHOST:5173` | **403 blocked** |
| Trailing slash `http://localhost:5173/` | **403 blocked** |
| Allow-listed `http://localhost:5173` | passes CSRF → auth check |

Because `request.headers.get("origin")` is `None` when absent, a **missing Origin fails the allowlist** — closing the most common CSRF bypass. Production CORS/origin validation additionally forbids `*`, non-HTTPS, and loopback origins.

### 3.3 Rate limiting works
Credential endpoints are rate-limited by **both** normalized email and client IP (`5` attempts / `900s`). Repeated bad logins tripped a clean `429` (`auth_rate_limited`). Trusted-proxy handling parses `X-Forwarded-For` only for allow-listed proxy CIDRs.

### 3.4 Cookie security is correct
Access & refresh tokens are set with:
- `HttpOnly` ✓ — **verified** (`document.cookie` is empty). Page JavaScript cannot read the token, but privileged browser tooling can inspect it and XSS can still issue authenticated same-origin requests.
- `Secure` — auto-enabled in production.
- `SameSite=Lax` — layered CSRF defense on top of the Origin middleware.
- Refresh-token cookie **path-scoped to `/api/auth`**, limiting its exposure surface.

### 3.5 Input validation & error handling
- Missing fields, wrong types, `null`, and non-JSON bodies are all rejected by Pydantic with a structured `422` before any business logic runs — and before the rate limiter, so they consume no rate budget.
- No stack traces or internal details leak to clients; errors are wrapped in a consistent `{"error": {...}}` envelope.

### 3.6 No user enumeration on login
Invalid credentials always return the generic `"Invalid login credentials"` regardless of whether the email exists.

### 3.7 Consistent authorization
A sample of protected endpoints (`/api/database/connections`, `/api/chat/sessions`, `/api/settings`, `/api/dashboard/dashboards`, `/api/analytics/overview`) all returned `401` without a token. No accidentally-unauthenticated endpoint was found **in this tested sample**. Logout is idempotent (`200` even with no session).

### 3.8 Refresh token is properly revoked on logout
Logout terminates the Supabase session server-side: a refresh attempt after logout returns `401 "Invalid Refresh Token: Refresh Token Not Found"`. The long-lived (30-day) credential is killed immediately — see F-01 for the one exception (the short-lived access token).

### 3.9 Safe configuration defaults
- Mock/dev auth bypass (`mock_auth_enabled`) requires `BACKEND_DEV_MODE=true` **and** a missing JWT secret — both false here, so it cannot be silently enabled while a secret is configured.
- `assert_user_exists` verifies the user's `is_active` flag, but positive results are cached for `AUTH_USER_CACHE_TTL_SECONDS` (60 seconds by default). Application-driven deactivation must invalidate this cache; direct database changes may remain effective only after the TTL.

---

## 4. Findings — Detailed

### F-01 · 🟡 Medium · Logout does not revoke the access token
**Component:** `app/services/auth.py` (`logout`), `app/integrations/supabase_auth/dependencies.py` (`authenticate_credentials`)

**Description.** Logout revokes the refresh token at Supabase and clears the browser cookies, but the **already-issued access JWT remains fully valid until its `exp`** (default lifetime 3600s / 1 hour). On each request the app validates only the token signature, `aud`, `iss`, `exp`, and the local `is_active` flag — it never checks whether the Supabase *session* was terminated. So a captured access token keeps authenticating after the user has "logged out."

**Evidence (live).**
```
pre-logout   /session (bearer) -> 200  authenticated
logout                          -> 200  "Signed out."
post-logout  /session (bearer) -> 200  authenticated   <-- still valid
             (original pasted access token)  -> 200
time-to-expiry at test moment: ~3254s (~54 min) remaining
```

**Impact.** Logout gives false assurance. On a shared/public machine, or during incident response ("revoke this user now"), a leaked or lingering access token still works for up to an hour. Severity is held to **Medium** — not High — because of compensating controls: `HttpOnly` prevents page JavaScript from reading the token and the 1-hour cap bounds the window. Direct database deactivation may itself be delayed by the positive active-user cache.

**Recommendation (pick one or combine):**
1. **Shorten the access-token TTL** to 5–15 min in the Supabase JWT settings (cheapest; most teams do this and lean on refresh rotation).
2. Maintain a server-side **revocation list keyed by `session_id`** (present in the JWT) and reject revoked sessions on logout-sensitive routes.
3. **Re-validate the session with Supabase** (or check `session_id`) on high-impact actions.

---

### F-02 · 🟢 Low · JWT verifier accepts both HS256 and ES256
**Component:** `app/integrations/supabase_auth/jwt.py:35`

**Description.** `decode_supabase_jwt` passes `algorithms=["HS256","ES256"]` while the configured key is an EC **asymmetric public** key. Accepting a symmetric algorithm (HS256) alongside an asymmetric one is the classic pre-condition for algorithm-confusion attacks.

**Status.** **Not currently exploitable** — python-jose refuses to use the asymmetric key as an HMAC secret (verified, see §3.1). This is a latent footgun / defense-in-depth issue, not an open hole: a future library change, or switching key material handling, could turn it into a real bypass.

**Recommendation.** Pin the algorithm to the key type: `algorithms=["ES256"]`.

---

### F-03 · 🟢 Low · No application-layer email/password validation
**Component:** `app/api/v1/schemas/auth.py`

**Description.** `AuthCredentialsRequest` declares `email: str` and `password: str` with no constraints. Email format is **not** validated (`"not-an-email"` passed the app layer entirely and only failed at Supabase), and password policy is whatever Supabase enforces — observed to be just the **6-character minimum** default, no complexity.

**Evidence.**
```
signup email="not-an-email" password="1" -> 400 "Password should be at least 6 characters."
   ^ rejected by Supabase, not by the app; the invalid email was never caught
```

**Impact.** Weak/low-quality credentials are possible; the app has no defense-in-depth if Supabase policy is ever relaxed. Low severity because Supabase is a real gate.

**Recommendation.** Use `pydantic.EmailStr` for email and add an explicit password policy (min length ≥ 8–12, basic complexity) at the schema layer.

---

### F-04 · 🟢 Low · Crafted token yields 500 instead of 401
**Component:** `app/integrations/supabase_auth/dependencies.py:118`

**Description.** A token crafted with `alg:HS256` but verified against the JWK dict raises an exception type that is **not** caught as `JWTError`; it falls through to the generic handler and returns `500 "Internal authentication service error."` instead of `401`.

**Evidence.** In the JWT-confusion test, the `raw_uncompressed_point` and `jwk_json_str` HS256 tokens returned `500`, not `401`. (Fail-closed, so not a security bypass — but incorrect status + log noise, and attacker-triggerable.)

**Recommendation.** Broaden the exception handling in `authenticate_credentials` to treat all token-decode/key errors (`JOSEError`/`JWKError`, key-type mismatches) as `401 Could not validate credentials`.

---

### F-05 · ⚪ Info · Refresh-token reuse grace window (~10s)
**Component:** Supabase (proxied by `app/services/auth.py:refresh_session`)

**Description.** Refresh tokens **do rotate** on every call (`R0 → R1 → R2 …`), but reusing the immediately-previous token within Supabase's `refresh_token_reuse_interval` (default **10s**) is **tolerated** and returns a valid session; it did not trigger family revocation in that window.

**Evidence.**
```
refresh(R0) -> 200   R0="emikuzkodpjw" -> R1="ty7qyeesshte"  (rotated)
refresh(R0 again, immediate) -> 200  authenticated   <-- old token still accepted (grace window)
```

**Notes.** This is documented Supabase behavior (grace for network retries), controllable only in the Supabase dashboard, not app code. Post-interval reuse (which should trigger reuse-detection/family-revocation) was **not** tested (would require waiting out the interval on a fresh session). Consider tightening `SECURITY_REFRESH_TOKEN_REUSE_INTERVAL` if the retry grace is not needed.

---

### F-06 · ⚪ Info · Auth cookie domain is `localhost` (shared across ports)
**Component:** cookie issuance (dev environment)

**Description.** In DevTools the auth cookies show **Domain = `localhost`** (host-only, no port). Because cookies ignore ports in domain matching, the tokens are sent to **every** localhost service (`:5173`, `:8000`, any other local app). This is why cross-origin `fetch` to `:8000` carried the session.

**Impact.** Dev-only concern; in production the domain is the deployed API host. Worth being aware of if multiple services share a hostname. No action required for production as configured.

---

### F-07 · ⚪ Info · Production auth fails closed on Redis outage
**Component:** `app/core/auth_rate_limit.py:107`

**Description.** In production, if Redis is unavailable, `enforce_auth_attempt_rate_limit` raises `ServiceUnavailableError` — meaning **all** login/signup requests return `503` during a Redis outage. In development it falls back to an in-memory limiter. This is a deliberate fail-closed posture (prevents unlimited brute-force during an outage) but couples auth availability to Redis.

**Recommendation.** Acceptable by design; add monitoring/alerting on Redis so an outage is caught before it becomes an auth outage.

---

### F-08 · 🟡 Medium · Logout previously ignored remote revocation failure
**Component:** `app/api/v1/routes/auth.py`, `app/services/auth.py`

**Description.** The service returned `False` when Supabase logout failed, but
the route discarded that result, cleared browser cookies, and always returned
`200 Signed out`. The tested successful logout proved refresh revocation only
for the success path; it did not prove revocation during a Supabase outage.

**Remediation.** QueryMind now writes a durable local current-session revocation
before contacting Supabase. A remote failure remains a silent `200` by product
decision, but the locally revoked access token remains blocked and the failure
is logged without tokens or raw session identifiers. A local revocation-storage
failure clears cookies and returns `503 auth_revocation_unavailable`.

---

## 5. Test Evidence Log

### 5.1 JWT algorithm-confusion / forgery
```
jwk kty=EC crv=P-256 has_private_d=False
pem_spki_str          -> could-not-sign (jose blocks asymmetric key as HMAC secret)
pem_spki_bytes        -> could-not-sign
raw_uncompressed_point-> rejected 500
jwk_json_str          -> rejected 500
x_concat_y            -> rejected 500
alg_none              -> rejected 401
ES256 signed w/ attacker key (correct iss/aud/sub) -> 401
tampered payload      -> 401
```

### 5.2 Input validation & rate limiting
```
signup {}                       -> 422 (missing email, password)
login missing password          -> 422
login wrong types               -> 422
signup null password            -> 422
login non-JSON                  -> 422
signup not-an-email / pw="1"    -> 400 (Supabase: password >= 6 chars)
login bad creds x5 (same IP)    -> 401,401,401,401,429  (rate limited)
```

### 5.3 Malformed auth headers & endpoint enforcement
```
Bearer (empty)                  -> 401 Missing authentication credentials
Bearer not.a.jwt                -> 401 Could not validate credentials
Bearer aaa.bbb                  -> 401
Basic <...>                     -> 401 Missing credentials
Bearer <5000 A's>               -> 401
no-token /api/database/connections -> 401
no-token /api/chat/sessions        -> 401
no-token /api/settings             -> 401
no-token /api/dashboard/dashboards -> 401
no-token /api/analytics/overview   -> 401
logout (no session)                -> 200 idempotent
```

### 5.4 CSRF Origin enforcement
```
cookie + no Origin              -> 403 csrf_origin_invalid
cookie + Origin evil.com        -> 403
cookie + Origin null            -> 403
cookie + Origin localhost:5173.evil.com -> 403
cookie + Origin HTTP://LOCALHOST:5173   -> 403 (exact match)
cookie + Origin localhost:5173/ -> 403
cookie + Origin localhost:5173  -> passes CSRF -> 401 (bad token)
no cookie (any Origin)          -> middleware does not fire -> 401
DELETE + cookie + evil Origin   -> 403
```

### 5.5 Authenticated session lifecycle (live)
```
A. access token: alg=ES256, lifetime=3600s, bearer /session -> 200
B. refresh(R0) -> 200, rotated R0->R1; refresh(R0 reuse) -> 200 (10s grace); refresh(R1) -> 200 rotated again
C. pre-logout /session -> 200 ; logout -> 200 ; post-logout /session -> 200  (ACCESS TOKEN STILL VALID)
D. refresh after logout -> 401 "Invalid Refresh Token: Refresh Token Not Found" (refresh family revoked)
```

---

## 6. Remediation Priority

| Priority | Finding | Action |
|---|---|---|
| 1 | F-01 | Shorten access-token TTL (5–15 min) and/or add `session_id` revocation. **Product decision needed.** |
| 2 | F-02 | Pin JWT `algorithms=["ES256"]`. One-line change. |
| 3 | F-03 | `EmailStr` + password policy in the auth schema. |
| 4 | F-04 | Catch all token/key errors as `401` in `authenticate_credentials`. |
| 5 | F-05 | (Optional) tighten Supabase refresh-reuse interval. |
| — | F-06, F-07 | No action / monitoring only. |

---

## 7. Not Yet Tested / Follow-ups

- **Post-interval refresh-token reuse detection** (reuse an old refresh token *after* the 10s grace window — should trigger family revocation). Requires a fresh session + timed wait.
- **Concurrent-session behavior** (multiple active sessions per user, per-session revocation).
- **OAuth / Google sign-in path** (the UI shows a deferred Google OAuth option — not exercised).
- **Email-confirmation & password-reset flows** (signup enumeration depends on the Supabase "Confirm email" setting — verify it is ON so existing-email signups don't reveal account existence).
- **Account lockout / progressive delays** beyond the flat rate limit.

---

## 8. Appendix — Test Artifacts

Dynamic tests were executed with Python (`httpx`, `python-jose`, `cryptography`) against the local backend. Scripts used during this assessment:
- `jwt_confusion_test.py` — algorithm-confusion / forgery matrix
- `auth_validation_test.py` — input validation + rate-limit trip
- `deeper_auth_test.py` — malformed headers, attacker-key signing, tampering, endpoint enforcement
- `csrf_test.py` — CSRF Origin bypass matrix
- `session_tests.py` — authenticated lifecycle (rotation, reuse, logout window)

> These were run from a scratch/working directory and are not committed to the repo. They can be reproduced against a local instance; the session tests require capturing the HttpOnly session cookies from browser DevTools after an interactive login.
