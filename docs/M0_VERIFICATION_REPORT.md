# M0 Verification Report

**Date:** 2026-06-01
**Platform:** Raspberry Pi 5 (aarch64), 7.9 GB RAM
**Docker:** 29.2.1 / Docker Compose v5.1.0
**Purpose:** Confirm Milestone 0 bootstrap is fully operational before M1 begins.

---

## 1. Port Mapping Verification

### Confirmed allocation

| Service | Host port | Container port | Status |
|---|---|---|---|
| nginx (web entry) | **3090** | 80 | ✅ Correct |
| MinIO API | **9190** | 9000 | ✅ Correct |
| MinIO Console | **9191** | 9001 | ✅ Correct |
| PostgreSQL | — | 5432 | ✅ Internal only |
| Redis | — | 6379 | ✅ Internal only |
| FastAPI backend | — | 8000 | ✅ Internal (no host exposure) |
| Next.js frontend | — | 3000 | ✅ Internal (no host exposure) |

No conflicts with existing Pi services. Backend and frontend are correctly internal, accessible only through nginx.

---

## 2. Service Status

All 6 services started and reached expected state.

| Container | Image | Status | Health |
|---|---|---|---|
| hsc-ai-backend-1 | hsc-ai-backend | Up | ✅ healthy |
| hsc-ai-frontend-1 | hsc-ai-frontend | Up | ⚠️ no health check (expected) |
| hsc-ai-minio-1 | minio/minio | Up | ✅ healthy |
| hsc-ai-nginx-1 | hsc-ai-nginx | Up | ℹ️ no check needed (proxy) |
| hsc-ai-postgres-1 | postgres:16-alpine | Up | ✅ healthy |
| hsc-ai-redis-1 | redis:7-alpine | Up | ✅ healthy |

Note: Frontend has no Docker health check defined. This is intentional for M0 — the service is verified by the nginx proxy returning HTTP 200 on `/`. A health check can be added in M1 if desired.

---

## 3. Health Endpoint Results

| Endpoint | Method | Expected | Result |
|---|---|---|---|
| `http://localhost:3090/api/health` | GET | 200 + JSON | ✅ 200 `{"status":"ok","service":"hsc-ai-backend","version":"0.1.0"}` |
| `http://localhost:3090/` | GET | 200 | ✅ 200 (Next.js landing page) |
| `http://localhost:9190/minio/health/live` | GET | 200 | ✅ 200 |
| `http://localhost:9191/` | GET | 200 | ✅ 200 (MinIO console UI) |

No direct backend (`8090`) or frontend (`3091`) host port mappings exist — both are correctly internal.

---

## 4. Test Results

```
make test-be   backend (pytest)    5 passed / 0 failed / 0 errors
make test-fe   frontend (vitest)   5 passed / 0 failed / 0 errors
make test      combined            10 passed total
```

### Backend tests (pytest)

| Test | Result |
|---|---|
| `test_health_returns_200` | ✅ PASSED |
| `test_health_returns_ok_status` | ✅ PASSED |
| `test_health_returns_service_name` | ✅ PASSED |
| `test_health_returns_version` | ✅ PASSED |
| `test_health_response_shape` | ✅ PASSED |

### Frontend tests (vitest)

| Test | Result |
|---|---|
| `renders without crashing` | ✅ PASSED |
| `displays Operational for ok` | ✅ PASSED |
| `displays Degraded for degraded` | ✅ PASSED |
| `displays Error for error` | ✅ PASSED |
| `renders the status indicator dot` | ✅ PASSED |

---

## 5. Log Summary

### backend

```
INFO: Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO: Started reloader process [1] using WatchFiles
INFO: Application startup complete.
INFO: "GET /api/health HTTP/1.1" 200 OK  (multiple health check hits)
```

Status: **Clean. No errors.**

### frontend

```
✓ Compiled / in 7.3s (544 modules)
GET / 200 in 7915ms   ← first request (JIT compilation, normal for dev mode)
✓ Compiled in 234ms   ← subsequent requests
```

