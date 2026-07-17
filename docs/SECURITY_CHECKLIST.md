# Security Checklist

Use this checklist for every paper-only deployment.

- [ ] `APP_ENV=production`, `AUTH_REQUIRED=true`, and explicit `CORS_ALLOW_ORIGINS` are set.
- [ ] The production identity provider/session issuer has been integrated and independently tested; the development demo is disabled.
- [ ] TLS is enforced by the reverse proxy and HTTP is redirected or blocked.
- [ ] API and dashboard security headers are present.
- [ ] Gateway rate limiting is configured for a multi-process deployment.
- [ ] The API runs as a non-root account; the database and backup directories are private.
- [ ] `.env`, `backend/data/*.db`, caches, build output, and logs are ignored by Git.
- [ ] `python3 scripts/security_check.py` and dependency checks pass.
- [ ] No secrets, account identifiers, API keys, tokens, or credentials appear in source, commit history, logs, or issue attachments.
- [ ] The broker credential interface remains disabled unless an approved external secret manager is integrated.
- [ ] Audit events are retained and access to `/audit-events` is restricted.
- [ ] Error pages and API errors do not expose stack traces, filesystem paths, broker addresses, or credentials.
- [ ] STOP ALL TRADING has been tested after a restart.

## CSRF note

The API uses bearer tokens in the `Authorization` header and does not use browser cookies, so cookie-based CSRF does not apply. If a future deployment introduces cookie sessions, it must add same-site cookie settings and CSRF tokens before accepting any state-changing browser request.
