# HSC-ai Operations Guide

## Health Endpoints

### `GET /api/health` (public)

Basic service status. Returns:

| Field | Description |
|---|---|
| `status` | `"ok"` or `"degraded"` |
| `service` | `"hsc-ai-backend"` |
| `version` | App version string |
| `database` | `"ok"` or `"error"` |
| `redis` | `"ok"` or `"error"` |

### `GET /api/health/detailed` (public)

Extended operational health. Safe for monitoring probes — no user data, row counts, or job details exposed.

| Field | Description |
|---|---|
| `database_status` | `"ok"` or `"error"` |
| `redis_status` | `"ok"` or `"error"` |
| `storage_status` | `"ok"` or `"error"` (MinIO) |
| `migration_version` | Alembic head revision |
| `uptime_seconds` | Seconds since server start |
| `memory_usage_mb` | RSS memory usage |

### `GET /api/v1/admin/system` (admin only)

Full platform health dashboard. Requires admin authentication.

Includes all health fields plus user activity, content counts, job status, failed/stuck job lists, and table row counts.

## Startup Diagnostics

On backend startup (production mode):

1. Logs environment (`development` or `production`)
2. Logs app version
3. Checks database connectivity — **fails fast** if unreachable
4. Checks Redis connectivity — logs critical if unreachable
5. Checks MinIO connectivity — logs warning if unreachable

Startup diagnostics are skipped when `DEBUG=true` (development mode).

## Dependency Checks

| Dependency | Health Check | Failure Behavior |
|---|---|---|
| PostgreSQL | `SELECT 1` | Startup: SystemExit. Runtime: endpoint returns `"error"` |
| Redis | `PING` | Startup: critical log. Runtime: endpoint returns `"error"` |
| MinIO | `list_buckets()` | Startup: warning log. Runtime: endpoint returns `"error"` |

## Stuck Jobs

### Definition

A job is **stuck** when:

- **OCR / Import jobs**: status is `processing` and `started_at` is older than `STUCK_JOB_THRESHOLD_MINUTES` (default: 30)
- **AI generation jobs**: status is `pending` and `created_at` is older than `STUCK_JOB_THRESHOLD_MINUTES` (default: 30)

### Configurable Threshold

Set via environment variable or `.env`:

```
STUCK_JOB_THRESHOLD_MINUTES=30
```

View stuck jobs at `GET /api/v1/admin/system` in the `stuck_jobs` field.

## Container Troubleshooting

### Backend unhealthy

```
docker compose ps
# Check backend status
docker compose logs backend --tail=100
# Look for startup errors
docker compose exec backend python -c "import fitz; print('OK')"
# Verify OCR deps
```

### Database connectivity

```
docker compose exec postgres pg_isready -U hscai -d hscai
docker compose exec backend python -c "
from app.core.database import engine
import asyncio
async def test():
    async with engine.connect() as conn:
        await conn.execute(text('SELECT 1'))
asyncio.run(test())
"
```

### Redis connectivity

```
docker compose exec redis redis-cli ping
```

### MinIO connectivity

```
curl http://localhost:9190/minio/health/live
```

## Recovery Steps

### Restart stack

```
docker compose down
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

### Reset unhealthy backend

```
docker compose restart backend
docker compose logs backend --tail=50
```

### Full reset (data preserved)

```
docker compose down
docker compose up -d
docker compose exec backend alembic upgrade head
```

### Check migration status

```
docker compose exec backend alembic current
docker compose exec backend alembic history
```

## Backup Strategy

### Database

```
docker compose exec postgres pg_dump -U hscai hscai > backup_$(date +%Y%m%d).sql
```

### Restore

```
docker compose exec -T postgres psql -U hscai hscai < backup_20260101.sql
```

### Volume backup

PostgreSQL data: `postgres_data` volume
Redis data: `redis_data` volume
MinIO data: `minio_data` volume

Back up via `docker run --rm -v <volume>:/data -v $(pwd):/backup alpine tar czf /backup/<name>.tar.gz -C /data .`

## Health Monitoring

### Recommended monitoring endpoints

- `GET /api/health` — every 30s for uptime monitoring
- `GET /api/health/detailed` — every 5min for detailed metrics

### Alert thresholds

| Metric | Warning | Critical |
|---|---|---|
| `database_status` | — | `"error"` |
| `redis_status` | — | `"error"` |
| `storage_status` | — | `"error"` |
| `memory_usage_mb` | > 400 MB | > 500 MB |
| Failed jobs | > 0 | > 5 |
| Stuck jobs | > 0 | > 3 |
