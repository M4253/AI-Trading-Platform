# Database Backup and Recovery

The application stores local paper-trading state in SQLite at `backend/data/trading.db`. This file contains paper orders, positions, decisions, watchlists, broker metadata, and redacted audit records. It must not be committed to Git.

## Backup

1. Stop the backend cleanly so no transaction is in progress.
2. Create a private backup directory and copy the database with restrictive permissions.

```bash
mkdir -p backups
chmod 700 backups
cp backend/data/trading.db backups/trading-$(date +%Y%m%d-%H%M%S).db
chmod 600 backups/trading-*.db
```

For an online SQLite backup, use the SQLite CLI `.backup` command while the service is running rather than copying a changing file. Store backups in encrypted infrastructure approved by the owner; this repository does not provide cloud backup storage.

## Restore

1. Stop the backend.
2. Preserve the current database under a dated name rather than deleting it.
3. Copy a chosen backup into `backend/data/trading.db` and set mode `600`.
4. Start the service and call `GET /ready`, then inspect the paper account, orders, and AI decisions.

```bash
mv backend/data/trading.db backend/data/trading-before-restore.db
cp backups/trading-YYYYMMDD-HHMMSS.db backend/data/trading.db
chmod 600 backend/data/trading.db
APP_ENV=development AUTH_REQUIRED=false uvicorn backend.main:app
```

The Phase 11 restart-recovery test verifies that saved paper state survives an application restart. It is not a substitute for a regularly tested backup/restore drill.

## Recovery safety

- Never restore while the backend is writing to the database.
- Check filesystem ownership and mode (`600`) after restore.
- The emergency stop is persisted in the database; confirm its state after restoration before starting paper trading.
- Restore only known-good local paper databases. No real broker credential should ever be present in this database.
