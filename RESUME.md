# NDIC Platform — Resume Prompt

Paste the contents of this file at the start of a new session to pick up exactly where we left off.

---

## Project

**Nigerian Dairy Intelligence Consortium (NDIC) Platform**
A full-stack herd intelligence platform for Nigerian dairy farming — multi-role dashboards, RBAC/compliance infrastructure, and a Cow Passport system with sensor data, vet records, and photo ML.

**GitHub:** https://github.com/DMFP13/ndic-platform
**Local root:** `/Users/mac1/ndic/`
**Frontend:** `/Users/mac1/ndic/frontend/`

---

## How to start the servers

```bash
# Backend (FastAPI)
cd /Users/mac1/ndic
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# Frontend (Vite dev server)
cd /Users/mac1/ndic/frontend
npm run dev
# Opens on http://localhost:3000 (falls back to 3001 if 3000 is busy)
```

**Demo login:** go to `http://localhost:3000`, pick any role, click the green **▶ Demo Mode** button. No backend needed — all data is mocked with a clear MOCK label.

---

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 async, Pydantic v2, Uvicorn |
| Database | PostgreSQL (async via asyncpg) |
| Frontend | React 18, Vite 5, Tailwind CSS 3, Recharts, react-leaflet, Axios |
| Auth | JWT (HS256), refresh tokens, Ed25519 record signatures |
| Storage | Local filesystem (`uploads/animal-photos/`) → S3-ready via `STORAGE_BACKEND=s3` |
| Deployment | Not yet deployed — local dev only |

---

## What has been built

### Backend

**RBAC + Compliance (Phase 5a)**
- `app/models/rbac_models.py` — Role, Permission, RolePermission, UserRoleAssignment, DataClassification, AuditLog, AuditExport
- `app/services/rbac_service.py` — permission checking, data class enforcement, org isolation
- `app/services/audit_service.py` — immutable audit log, 3-year retention, SHA-256 export hashing
- `app/api/compliance.py` — 5 endpoints: audit report, chain integrity, RBAC audit, export audit, data deletion
- `app/middleware/access_control.py` — JWT auth dependency, `require_role()`, `require_admin()`
- `scripts/seed_rbac.py` — seeds 8 roles, 24 permissions, 12 data classifications
- `tests/test_rbac_compliance.py` — 73 tests, all passing

**Core data models**
- `models/database.py` — Organization, User, Farm, Animal, HealthRecord, ProcessorIntake, DiseaseAlert, LenderAssessment, LedgerLog (append-only, cryptographically chained)
- `models/enums.py` — all enums
- `app/api/farm_submissions.py` — farm/animal registration, health records, dashboard

**Cow Passport (latest)**
- `app/models/animal_models.py` — SensorReading, VetRecord, AnimalPhoto ORM tables
- `app/services/storage_service.py` — `save_photo()` / `get_photo_url()` / `delete_photo()`, local now, S3 in prod
- `app/api/animals.py` — 10 endpoints: passport, sensor history, vet records CRUD, photo upload/delete, ML ID stub
- All endpoints return realistic mock data when DB tables don't exist yet (pre-migration)

### Frontend

**9 roles:** farm_manager, farm_admin, farm_vet, processor_analyst, processor_commercial, govt_analyst, govt_admin, lender_analyst, arpexas_admin

**Pages/components:**
- `LoginPage.jsx` — demo mode (bypasses backend), role dropdown, 3s timeout before auto-demo on network failure
- `DashboardLayout.jsx` — top nav, collapsible sidebar, audit log panel, role badge
- `GovDashboard.jsx` — react-leaflet disease outbreak map, production BarChart, early warnings
- `ProcessorDashboard.jsx` — supply forecast AreaChart with confidence bands, supplier table, benchmarking
- `FarmDashboard.jsx` — animal table with expand/collapse AI panel, interventions accordion, climate section
- `LenderDashboard.jsx` — loan table, slide-in collateral panel, early warnings, pipeline
- `AnimalPassportPage.jsx` — **Cow Passport** (standalone page, mobile-first):
  - Hero: primary photo + identity grid (tag, microchip, breed, sex, DOB, dam/sire)
  - Live sensor cards: temp, weight, milk yield, heart rate, activity, feed intake
  - 30-day trend charts: milk yield, weight, temperature
  - Vet records timeline: add/edit/delete with type-specific forms (vaccination, treatment, disease, weight check, pregnancy check, calving, note)
  - Photo gallery: mobile camera capture, file upload, lightbox, ML identification stub
  - Read-only for lender/govt roles, full write for farm_manager/farm_admin/farm_vet