Status: **Clean. No errors.** First-request compile time (~7–8 s) is normal for Next.js dev mode on ARM64. Subsequent requests are fast (234 ms). Not a concern for M0.

### nginx

```
GET /api/health HTTP/1.1 200 60
GET / HTTP/1.1 200 13661
```

Status: **Clean. Proxy routing working correctly.**

### postgres

```
database system is ready to accept connections
```

Status: **Clean. No errors.** Database initialised and accepting connections.

### redis

```
WARNING Memory overcommit must be enabled! Without it, a background save or
replication may fail under low memory condition. ...
To fix: add 'vm.overcommit_memory = 1' to /etc/sysctl.conf and reboot,
or run: sysctl vm.overcommit_memory=1
```

Status: **Warning only — Redis is functional.** The warning is a Linux kernel tuning recommendation. Redis passes its health check (`redis-cli ping → PONG`) and operates normally. This is a system-level setting outside Docker control.

**To suppress permanently:** run `sudo sysctl -w vm.overcommit_memory=1` on the Pi host, then add `vm.overcommit_memory = 1` to `/etc/sysctl.conf` for persistence across reboots.

### minio

```
MinIO Object Storage Server
Version: RELEASE.2025-09-07T16-13-09Z (go1.24.6 linux/arm64)
API: http://172.25.0.3:9000
WebUI: http://172.25.0.3:9001
```

Status: **Clean. Running native linux/arm64 binary.**

---

## 6. Fixes Applied

No fixes were required. All M0 components were operational on first run.

---

## 7. Known Limitations (non-blocking for M1)

| # | Item | Severity | Notes |
|---|---|---|---|
| L1 | Redis `vm.overcommit_memory` warning | Low | System-level kernel parameter; Redis works correctly. Apply `sysctl vm.overcommit_memory=1` on the Pi host to eliminate the warning. |
| L2 | Frontend first-request compile time ~8 s | Low | Normal for Next.js dev mode JIT. Not a concern until production build is created (Milestone 7). |
| L3 | Vitest CJS deprecation notice | Cosmetic | Vite internal warning; does not affect test results. Will resolve in a future vitest release. |
| L4 | No database migrations | Expected | M0 scaffold only. PostgreSQL is running but the schema is empty. Migrations are Milestone 1 work. |
| L5 | No auth implementation | Expected | M0 scaffold only. All endpoints are unauthenticated. Auth is Milestone 1 work. |
| L6 | Frontend has no Docker health check | Low | The frontend is verified healthy via the nginx proxy. A Docker-native health check is optional and can be added in M1. |

---

## 8. M0 Readiness Assessment

**M0 is complete and ready for M1.**

| Check | Result |
|---|---|
| Port allocation matches HSC agreed range | ✅ |
| No host port conflicts with other Pi services | ✅ |
| All 6 services start and reach healthy state | ✅ |
| Health endpoint returns correct JSON | ✅ |
| Frontend serves via nginx reverse proxy | ✅ |
| MinIO API and console accessible on correct ports | ✅ |
| PostgreSQL internal only | ✅ |
| Redis internal only | ✅ |
| Backend unit tests pass (5/5) | ✅ |
| Frontend component tests pass (5/5) | ✅ |
| No errors in any service logs | ✅ |
| No breaking issues discovered | ✅ |

---

## 9. Recommended Next Step

Begin **Milestone 1 — Auth + Database Foundation**:

1. Alembic setup and initial migration (users, parents, students, admins, refresh_tokens tables)
2. JWT RS256 auth: parent registration and login, admin login
3. Role middleware (`get_current_parent`, `get_current_admin` FastAPI dependencies)
4. Student first-login password setup endpoint
5. Upgrade `/api/health` to check PostgreSQL and Redis connectivity
6. Auth endpoint tests (unauthenticated → 401, wrong role → 403)

Resolve before M1 coding starts:
- `OPEN_DECISIONS.md` item 11 (ExamTemplate/Instance V1 separation) — needed before schema migration
- Redis `vm.overcommit_memory` sysctl on the Pi host (optional but recommended)
