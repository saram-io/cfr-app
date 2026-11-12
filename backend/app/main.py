from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import Base, SessionLocal, engine
from .routers import agents, assets, audit, auth, backups, dashboard, policies, restores, sops, storage
from .seed import seed_initial_data


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_initial_data(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="CFR-App: Life Science Asset & GxP Restic Backup Management System",
    description=(
        "MIT Open-Source Asset Criticality, GMP Classification, Restic Multi-Backend Backup Orchestration, "
        "SOP Restore Drill Verification, and 21 CFR Part 11 Electronic Signature & Audit Trail Platform."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(dashboard.router, prefix=API_PREFIX)
app.include_router(assets.router, prefix=API_PREFIX)
app.include_router(storage.router, prefix=API_PREFIX)
app.include_router(policies.router, prefix=API_PREFIX)
app.include_router(backups.router, prefix=API_PREFIX)
app.include_router(restores.router, prefix=API_PREFIX)
app.include_router(sops.router, prefix=API_PREFIX)
app.include_router(agents.router, prefix=API_PREFIX)
app.include_router(audit.router, prefix=API_PREFIX)


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "cfr-app-backend", "version": "1.0.0"}
