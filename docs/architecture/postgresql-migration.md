# PostgreSQL Runtime Migration

BSIE already supports PostgreSQL through `DATABASE_URL`. Local development can continue using SQLite fallback, but production should point to PostgreSQL.

BSIE now auto-loads `.env` during normal app startup, so a local `.env` can make PostgreSQL the default runtime on a workstation without changing the run command.

## Quick Start

1. Start PostgreSQL:

```bash
docker compose -f docker-compose.postgres.yml up -d
```

2. Set environment:

```bash
cp .env.example .env
```

Default operational values in `.env.example`:

- `DATABASE_URL=postgresql+psycopg://bsie:bsie@localhost:5432/bsie`
- `BSIE_ENABLE_AUTO_BACKUP=1`
- `BSIE_BACKUP_INTERVAL_HOURS=24`
- `BSIE_AUTO_BACKUP_FORMAT=auto`
- `BSIE_BACKUP_POLL_SECONDS=60`

3. Apply migrations:

```bash
alembic upgrade head
```

4. Start BSIE normally:

```bash
.venv/bin/python app.py
```

5. Verify runtime backend:

```bash
curl http://127.0.0.1:5001/api/admin/db-status
```

The response should report:

- `database_backend = postgresql`
- `database_runtime_source = environment`
- `has_investigation_schema = true`

6. Use Investigation Admin for operational safety:

- create JSON or `pg_dump` backups before major changes
- change scheduled backup enablement, interval, and format from the UI
- preview restore impact before applying a backup
- reset the active DB only with the reset confirmation phrase
- restore a backup only with the restore confirmation phrase
- download backups from `/api/download-backup/{backup_name}`

## Notes

- SQLite remains the fallback when `DATABASE_URL` is unset.
- Existing investigation/admin APIs are database-backend agnostic.
- `pg_dump` / `pg_restore` are used only when PostgreSQL is active and the binaries are available on PATH.
- Production migration should be done before large-scale case imports to avoid split historical state between SQLite and PostgreSQL.
