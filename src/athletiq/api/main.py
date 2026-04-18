"""FastAPI entry point."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from athletiq import __version__
from athletiq.api.routes import (
    ahp_bip,
    cv,
    metrics,
    persistence,
    pitch_control,
    players,
    recruit,
    scouting,
    statsbomb,
    vaep,
)
from athletiq.db import init_db

app = FastAPI(
    title="AthletIQ Prototype API",
    version=__version__,
    description=(
        "End-to-end API for the AthletIQ deeptech analytics prototype: "
        "context-aware metrics, AI scouting, and single-camera CV pipeline."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


app.include_router(players.router, prefix="/api/players", tags=["players"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])
app.include_router(pitch_control.router, prefix="/api/pitch-control", tags=["pitch-control"])
app.include_router(scouting.router, prefix="/api/scouting", tags=["scouting"])
app.include_router(ahp_bip.router, prefix="/api/squad", tags=["squad"])
app.include_router(persistence.router, prefix="/api/squad", tags=["squad"])
app.include_router(cv.router, prefix="/api/cv", tags=["cv"])
app.include_router(statsbomb.router, prefix="/api/statsbomb", tags=["statsbomb"])
app.include_router(recruit.router, prefix="/api/recruit", tags=["recruit"])
app.include_router(vaep.router, prefix="/api/vaep", tags=["vaep"])
