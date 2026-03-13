# NDIC Platform — Resume Prompt

Paste the contents of this file at the start of a new session to pick up exactly where we left off.

---

## Project

**Nigerian Dairy Intelligence Consortium (NDIC) Platform**
A full-stack herd intelligence platform for Nigerian dairy farming — multi-role dashboards, RBAC/compliance infrastructure, and a Cow Passport system with sensor data, vet records, and photo ML.

**GitHub:** https://github.com/DMFP13/ndic-platform
**Live demo:** https://frontend-henna-one-46.vercel.app
**Local root:** `/Users/mac1/ndic/`
**Frontend:** `/Users/mac1/ndic/frontend/`

---

## Current state (as of 2026-03-13)

- Full platform built and working in demo mode
- Frontend deployed live on Vercel — colleagues can access and test now
- Backend running locally on port 8001 — not yet cloud-deployed
- All code backed up to GitHub (3 commits on main)
- No real database connected — all data is mock/simulated, clearly labelled in the UI

---

## How to start the servers locally

```bash
# Backend (FastAPI)
cd /Users/mac1/ndic
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# Frontend (Vite dev server)
cd /Users/mac1/ndic/frontend
npm run dev
# Opens on http://localhost:3000 (falls back to 3001 if 3000 is busy)
```

**Demo login:** go to `http://localhost:3000` or the live Vercel URL, pick any role, click the green **▶ Demo Mode** button. No backend needed — all data is mocked with a clear MOCK label.

## How to redeploy frontend to Vercel

```bash
cd /Users/mac1/ndic/frontend
vercel --prod
# Vercel account: danjpeters-2477
```

---

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 async, Pydantic v2, Uvicorn |
| Database | PostgreSQL (async via asyncpg) — not yet connected |
| Frontend | React 18, Vite 5, Tailwind CSS 3, Recharts, react-leaflet, Axios |
| Auth | JWT (HS256), refresh tokens, Ed25519 record signatures |
| Storage | Local filesystem (`uploads/animal-photos/`) → S3-ready via `STORAGE_BACKEND=s3` |
| Hosting | Frontend: Vercel. Backend: local only (next step: Railway or Render) |

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

**Cow Passport**
- `app/models/animal_models.py` — SensorReading, VetRecord, AnimalPhoto ORM tables
- `app/services/storage_service.py` — `save_photo()` / `get_photo_url()` / `delete_photo()`, local now, S3 in prod via `STORAGE_BACKEND=s3` env var — zero code changes needed to switch
- `app/api/animals.py` — 10 endpoints: passport, sensor history, vet records CRUD, photo upload/delete, ML ID stub at `POST /api/animals/identify-from-photo`
- All endpoints return realistic mock data when DB tables don't exist yet (pre-migration)

### Frontend

**9 roles:** farm_manager, farm_admin, farm_vet, processor_analyst, processor_commercial, govt_analyst, govt_admin, lender_analyst, arpexas_admin

**Pages/components:**
- `LoginPage.jsx` — demo mode (bypasses backend), role dropdown, 3s timeout before auto-demo on network failure
- `DashboardLayout.jsx` — top nav, collapsible sidebar, audit log panel, role badge
- `GovDashboard.jsx` — react-leaflet disease outbreak map, production BarChart, early warnings
- `ProcessorDashboard.jsx` — supply forecast AreaChart with confidence bands, supplier table, benchmarking
- `FarmDashboard.jsx` — animal table with expand/collapse AI panel, interventions accordion, climate section. Each animal row has a **Passport →** link
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
| farm_vet | /farm | Yes (vet records + photos) |
| processor_analyst | /processor | No |
| processor_commercial | /processor | No |
| govt_analyst | /government | No |
| govt_admin | /government | No |
| lender_analyst | /lender | No |
| arpexas_admin | /government | No |

**Cow Passport URL:** `/farm/animals/:animalId` or `/animals/:animalId` (cross-role read)

---

## What is NOT done yet — prioritised next steps

### Must-do before going live with real data

1. **Deploy backend to the cloud** — frontend is live on Vercel, backend still only runs locally. Easiest path: Railway (free tier, connects to GitHub, auto-deploys on push). Estimated time: 30 minutes.

2. **Database migration** — the new `sensor_readings`, `vet_records`, `animal_photos` tables exist as ORM models but have never been applied to a real PostgreSQL database. Need Alembic or a manual `CREATE TABLE` run. Until this is done, all passport data is mock.

