from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import auth, farm_submissions, compliance
from app.api import animals

UPLOAD_DIR = Path("uploads/animal-photos")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from config import build_engine, build_session_factory
    engine = build_engine()
    app.state.session_factory = build_session_factory(engine)
    yield
    await engine.dispose()


app = FastAPI(title="NDIC", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads/animal-photos", StaticFiles(directory=str(UPLOAD_DIR)), name="animal-photos")

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(farm_submissions.router, prefix="/api/farms", tags=["Farms"])
app.include_router(compliance.router, prefix="/api/compliance", tags=["Compliance"])
app.include_router(animals.router, prefix="/api", tags=["Animals"])


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"name": "NDIC"}