**API layer:**
- `src/api/client.js` — Axios instance, 3s timeout, 401 refresh queue (no hard redirects in demo mode)
- `src/api/endpoints.js` — 20+ endpoint functions, all wrapped in `_mockFallback()` with realistic Nigerian dairy mock data

---

## Roles and routing

| Role | Dashboard | Can edit passport? |
|---|---|---|
| farm_manager | /farm | Yes |
| farm_admin | /farm | Yes |
| farm_vet | /farm | Yes (vet records only by convention) |
| processor_analyst | /processor | No |
| processor_commercial | /processor | No |
| govt_analyst | /government | No |
| govt_admin | /government | No |
| lender_analyst | /lender | No |
| arpexas_admin | /government | No |

**Cow Passport URL:** `/farm/animals/:animalId` or `/animals/:animalId` (cross-role read)

---

## What is NOT done yet (next steps)

### High priority
1. **Database migration** — the new `sensor_readings`, `vet_records`, `animal_photos` tables exist as ORM models but have never been migrated. Need Alembic or a manual `CREATE TABLE` run against PostgreSQL before the backend endpoints persist real data.
2. **Real sensor integration** — `SensorReading` model and API are ready. Need to wire up the actual IoT device protocol (RFID/BLE/bolus sensor) and a background task (Celery or FastAPI BackgroundTasks) to ingest readings.
3. **ML cow identification** — `POST /api/animals/identify-from-photo` is a stub returning mock confidence scores. Real integration point is in `app/api/animals.py → identify_from_photo()`. Suggested model: a fine-tuned MobileNetV3 or EfficientNet trained on Nigerian cattle breeds.
4. **S3 photo storage** — `storage_service.py` is fully wired. To go live: set `STORAGE_BACKEND=s3`, `S3_BUCKET`, `S3_REGION`, AWS credentials. Zero code changes needed.
5. **Auth URL alignment** — `AuthContext.jsx` calls `http://localhost:8001/auth/...` but the real backend route is `/api/auth/...`. In demo mode this doesn't matter (falls to mock), but needs fixing for real login.

### Medium priority
6. **Alembic setup** — no migration tool configured yet. Add `alembic init` and create initial migration covering all models.
7. **Cow Passport — primary photo setter** — UI allows photo upload but no button to set a photo as primary. Add a "Set as primary" tap action in the photo gallery.
8. **Cow Passport — PDF export** — generate a printable/downloadable passport PDF for each animal (for physical records, loan collateral documents, etc.).
9. **Processor/Lender passport access** — routes are configured read-only, but the dashboards don't yet have "View Passport" links. Add them from the supplier table (Processor) and loan table (Lender).
10. **Push notifications / alerts** — fever alerts and disease warnings are currently display-only. Wire up email or SMS (Termii for Nigeria) when sensor thresholds are breached.

### Nice to have
11. **Offline mode / PWA** — the mobile field use case (taking photos, adding vet records) needs offline support with sync-on-reconnect. Service worker + IndexedDB.
12. **Multi-animal selector for bulk vet records** — e.g. apply one vaccination record to a whole herd batch.
13. **Herd map view** — show all animals as pins on a farm layout map.
14. **Lender collateral auto-valuation** — use herd health scores + milk yield trends to auto-calculate collateral value on the passport page.

---

## Key known issues (fixed)

- Demo mode was bouncing back to login: fixed — `demoLogin()` in AuthContext now sets state before navigation
- 401 response was clearing localStorage and hard-redirecting to login: fixed — removed `window.location.href` from 401 handler, errors bubble up to `_mockFallback`
- API timeout was 15s causing long loading: fixed — reduced to 3s
- Backend on port 8001, AuthContext was defaulting to 8000: fixed

---

## Environment

- macOS Darwin 25.3.0
- Python 3.12 (backend runs on port 8001)
- Node 20+ (frontend runs on port 3000)
- PostgreSQL (async) — DB connection details in `config.py`
- No Docker in use (Docker daemon was not running during development)

---

## File structure (key files only)

```
ndic/
├── app/
│   ├── api/          auth.py, farm_submissions.py, compliance.py, animals.py
│   ├── middleware/   access_control.py
│   ├── models/       rbac_models.py, animal_models.py
│   ├── services/     rbac_service.py, audit_service.py, storage_service.py, farm_service.py
│   └── main.py
├── models/           database.py, enums.py  (shared SQLAlchemy Base)
├── scripts/          seed_rbac.py
├── tests/            test_rbac_compliance.py (73 tests)
├── frontend/
│   └── src/
│       ├── api/      client.js, endpoints.js
│       ├── components/ FarmDashboard, GovDashboard, ProcessorDashboard, LenderDashboard, shared/
│       ├── context/  AuthContext.jsx
│       └── pages/    LoginPage, DashboardLayout, AnimalPassportPage
└── RESUME.md         ← this file
```
