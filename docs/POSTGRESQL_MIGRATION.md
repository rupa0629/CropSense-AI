# Managed PostgreSQL migration

Do not replace the live SQLite database until a backup and restore rehearsal
has succeeded.

1. Create Railway PostgreSQL in a staging project.
2. Set staging `DATABASE_URL` from the Railway PostgreSQL reference variable.
3. Set `RUN_DATABASE_MIGRATIONS=true`.
4. Deploy; `scripts/start.sh` runs `alembic upgrade head` before the API starts.
5. Run the full API and browser suites against staging.
6. Audit the transfer without writing:

   ```powershell
   python scripts/migrate_sqlite_to_postgres.py `
     --sqlite C:\path\to\cropsense.db `
     --postgres-url $env:STAGING_DATABASE_URL
   ```

7. If every destination table is empty and the dry run is correct, execute:

   ```powershell
   python scripts/migrate_sqlite_to_postgres.py `
     --sqlite C:\path\to\cropsense.db `
     --postgres-url $env:STAGING_DATABASE_URL `
     --execute
   ```

   The command preserves IDs, refuses non-empty target tables and verifies
   every row count before committing.
8. Create an encrypted PostgreSQL backup and restore it into a disposable
   database. Verify login, history, feedback and review queues.
9. Schedule a maintenance window, stop writes, repeat export/import, validate,
   then switch production `DATABASE_URL`.
10. Keep the old SQLite volume read-only for the agreed rollback window.

## Railway private-network transfer

To avoid exposing credentials through a public TCP proxy, the backend startup
supports a one-time transfer while the application still serves SQLite:

```text
DATABASE_URL=sqlite:////app/data/cropsense.db
MIGRATION_DATABASE_URL=${{Postgres.DATABASE_URL}}
MIGRATE_SQLITE_TO_POSTGRES=true
LEGACY_SQLITE_PATH=/app/data/cropsense.db
RUN_BACKUP_REHEARSAL=true
BACKUP_ENCRYPTION_KEY=${{secret(64)}}
BACKUP_OUTPUT=/app/data/backups
RUN_DATABASE_MIGRATIONS=false
```

On that deployment, startup creates an encrypted SQLite snapshot and verifies a
decrypted copy with `PRAGMA integrity_check`. It then migrates the empty
PostgreSQL schema, copies every SQLite table, and verifies row counts. Finally,
it creates an encrypted PostgreSQL custom-format dump, restores it into an
isolated temporary database, compares every application table's row count, and
drops the temporary database. The deployment log must contain
`CUTOVER_REHEARSAL_PASSED`; otherwise do not switch production.

Immediately remove `MIGRATE_SQLITE_TO_POSTGRES`, `MIGRATION_DATABASE_URL`, and
`RUN_BACKUP_REHEARSAL` after the successful transfer so a later deployment
cannot attempt to copy into non-empty tables. Keep `BACKUP_ENCRYPTION_KEY`
secret and retain the encrypted files under `/app/data/backups`.

Only after backup/restore rehearsal should production change to:

```text
DATABASE_URL=${{Postgres.DATABASE_URL}}
RUN_DATABASE_MIGRATIONS=true
```

Railway managed volume backups require a paid plan. If that feature is enabled,
use it in addition to the independent encrypted export:

```sh
python scripts/backup_postgres.py
python scripts/verify_postgres_backup.py backups/FILE.dump.encrypted
```

Store `BACKUP_ENCRYPTION_KEY` separately from both Railway and backup storage.
Test a full restore quarterly. A backup that has not been restored is unproven.
