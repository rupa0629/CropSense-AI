# Managed PostgreSQL migration

Do not replace the live SQLite database until a backup and restore rehearsal
has succeeded.

1. Create Railway PostgreSQL in a staging project.
2. Set staging `DATABASE_URL` from the Railway PostgreSQL reference variable.
3. Set `RUN_DATABASE_MIGRATIONS=true`.
4. Deploy; `scripts/start.sh` runs `alembic upgrade head` before the API starts.
5. Run the full API and browser suites against staging.
6. Export SQLite records with a purpose-built one-time migration command,
   import them into staging, and compare row counts and sampled records.
7. Create an encrypted PostgreSQL backup and restore it into a disposable
   database. Verify login, history, feedback and review queues.
8. Schedule a maintenance window, stop writes, repeat export/import, validate,
   then switch production `DATABASE_URL`.
9. Keep the old SQLite volume read-only for the agreed rollback window.

Use Railway managed backups plus an independent encrypted export:

```sh
python scripts/backup_postgres.py
python scripts/verify_postgres_backup.py backups/FILE.dump.encrypted
```

Store `BACKUP_ENCRYPTION_KEY` separately from both Railway and backup storage.
Test a full restore quarterly. A backup that has not been restored is unproven.