3. **Auth URL alignment** — `AuthContext.jsx` calls `http://localhost:8001/auth/...` but the real backend route is `/api/auth/login`. In demo mode this doesn't matter (falls to mock), but needs fixing for real login to work. One-line fix in `AuthContext.jsx`.

4. **Connect a live PostgreSQL database** — Railway and Render both offer managed Postgres on free tiers. Set `DATABASE_URL` env var on the backend and the ORM connects automatically.

### High priority features

5. **Real sensor integration** — `SensorReading` model and API are ready. Need to wire up the actual IoT device protocol (RFID/BLE/bolus sensor) and a background ingestion task to receive and store readings continuously.

6. **ML cow identification** — `POST /api/animals/identify-from-photo` is a working stub. Real integration point is in `app/api/animals.py → identify_from_photo()`. Suggested model: fine-tuned MobileNetV3 or EfficientNet trained on Nigerian cattle breeds.

7. **S3 photo storage** — `storage_service.py` is fully wired. To activate: set `STORAGE_BACKEND=s3`, `S3_BUCKET`, `S3_REGION`, AWS credentials. Zero code changes needed.

### Medium priority

8. **Cow Passport — set primary photo** — UI allows upload but no button to designate a photo as primary. Small addition to photo gallery.

9. **Cow Passport — PDF export** — printable/downloadable passport for physical records, vet visits, loan collateral documents.

10. **Passport links from Processor and Lender dashboards** — routes are configured read-only for these roles but the dashboards don't yet have "View Passport" links in their tables.

11. **Push / SMS alerts** — fever alerts and disease warnings are display-only. Wire up email or Termii SMS (Nigeria) when sensor thresholds are breached.

12. **Offline / PWA support** — field use (taking photos, adding vet records with no signal) needs offline-first architecture with sync-on-reconnect.

### Nice to have

13. **Bulk vet records** — apply one vaccination or treatment to a group of animals at once.
14. **Herd map view** — show all animals as pins on a farm layout map.
15. **Auto collateral valuation** — use health scores + yield trends to auto-calculate herd collateral value on the lender's passport view.
16. **Custom domain** — replace `frontend-henna-one-46.vercel.app` with `platform.ndic.ng` or similar.

---

## Known issues (all fixed in current build)

- Demo mode was bouncing back to login → fixed: `demoLogin()` in AuthContext now sets state before navigation
- 401 response was clearing localStorage and hard-redirecting to login → fixed: removed `window.location.href` from 401 handler
- API timeout was 15s causing long spinner → fixed: reduced to 3s
- Backend on port 8001, AuthContext defaulting to 8000 → fixed

---

## Environment

- macOS Darwin 25.3.0
- Python 3.12 (backend runs on port 8001)
- Node 20+ (frontend runs on port 3000)
- PostgreSQL (async) — DB connection details in `config.py`
- No Docker in use
- Vercel account: danjpeters-2477

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
│   ├── vercel.json   (SPA rewrite rule)
│   └── src/
│       ├── api/      client.js, endpoints.js
│       ├── components/ FarmDashboard, GovDashboard, ProcessorDashboard, LenderDashboard, shared/
│       ├── context/  AuthContext.jsx
│       └── pages/    LoginPage, DashboardLayout, AnimalPassportPage
└── RESUME.md         ← this file
```

---

## Project description (plain English, for sharing with stakeholders)

The NDIC Platform is a shared intelligence system for Nigeria's dairy industry. It is a secure online hub where everyone involved in dairy — farmers, milk processors, government inspectors, and bank lenders — can each see exactly the information they need, without seeing information that isn't theirs.

**Nine user roles** each get a tailored dashboard:
- **Farm staff and vets** — full herd health, AI risk scores, financial performance, and individual cow passports
- **Milk processors** — supply forecasts, supplier health, quality grades
- **Government / FMARD** — national disease map, production trends by state, early warning alerts
- **Lenders** — loan portfolio health, collateral (herd) valuations, default risk signals

**The Cow Passport** is a lifelong digital record for every individual animal: identity, live sensor readings (temperature, weight, milk yield, heart rate, activity, feed), 30-day trend charts, full veterinary history (vaccinations, treatments, diseases), and a photo gallery with mobile camera capture and AI-powered animal identification.

**Security and compliance** is built into the foundation: role-based access enforced at the server level, an immutable 3-year audit log of every action, cryptographic signatures on every record, data deletion support, and chain-integrity verification — meeting GDPR-equivalent standards.

The demo at **https://frontend-henna-one-46.vercel.app** shows all dashboards and features running on clearly-labelled simulated data. The platform is ready to connect to live sensors, a production database, and cloud storage with no architectural changes.
