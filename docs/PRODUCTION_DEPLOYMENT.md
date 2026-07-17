# Production Deployment Guide

## Scope and safety boundary

“Production” here means operating the paper-only application reliably. It does **not** mean real-money deployment. The backend has no live execution route, the IBKR adapter refuses to connect or submit orders, and the broker settings page is mock-only.

## Required deployment controls

1. Terminate TLS at an approved reverse proxy and expose only HTTPS.
2. Run a supported Python/Node runtime using a dedicated non-root operating-system account.
3. Set `APP_ENV=production`, `AUTH_REQUIRED=true`, and an explicit, comma-separated `CORS_ALLOW_ORIGINS` value for the dashboard origin. The production default for CORS is deny-all.
4. Run the API behind a production process manager; do not use `--reload`.
5. Use a private persistent volume for `backend/data/` with directory mode `700` and database mode `600`.
6. Configure central structured-log collection with access controls. The application logs request metadata, event names, and error classes, never request bodies or Authorization headers.
7. Put an HTTPS-aware shared rate limit at the reverse proxy/API gateway when more than one backend process is used. The in-process limiter is intentionally per-process.
8. Schedule encrypted backups and test recovery according to [Database Backup and Recovery](DATABASE_BACKUP_RECOVERY.md).

Example backend command after an external identity provider/session issuer has been integrated:

```bash
APP_ENV=production \
AUTH_REQUIRED=true \
CORS_ALLOW_ORIGINS=https://dashboard.example.com \
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 2
```

## Authentication status

The built-in demo login is intentionally disabled in production. The opaque bearer-session middleware fails closed without a valid server-issued session, but this repository does not ship an external IdP/session issuer. Do not relax `AUTH_REQUIRED` to make a production dashboard writable. Integrate and test an approved identity provider first.

## Deployment validation

After deployment, verify `/health`, `/ready`, and `/dependencies` from the monitoring network; run the security and paper-trading checklists; verify production CORS with the real dashboard origin; and confirm the audit log records paper settings/actions. Do not add broker credentials or open a broker network connection as part of this process.
