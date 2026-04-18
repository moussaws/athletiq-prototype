"""FastAPI entry point."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from athletiq import __version__
from athletiq.api.routes import ahp_bip, cv, metrics, pitch_control, players, scouting

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


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


app.include_router(players.router, prefix="/api/players", tags=["players"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])
app.include_router(pitch_control.router, prefix="/api/pitch-control", tags=["pitch-control"])
app.include_router(scouting.router, prefix="/api/scouting", tags=["scouting"])
app.include_router(ahp_bip.router, prefix="/api/squad", tags=["squad"])
app.include_router(cv.router, prefix="/api/cv", tags=["cv"])
